import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
from datetime import datetime, timedelta

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
# VERIFICAÇÃO DAS SECRETS
# =============================================

def verificar_secrets():
    """Função para verificar se as secrets estão carregadas"""
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
    """Carrega todos os dados para o dashboard"""
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
        LIMIT 90;
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
        st.metric("🎫 Ticket Médio", f"R$ {ticket_medio:.2f}")
    
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
# SEÇÃO 2: TOP PRATOS + RANKING GARÇONS
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
# SEÇÃO 3: PESQUISA DE SATISFAÇÃO
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
# SEÇÃO 4: TIPOS DE PAGAMENTO
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
        📊 Dashboard Smart Order • Desenvolvido com Streamlit • 
    </div>
    """, 
    unsafe_allow_html=True
)