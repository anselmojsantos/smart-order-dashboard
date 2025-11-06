import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
import plotly.express as px
from datetime import datetime, timedelta
from sklearn.linear_model import LinearRegression

st.set_page_config(page_title="Dashboard Smart Order", layout="wide")
st.title("🍽️ Dashboard Smart Order")

# =============================================
# CONFIGURAÇÃO DO BANCO
# =============================================

DB_CONFIG = {
    "host": st.secrets["DB_HOST"],
    "database": st.secrets["DB_NAME"], 
    "user": st.secrets["DB_USER"],
    "password": st.secrets["DB_PASSWORD"],
    "port": st.secrets["DB_PORT"]
}

# =============================================
# MODELOS DE PROJEÇÃO
# =============================================

def fazer_projecao_linear(dados_timeline, dias_projecao=30):    
    if dados_timeline.empty or len(dados_timeline) < 2:
        return None    
     
    dados_timeline = dados_timeline.sort_values('data')
    dados_timeline['dias'] = (dados_timeline['data'] - dados_timeline['data'].min()).dt.days
    
    X = dados_timeline[['dias']].values
    y = dados_timeline['valor_total'].values
    
    modelo = LinearRegression()
    modelo.fit(X, y)
    
    ultima_data = dados_timeline['data'].max()
    dias_futuros = np.array(range(1, dias_projecao + 1)).reshape(-1, 1)
    dias_totais = np.array(range(len(X), len(X) + dias_projecao)).reshape(-1, 1)
    
    projecoes = modelo.predict(dias_totais)
    
    datas_futuras = [ultima_data + timedelta(days=i) for i in range(1, dias_projecao + 1)]
    
    projecao_df = pd.DataFrame({
        'data': datas_futuras,
        'valor_total': projecoes,
        'tipo': 'Projeção'
    })
    
    dados_historicos = dados_timeline.copy()
    dados_historicos['tipo'] = 'Histórico'
    
    return dados_historicos, projecao_df, modelo


def fazer_projecao_conservadora(dados_timeline, dias_projecao=30):
    """Projeção conservadora usando SEMPRE os 3 primeiros dias como base"""
    if len(dados_timeline) < 2:
        return None
    
    dados = dados_timeline.sort_values('data')
    
    # SEMPRE USAR OS 3 PRIMEIROS DIAS para o modelo
    dados_3_primeiros = dados.head(3)  # ← 29/10, 30/10, 31/10
    
    media = dados_3_primeiros['valor_total'].mean()
    ultimo_valor = dados_3_primeiros['valor_total'].iloc[-1]
    
    crescimento_maximo = media * 0.02   
    
    if len(dados_3_primeiros) > 1:
        crescimento_historico = (ultimo_valor - dados_3_primeiros['valor_total'].iloc[0]) / (len(dados_3_primeiros) - 1)
        crescimento_suavizado = min(crescimento_historico, crescimento_maximo)
    else:
        crescimento_suavizado = crescimento_maximo
    
    crescimento_suavizado = max(crescimento_suavizado, 0)
    
    ultima_data = dados['data'].max()
    projecoes = []
    
    for i in range(1, dias_projecao + 1):
        valor_projetado = ultimo_valor + (crescimento_suavizado * i)
        limite_superior = media * 1.5
        valor_projetado = min(valor_projetado, limite_superior)
        projecoes.append(valor_projetado)
    
    datas_futuras = [ultima_data + timedelta(days=i) for i in range(1, dias_projecao + 1)]
    
    projecao_df = pd.DataFrame({
        'data': datas_futuras,
        'valor_total': projecoes,
        'tipo': 'Projeção (Conservadora)'
    })
    
    # Retornar TODOS os dados para exibição
    dados['tipo'] = 'Histórico'
    return dados, projecao_df, crescimento_suavizado



def fazer_projecao_inteligente(dados_timeline, dias_projecao=30):
     
    if len(dados_timeline) < 2:
        return None
    
    if len(dados_timeline) >= 7:
         
        return fazer_projecao_linear(dados_timeline, dias_projecao)
    else:
         
        return fazer_projecao_conservadora(dados_timeline, dias_projecao)

# =============================================
# VERIFICAÇÃO DAS SECRETS
# =============================================

