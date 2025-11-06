# projecoes.py
import pandas as pd
import numpy as np
from datetime import timedelta
from sklearn.linear_model import LinearRegression

def projecao_linear(dados_timeline, dias_projecao=30):    
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

def projecao_media(dados_timeline, dias_projecao=30):
    """Projeção conservadora usando SEMPRE os 3 primeiros dias como base"""
    if len(dados_timeline) < 2:
        return None
    
    dados = dados_timeline.sort_values('data')
    
    # SEMPRE USAR OS 3 PRIMEIROS DIAS para o modelo
    dados_3_primeiros = dados.head(3)
    
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
    
    dados['tipo'] = 'Histórico'
    return dados, projecao_df, crescimento_suavizado
