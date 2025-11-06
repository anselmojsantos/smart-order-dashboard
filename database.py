# database.py
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

@st.cache_resource
def get_engine():
    """Cria o engine UMA vez e mantém em cache"""
    connection_string = f"postgresql://{st.secrets['DB_USER']}:{st.secrets['DB_PASSWORD']}@{st.secrets['DB_HOST']}:{st.secrets['DB_PORT']}/{st.secrets['DB_NAME']}"
    return create_engine(connection_string)

@st.cache_data(ttl=300)
def carregar_dados():
    """Carrega todos os dados do dashboard"""
    try:
        engine = get_engine()
        
        queries = {
            'timeline': text("""
                SELECT 
                    DATE("created_at") as data,
                    COUNT(*) as quantidade,
                    SUM(total) as valor_total
                FROM payments 
                WHERE "created_at" IS NOT NULL
                GROUP BY DATE("created_at")
                ORDER BY data DESC
                LIMIT 180;
            """),
            'top_pratos': text("""
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
            """),
            'garcons': text("""
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
            """),
            'satisfacao': text("""
                SELECT 
                    note as nota,
                    COUNT(*) as quantidade
                FROM "satisfactions_survey" 
                WHERE note IS NOT NULL
                GROUP BY note
                ORDER BY note;
            """),
            'pagamentos_tipo': text("""
                SELECT 
                    payment_type as tipo_pagamento,
                    COUNT(*) as quantidade,
                    SUM(total) as valor_total
                FROM payments 
                WHERE status = 'paid'
                GROUP BY payment_type
                ORDER BY quantidade DESC;
            """)
        }
        
        dados = {}
        with engine.connect() as conn:
            for chave, query in queries.items():
                dados[chave] = pd.read_sql(query, conn)

        # Processar dados
        if not dados['timeline'].empty:
            dados['timeline']['data'] = pd.to_datetime(dados['timeline']['data'])
        
        return dados
        
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return None