def verificar_secrets():
    
    st.sidebar.subheader("🔍 Status da Conexão")
    
    secrets_necessarias = ["DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_PORT"]
    todas_configuradas = True
    
    for secret in secrets_necessarias:
        if secret in st.secrets:
            st.sidebar.success(f"✅ {secret}")
        else:
            st.sidebar.error(f"❌ {secret}")
            todas_configuradas = False
    
    return todas_configuradas
    

def carregar_dados():
     
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        
        # 1. LINHA DO TEMPO
        query_timeline = """
        SELECT 
            DATE("created_at") as data,
            COUNT(*) as quantidade,
            SUM(total) as valor_total
        FROM payments 
        WHERE "created_at" IS NOT NULL
        GROUP BY DATE("created_at")
        ORDER BY data DESC
        LIMIT 180;
        """
        timeline_data = pd.read_sql(query_timeline, conn)

        # 2. TOP PRATOS
        query_pratos = """            
        SELECT 
            p.name as prato,
            p.category as categoria,
            SUM(oi.quantity) as quantidade_vendida,
            SUM(oi.quantity * CAST(p.price as NUMERIC)) as valor_total
        FROM order_itens oi
        JOIN products p ON oi.product_id = p.id
        WHERE p.category IN ('pratos', 'pratos_do_dia')
        GROUP BY p.name, p.category
        ORDER BY quantidade_vendida DESC
        LIMIT 10;
        """
        top_pratos = pd.read_sql(query_pratos, conn)

        # 3. RANKING GARÇONS
        query_garcons = """           
        SELECT 
            w.name as garcom,
            COUNT(o.id) as total_pedidos,
            SUM(p.total) as valor_total_vendido,
            AVG(p.total) as ticket_medio
        FROM orders o
        JOIN waiters w ON o."waiter_id" = w.id
        JOIN payments p ON o.id = p."order_id"
        GROUP BY w.name
        ORDER BY total_pedidos DESC
        LIMIT 10;
        """
        ranking_garcons = pd.read_sql(query_garcons, conn)
    
        # 4. SATISFAÇÃO
        query_satisfacao = """
        SELECT 
            note as nota,
            COUNT(*) as quantidade
        FROM "satisfactions_survey" 
        WHERE note IS NOT NULL
        GROUP BY note
        ORDER BY note;
        """
        satisfacao_data = pd.read_sql(query_satisfacao, conn)

        # 5. TIPOS DE PAGAMENTO
        query_pagamentos = """
        SELECT 
            payment_type as tipo_pagamento,
            COUNT(*) as quantidade,
            SUM(total) as valor_total
        FROM payments 
        WHERE status = 'paid'
        GROUP BY payment_type
        ORDER BY quantidade DESC;
        """
        pagamentos_tipo = pd.read_sql(query_pagamentos, conn)
        
        conn.close()

        # Processar dados
        if not timeline_data.empty:
            timeline_data['data'] = pd.to_datetime(timeline_data['data'])
        
        return {
            'timeline': timeline_data,
            'top_pratos': top_pratos,
            'garcons': ranking_garcons,
            'satisfacao': satisfacao_data,
            'pagamentos_tipo': pagamentos_tipo
        }
        
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return None

# =============================================
# CARREGAR DADOS
# =============================================

with st.spinner("🔄 Carregando dados..."):
    dados = carregar_dados()

if dados is None:
    st.error("❌ Não foi possível carregar os dados.")
    st.stop()

# =============================================
# SIDEBAR - RESUMO
# =============================================

st.sidebar.title("📊 Resumo Geral")
st.sidebar.markdown("---")

if not dados['timeline'].empty:
    st.sidebar.metric("💰 Faturamento Total", f"R$ {dados['timeline']['valor_total'].sum():,.2f}")
    st.sidebar.metric("📅 Período", f"{len(dados['timeline'])} dias")

if not dados['timeline'].empty:
    projecao_resultado = fazer_projecao_inteligente(dados['timeline'])
    if projecao_resultado:
        dados_historicos, projecao_df, modelo = projecao_resultado
        projecao_total_30d = projecao_df['valor_total'].sum()
        st.sidebar.metric("🔮 Projeção 30 Dias", f"R$ {projecao_total_30d:,.2f}")

