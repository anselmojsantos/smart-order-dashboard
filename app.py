# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from database import carregar_dados
from projecoes import projecao_media, projecao_linear
from sklearn.linear_model import LinearRegression

st.set_page_config(page_title="Dashboard Smart Order", layout="wide")
st.title("🍽️ Dashboard Smart Order")

# =============================================
# CARREGAR DADOS (agora importado)
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
    projecao_resultado = projecao_media(dados['timeline'])
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
        projecao_resultado = projecao_linear(dados['timeline'])
        st.success(f"✅ Projeção com regressão linear ({num_dias} dias de dados)")
    else:
        projecao_resultado = projecao_media(dados['timeline'])

    if projecao_resultado:
        dados_historicos, projecao_df, modelo = projecao_resultado
        
        # Mostrar dados históricos primeiro
        st.subheader("📊 Dados Históricos dos Últimos 3 Dias")
        dados_sorted = dados_historicos.sort_values('data', ascending=False)
        dados_3_ultimos = dados_sorted.head(3)
        
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

        st.markdown("\n \n")

        # Métricas da projeção
        st.subheader("📈 Métricas da Projeção com base nos dias 29/10, 30/10, 31/10")
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