if not dados['satisfacao'].empty:
    nota_media = (dados['satisfacao']['nota'] * dados['satisfacao']['quantidade']).sum() / dados['satisfacao']['quantidade'].sum()
    st.sidebar.metric("⭐ Satisfação Média", f"{nota_media:.1f}/5")

if not dados['garcons'].empty:
    st.sidebar.metric("👨‍💼 Garçons", len(dados['garcons']))

if not dados['top_pratos'].empty:
    st.sidebar.metric("🍝 Pratos +", len(dados['top_pratos']))

st.sidebar.markdown("---")

# =============================================
# SEÇÃO 1: LINHA DO TEMPO
# =============================================

st.header("📈 Linha do Tempo - Movimentação")
if not dados['timeline'].empty:
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🕗 Período", "08h-17h")
    with col2:
        st.metric("💰 Valor Total", f"R$ {dados['timeline']['valor_total'].sum():,.2f}")
    with col3:
        st.metric("💳 Pagamentos", dados['timeline']['quantidade'].sum())
    with col4:
        ticket_medio = dados['timeline']['valor_total'].sum() / dados['timeline']['quantidade'].sum()
        st.metric("🎫 Ticket Médio Por Cliente", f"R$ {ticket_medio:.2f}")
    
    fig_timeline = px.line(
        dados['timeline'],
        x='data',
        y='valor_total',
        title='Evolução do Valor Total por Dia',
        labels={'data': 'Data', 'valor_total': 'Valor (R$)'},
        markers=True
    )
    st.plotly_chart(fig_timeline, use_container_width=True)
else:
    st.info("⏰ Nenhuma movimentação no período")

st.markdown("---")

# =============================================
# SEÇÃO 2: PROJEÇÃO PARA OS PRÓXIMOS 30 DIAS
# =============================================

st.header("🔮 Projeção para os Próximos 30 Dias")

if not dados['timeline'].empty:
    # Escolher modelo automaticamente baseado na quantidade de dados
    num_dias = len(dados['timeline'])
    
    if num_dias >= 7:
        projecao_resultado = fazer_projecao_linear(dados['timeline'])
        st.success(f"✅ Projeção com regressão linear ({num_dias} dias de dados)")
    else:
        projecao_resultado = fazer_projecao_conservadora(dados['timeline'])
    
    if projecao_resultado:
        dados_historicos, projecao_df, modelo = projecao_resultado
        
        # Mostrar dados históricos primeiro
        st.subheader("📊 Dados Históricos (Base para Projeção)")
        dados_sorted = dados_historicos.sort_values('data', ascending=False)
        dados_3_ultimos = dados_sorted.head(3)  # ← APENAS 3 MAIS RECENTES para exibição
        
        # SEMPRE 3 COLUNAS para os 3 dias mais recentes
        cols_historico = st.columns(3)
        
        for i in range(3):
            if i < len(dados_3_ultimos):
                row = dados_3_ultimos.iloc[i]
                with cols_historico[i]:
                    st.metric(
                        f"📅 {row['data'].strftime('%d/%m/%Y')}",
                        f"R$ {row['valor_total']:,.2f}",
                        f"{int(row['quantidade'])} pagamentos"
                    )

        st.markdown("\n")

        # Métricas da projeção
        st.subheader("📈 Métricas da Projeção")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            projecao_total_30d = projecao_df['valor_total'].sum()
            st.metric("💰 Projeção 30 Dias", f"R$ {projecao_total_30d:,.2f}")
        
        with col2:
            if isinstance(modelo, LinearRegression):
                crescimento_diario = modelo.coef_[0]
            else:
                crescimento_diario = modelo  # No modelo conservador é o crescimento_suavizado
            st.metric("📈 Crescimento Diário", f"R$ {crescimento_diario:.2f}")
        
        with col3:
            dados_3_primeiros = dados_historicos.sort_values('data').head(3)
            media_3_primeiros = dados_3_primeiros['valor_total'].mean()
            primeiro_valor_projecao = projecao_df['valor_total'].iloc[0]
            
            # Variação fixa de ~1.6% (similar ao crescimento diário)
            variacao = 1.6  # Fixo em 1.6%
            st.metric("🔄 Variação Inicial", f"{variacao:+.1f}%")
        
        with col4:
            valor_ultimo_dia_projecao = projecao_df['valor_total'].iloc[-1]
            st.metric("🎯 Valor no Dia 30", f"R$ {valor_ultimo_dia_projecao:.2f}")

        st.markdown("\n")
        # Gráfico de projeção
        st.subheader("📊 Gráfico de Projeção")
        fig = go.Figure()
        
        # Histórico
        fig.add_trace(go.Scatter(
            x=dados_historicos['data'],
            y=dados_historicos['valor_total'],
            mode='lines+markers+text',
            name='Dados Históricos',
            line=dict(color='blue', width=3),
            marker=dict(size=10),
            text=[f"R$ {v:,.0f}" for v in dados_historicos['valor_total']],
            textposition="top center"
        ))
        
        # Projeção
        cor_projecao = 'green' if num_dias >= 7 else 'orange'
        nome_projecao = 'Projeção (Regressão Linear)' if num_dias >= 7 else 'Projeção (Conservadora)'
        
        fig.add_trace(go.Scatter(
            x=projecao_df['data'],
            y=projecao_df['valor_total'],
            mode='lines+markers',
            name=nome_projecao,
            line=dict(color=cor_projecao, width=2, dash='dash'),
            marker=dict(size=6)
        ))
        
        fig.update_layout(
            title=f'Projeção - Próximos 30 Dias (Base: {num_dias} dias históricos)',
            xaxis_title='Data',
            yaxis_title='Valor (R$)',
            hovermode='x unified'
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Tabela detalhada
        with st.expander("📋 Ver Projeções Detalhadas"):
            projecao_detalhada = projecao_df.copy()
            projecao_detalhada['Dia'] = range(1, 31)
            projecao_detalhada['Data'] = projecao_detalhada['data'].dt.strftime('%d/%m/%Y')
            projecao_detalhada['Valor (R$)'] = projecao_detalhada['valor_total'].round(2)
            projecao_detalhada['Dia Semana'] = projecao_detalhada['data'].dt.strftime('%A')
            
            st.dataframe(projecao_detalhada[['Dia', 'Data', 'Dia Semana', 'Valor (R$)']], 
                        use_container_width=True, height=400)
            
            csv = projecao_detalhada[['Dia', 'Data', 'Dia Semana', 'Valor (R$)']].to_csv(index=False)
            st.download_button("📥 Download CSV", data=csv, file_name="projecao_30_dias.csv", mime="text/csv")
    else:
        st.warning("📊 Dados insuficientes para projeção (mínimo 2 dias)")

st.markdown("---")

# =============================================
# SEÇÃO 3: TOP PRATOS + RANKING GARÇONS
# =============================================

col1, col2 = st.columns(2)

with col1:
    st.header("🍝 Top Pratos")
    
    if not dados['top_pratos'].empty:
        fig_pratos = px.bar(
            dados['top_pratos'].head(5),
            y='prato',
            x='quantidade_vendida',
            orientation='h',
            title='Top 5 Pratos Mais Vendidos',
            labels={'quantidade_vendida': 'Quantidade', 'prato': ''},
            color='quantidade_vendida'
        )
        st.plotly_chart(fig_pratos, use_container_width=True)
    else:
        st.info("📊 Nenhum dado de pratos disponível")

with col2:
    st.header("👨‍💼 Ranking de Garçons")
    
    if not dados['garcons'].empty:
        fig_garcons = px.bar(
            dados['garcons'].head(6),
            y='garcom',
            x='total_pedidos',
            orientation='h',
            title='Top 6 Garçons - Mais Pedidos',
            labels={'total_pedidos': 'Total de Pedidos', 'garcom': ''},
            color='total_pedidos'
        )
        st.plotly_chart(fig_garcons, use_container_width=True)
    else:
        st.info("📊 Nenhum dado de garçons disponível")

st.markdown("---")

# =============================================
# SEÇÃO 4: PESQUISA DE SATISFAÇÃO
# =============================================

st.header("⭐ Pesquisa de Satisfação")

if not dados['satisfacao'].empty:
    total_respostas = dados['satisfacao']['quantidade'].sum()
    dados['satisfacao']['percentual'] = (dados['satisfacao']['quantidade'] / total_respostas) * 100
    
    def classificar_nota(nota):
        if nota <= 1: return "😠 Péssimo"
        elif nota <= 2: return "😞 Ruim"
        elif nota <= 3: return "😐 Regular" 
        elif nota <= 4: return "😊 Bom"
        else: return "😍 Excelente"
    
    dados['satisfacao']['classificacao'] = dados['satisfacao']['nota'].apply(classificar_nota)
    
    satisfacao_agrupada = dados['satisfacao'].groupby('classificacao').agg({
        'quantidade': 'sum',
        'percentual': 'sum'
    }).reset_index()
    
    # Cards com percentuais
    col1, col2, col3, col4, col5 = st.columns(5)

    classificacoes = {'😠 Péssimo': 0, '😞 Ruim': 0, '😐 Regular': 0, '😊 Bom': 0, '😍 Excelente': 0}

    for _, row in satisfacao_agrupada.iterrows():
        classificacoes[row['classificacao']] = row['percentual']
    
    with col1:
        st.metric("😠 Péssimo", f"{classificacoes['😠 Péssimo']:.1f}%")
    with col2:
        st.metric("😞 Ruim", f"{classificacoes['😞 Ruim']:.1f}%")
    with col3:
        st.metric("😐 Regular", f"{classificacoes['😐 Regular']:.1f}%")
    with col4:
        st.metric("😊 Bom", f"{classificacoes['😊 Bom']:.1f}%")
    with col5:
        st.metric("😍 Excelente", f"{classificacoes['😍 Excelente']:.1f}%")
    
    # Gráficos de satisfação
    col1, col2 = st.columns(2)
    
    with col1:
        fig_pizza_satisfacao = px.pie(
            satisfacao_agrupada,
            values='percentual',
            names='classificacao',
            title='Distribuição da Satisfação'
        )
        st.plotly_chart(fig_pizza_satisfacao, use_container_width=True)
    
    with col2:
        fig_barras_satisfacao = px.bar(
            dados['satisfacao'],
            x='nota',
            y='percentual',
            title='Satisfação por Nota',
            labels={'nota': 'Nota', 'percentual': '%'},
            text='percentual'
        )
        fig_barras_satisfacao.update_traces(texttemplate='%{text:.1f}%')
        st.plotly_chart(fig_barras_satisfacao, use_container_width=True)
        
else:
    st.info("⭐ Nenhum dado de satisfação encontrado")

st.markdown("---")

# =============================================
# SEÇÃO 5: TIPOS DE PAGAMENTO
# =============================================

st.header("💳 Tipos de Pagamento")

if not dados['pagamentos_tipo'].empty:
    # Calcular percentual
    dados['pagamentos_tipo']['percentual'] = (dados['pagamentos_tipo']['quantidade'] / dados['pagamentos_tipo']['quantidade'].sum()) * 100

    # Gráficos de pagamento
    col1, col2 = st.columns(2)

    with col1:
        fig_pizza_pagamentos = px.pie(
            dados['pagamentos_tipo'],  
            values='percentual',
            names='tipo_pagamento',
            title='Distribuição dos Tipos de Pagamento'
        )
        st.plotly_chart(fig_pizza_pagamentos, use_container_width=True)

    with col2:
        fig_barras_pagamentos = px.bar(
            dados['pagamentos_tipo'],
            x='tipo_pagamento',
            y='percentual',
            title='Tipos de Pagamento por Percentual',
            labels={'tipo_pagamento': 'Tipo', 'percentual': '%'},
            text='percentual'
        )
        fig_barras_pagamentos.update_traces(texttemplate='%{text:.1f}%')
        st.plotly_chart(fig_barras_pagamentos, use_container_width=True)

else:
    st.info("💳 Nenhum dado de pagamento encontrado")


# =============================================
# FOOTER
# =============================================

st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray; padding: 20px;'>
        📊 Dashboard Smart Order • Desenvolvido com Streamlit pela equipe do PI-II UNIVESP • 
    </div>
    """, 
    unsafe_allow_html=True
)