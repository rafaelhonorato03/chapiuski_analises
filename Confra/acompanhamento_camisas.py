import os
from dotenv import load_dotenv
from supabase import create_client, Client
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import math 
import re # Para manipulação de strings (nomes)

# Para Machine Learning
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from datetime import timedelta

# --- CONFIGURAÇÃO DA PÁGINA (Padrão/Centered) ---
st.set_page_config(
    layout="wide", 
    page_title="Painel de Vendas - Chapiuski (Avançado)"
)

# --- CONEXÃO E CARREGAMENTO DE DADOS INICIAIS ---
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

try:
    if SUPABASE_URL and SUPABASE_KEY:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    else:
        st.error("Variáveis de ambiente SUPABASE_URL ou SUPABASE_KEY não configuradas.")
        supabase = None
except Exception as e:
    st.error("Falha ao conectar com o Supabase.")
    st.error(f"Erro: {e}")
    st.stop()


# =========================================================================
# === FUNÇÕES DE BUSCA E UTILITY ==========================================
# =========================================================================

@st.cache_data(ttl=60) 
def buscar_dados_supabase(tabela):
    """Busca dados de uma tabela específica no Supabase, ajustando a ordenação."""
    
    if tabela == 'compra_ingressos':
        coluna_ordenacao = 'datahora'
    else:
        coluna_ordenacao = 'created_at'

    try:
        if supabase:
            response = supabase.table(tabela).select('*').order(coluna_ordenacao, desc=True).execute()
            return pd.DataFrame(response.data)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erro ao acessar a tabela '{tabela}': {e}")
        return pd.DataFrame()


def split_value(row_value, index):
    """Função auxiliar para separar valores em strings delimitadas por vírgula."""
    try:
        parts = str(row_value).split(',')
        return parts[index].strip()
    except IndexError:
        parts = str(row_value).split(',')
        return parts[-1].strip() if parts else ""

def standardize_email(email_series):
    """Padroniza e-mails para garantir unicidade (lower case e sem espaços)."""
    return email_series.astype(str).str.lower().str.strip()

def standardize_name(name_series):
    """Padroniza nomes removendo espaços múltiplos e espaços em branco desnecessários."""
    if name_series is None or name_series.empty:
        return pd.Series([], dtype='object')
    # Remove espaços múltiplos, converte para strip, e capitaliza o início de cada palavra
    cleaned_names = name_series.astype(str).apply(lambda x: re.sub(r'\s+', ' ', str(x).strip()).title() if pd.notna(x) else x)
    return cleaned_names

# =========================================================================
# === FUNÇÕES DE PROCESSAMENTO: CONFRA (Ajustado) =========================
# =========================================================================

def processar_dados_confra(df_confra):
    """Calcula KPIs e trata a base para a Confra."""
    if df_confra.empty:
        return 0, 0, 0, 0, pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    df = df_confra.copy()
    
    # 🎯 PADRONIZAÇÃO DE E-MAIL e NOME
    if 'email_comprador' in df.columns:
        df['email_comprador_padrao'] = standardize_email(df['email_comprador'])
        df['nome_comprador'] = standardize_name(df['nome_comprador'])
    
    # Cálculos de KPI
    df['qtd_confra'] = pd.to_numeric(df['qtd_confra'], errors='coerce').fillna(0).astype(int)
    df['qtd_copo'] = pd.to_numeric(df['qtd_copo'], errors='coerce').fillna(0).astype(int)
    total_ingressos_bruto = df['qtd_confra'].sum()
    total_copos = df['qtd_copo'].sum()
    total_arrecadado_pix = df['valor_pix'].sum()
    
    def contar_criancas(crianca_str):
        if pd.isna(crianca_str):
            return 0
        return str(crianca_str).lower().count('sim')

    df['qtd_criancas'] = df.apply(lambda row: contar_criancas(row.get('e_crianca')), axis=1)
    total_criancas_gratis = df['qtd_criancas'].sum()
    total_ingressos_pagantes = total_ingressos_bruto - total_criancas_gratis
    
    # 🎯 TRATAMENTO DE DATA - CORREÇÃO DE TIMEZONE
    df['data_pedido'] = pd.to_datetime(df['created_at'], errors='coerce') 
    if df['data_pedido'].dt.tz is not None:
        df['data_pedido'] = df['data_pedido'].dt.tz_convert('UTC').dt.tz_localize(None)
    df['data_pedido'] = df['data_pedido'].dt.tz_localize('UTC').dt.tz_convert('America/Sao_Paulo')
    
    # Expansão para Ingressos e Copos
    df_ingressos_expanded, df_copos_expanded = expandir_dados_confra(df)
    
    return total_ingressos_pagantes, total_criancas_gratis, total_copos, total_arrecadado_pix, df, df_ingressos_expanded, df_copos_expanded


def expandir_dados_confra(df):
    """Expande a tabela Confra em duas: uma para Ingressos e outra para Copos."""
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    df = df.copy()
    
    # --- 1. EXPANSÃO DE INGRESSOS (LISTA DE PARTICIPANTES) ---
    colunas_base_ingresso = [
        'data_pedido', 'nome_comprador', 'email_comprador_padrao', 'nomes_participantes', 
        'documentos_participantes', 'e_crianca', 'qtd_confra', 'id'
    ]
    cols_existentes_ingresso = [col for col in colunas_base_ingresso if col in df.columns]
    df_base_ingresso = df[cols_existentes_ingresso].loc[df['qtd_confra'] > 0].copy()
    
    if df_base_ingresso.empty:
          df_ingressos = pd.DataFrame()
    else:
        df_ingressos = df_base_ingresso.loc[df_base_ingresso.index.repeat(df_base_ingresso['qtd_confra'])].reset_index(drop=True)
        df_ingressos['seq_ingresso'] = df_ingressos.groupby('id').cumcount()
        
        # Nome do participante também padronizado
        df_ingressos['nome_participante'] = df_ingressos.apply(
            lambda x: standardize_name(pd.Series([split_value(x['nomes_participantes'], x['seq_ingresso'])])).iloc[0], axis=1
        )
        df_ingressos['documento_participante'] = df_ingressos.apply(
            lambda x: split_value(x['documentos_participantes'], x['seq_ingresso']), axis=1
        )
        df_ingressos['e_crianca_flag'] = df_ingressos.apply(
            lambda x: split_value(x['e_crianca'], x['seq_ingresso']), axis=1
        )
    
    # --- 2. EXPANSÃO DE COPOS (LISTA DE PERSONALIZAÇÃO) ---
    colunas_base_copo = [
        'data_pedido', 'nome_comprador', 'email_comprador_padrao', 'nomes_copo', 'qtd_copo', 'id'
    ]
    cols_existentes_copo = [col for col in colunas_base_copo if col in df.columns]
    df_base_copo = df[cols_existentes_copo].loc[df['qtd_copo'] > 0].copy()

    if df_base_copo.empty:
        df_copos = pd.DataFrame()
    else:
        df_copos = df_base_copo.loc[df_base_copo.index.repeat(df_base_copo['qtd_copo'])].reset_index(drop=True)
        df_copos['seq_copo'] = df_copos.groupby('id').cumcount()

        df_copos['nome_no_copo'] = df_copos.apply(
            lambda x: standardize_name(pd.Series([split_value(x['nomes_copo'], x['seq_copo'])])).iloc[0], axis=1
        )
    
    return df_ingressos, df_copos


# =========================================================================
# === FUNÇÕES DE PROCESSAMENTO: CAMISAS (Ajustado) =========================
# =========================================================================

def processar_dados_camisas(df_camisas):
    """Calcula KPIs e expande o DataFrame para análise por item (Camisas)."""
    if df_camisas.empty:
        return None
        
    df = df_camisas.copy()
    
    # 🎯 PADRONIZAÇÃO DE E-MAIL e NOME
    if 'email_comprador' in df.columns:
        df['email_comprador_padrao'] = standardize_email(df['email_comprador'])
        df['nome_comprador'] = standardize_name(df['nome_comprador'])
    
    # 🎯 TRATAMENTO DE DATA - CORREÇÃO DE TIMEZONE
    df['data_pedido'] = pd.to_datetime(df['created_at'], errors='coerce')
    if df['data_pedido'].dt.tz is not None:
        df['data_pedido'] = df['data_pedido'].dt.tz_convert('UTC').dt.tz_localize(None)
    df['data_pedido'] = df['data_pedido'].dt.tz_localize('UTC').dt.tz_convert('America/Sao_Paulo')

    # Expansão para 1 linha por camisa
    df['quantidade'] = pd.to_numeric(df['quantidade'], errors='coerce').fillna(0).astype(int) 
    df_expanded = df.loc[df.index.repeat(df['quantidade'])].reset_index(drop=True)
    df_expanded['seq_pedido'] = df_expanded.groupby('id').cumcount()

    # Aplica split para obter detalhes por camisa (Nome na camisa também padronizado)
    df_expanded['nome_na_camisa'] = df_expanded.apply(
        lambda x: standardize_name(pd.Series([split_value(x['detalhes_pedido'], x['seq_pedido']).split('(')[0].strip()])).iloc[0], axis=1
    )
    df_expanded['tamanho_individual'] = df_expanded.apply(lambda x: split_value(x['tamanho'], x['seq_pedido']), axis=1)
    df_expanded['tipo_individual'] = df_expanded.apply(lambda x: split_value(x['tipo_camisa'], x['seq_pedido']), axis=1)
    df_expanded['numero_individual'] = df_expanded.apply(lambda x: split_value(x['numero_camisa'], x['seq_pedido']), axis=1)

    # Mapeia o preço
    precos = {'Jogador': 150, 'Torcedor': 115}
    df_expanded['preco_individual'] = df_expanded['tipo_individual'].map(precos).fillna(0)
    
    return df_expanded


# =========================================================================
# === FUNÇÕES DE PROCESSAMENTO: FESTA 8 ANOS (Ajustado) ===================
# =========================================================================

def processar_dados_festa_8anos(df_festa):
    """Calcula KPIs e expande o DataFrame para a Festa 8 Anos. RETORNA O DF BRUTO/PADRONIZADO E O EXPANDIDO"""
    if df_festa.empty:
        return None
    
    df = df_festa.copy()
    
    # 🎯 PADRONIZAÇÃO DE E-MAIL
    if 'email' in df.columns:
        df['email_comprador_padrao'] = standardize_email(df['email'])
    
    # 🎯 TRATAMENTO DE DATA - CORREÇÃO DE TIMEZONE
    df['datahora'] = pd.to_datetime(df['datahora'], errors='coerce')
    if df['datahora'].dt.tz is not None:
        df['datahora'] = df['datahora'].dt.tz_convert('UTC').dt.tz_localize(None)
        
    df['datahora'] = df['datahora'].dt.tz_localize('UTC').dt.tz_convert('America/Sao_Paulo')
    
    # Expansão para 1 linha por ingresso
    df['quantidade'] = pd.to_numeric(df['quantidade'], errors='coerce').fillna(0).astype(int) 
    df_expanded = df.loc[df.index.repeat(df['quantidade'])].reset_index(drop=True)
    df_expanded['quantidade'] = 1 
    df_expanded['seq'] = df_expanded.groupby('id').cumcount()

    # Expansão dos participantes (Nome do participante também padronizado)
    df_expanded['nome_participante'] = df_expanded.apply(
        lambda x: standardize_name(pd.Series([split_value(x['nomes'], x['seq'])])).iloc[0], axis=1
    )
    df_expanded['documento_participante'] = df_expanded.apply(lambda x: split_value(x['documentos'], x['seq']), axis=1)

    # Mapeamento e cálculo de preço 
    precos = {'1º LOTE PROMOCIONAL': 100, '2º LOTE': 120}
    df_expanded['lote'] = df_expanded['lote'].str.upper().str.strip() 
    df_expanded['preco_unitario'] = df_expanded['lote'].map(precos).fillna(0)
    
    # KPIs
    total_vendido = df_expanded.shape[0]
    total_disponivel = 100 
    percentual_ocupacao = total_vendido / total_disponivel * 100 if total_disponivel else 0
    total_arrecadado = df_expanded['preco_unitario'].sum()

    venda_por_dia = df_expanded.groupby(df_expanded['datahora'].dt.date).size().reset_index(name='quantidade')
    venda_por_dia['quantidade'] = venda_por_dia['quantidade'].astype(int)
    velocidade_media = venda_por_dia['quantidade'].mean()
    
    return total_vendido, total_arrecadado, percentual_ocupacao, velocidade_media, df, df_expanded


# =========================================================================
# === MACHINE LEARNING E ANÁLISES AVANÇADAS (AJUSTADO PARA TODOS) =========
# =========================================================================

@st.cache_data
def calculate_optimal_k(X_scaled, max_k=10):
    """Aplica o Método do Cotovelo para encontrar o K ideal (interno)."""
    if X_scaled.shape[0] == 0:
        return 3 
        
    sse = []
    k_range = range(1, min(max_k, X_scaled.shape[0]) + 1)
        
    for k in k_range:
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        kmeans.fit(X_scaled)
        sse.append(kmeans.inertia_)
    
    return 3 

def interpret_clusters(df_cluster_analysis_indexed, K):
    """Gera uma descrição textual dos clusters baseada nas médias das métricas. (Interno)"""
    descriptions = {}
    
    if K == 3:
        df_analysis = df_cluster_analysis_indexed.T
        cluster_0_gasto = df_analysis.get('Cluster 0', pd.Series()).get('GASTO TOTAL (R$)', 0)
        
        if cluster_0_gasto > 0:
             descriptions['Cluster 0'] = f"Clientes de **Alto Valor (VIPs)**: Têm o maior gasto e alto volume de compras. Gasto médio: R$ {cluster_0_gasto:.2f}."
             descriptions['Cluster 1'] = f"Clientes **Frequentes/Moderados**: Alto volume de transações em eventos (Pedidos Confra/Festa). Gasto moderado."
             descriptions['Cluster 2'] = f"Clientes **Ocasionais/Novos**: Menor gasto e baixa frequência. Clientes em fase de aquisição."
        else:
             descriptions['Cluster 0'] = "Grupo 0: Tendência a ser o maior valor (Gasto Total)."
             descriptions['Cluster 1'] = "Grupo 1: Tendência a ser a maior frequência de pedidos."
             descriptions['Cluster 2'] = "Grupo 2: Tendência a ser o menor gasto/frequência."
    else:
         for i in range(K):
              descriptions[f'Cluster {i}'] = f"Cluster {i}: Analise as colunas do heatmap para identificar o perfil dominante (Gasto/Frequência)."
            
    return descriptions


def gerar_analises_avancadas(df_confra, df_camisas_expanded, df_festa, resultados_festa_kpis): 
    """Executa todas as análises de ML e visualizações solicitadas com tratamento de erro, 
       considerando Confra, Camisas e Festa 8 Anos."""
    
    st.subheader("Análises Avançadas e Consolidação de Vendas")
    st.markdown("---") 

    if df_confra.empty or df_camisas_expanded is None or df_camisas_expanded.empty or resultados_festa_kpis is None:
        st.warning("Dados insuficientes para executar todas as análises avançadas (Confra, Camisas e Festa).")
        return

    df_festa_expanded = resultados_festa_kpis[5].copy() 
    
    # -------------------------------------------------------------------------
    # CONSOLIDAÇÃO DE EMAILS (PARA CRESCIMENTO E LISTA)
    # -------------------------------------------------------------------------
    
    # df_confra: data_pedido, nome_comprador (JÁ PADRONIZADOS no processamento)
    df_confra_compradores = df_confra[['email_comprador_padrao', 'data_pedido', 'nome_comprador']].rename(columns={'data_pedido': 'datahora', 'nome_comprador': 'nome'}).copy()
    
    # df_camisas_expanded: data_pedido, nome_comprador (JÁ PADRONIZADOS no processamento)
    df_camisas_compradores = df_camisas_expanded[['email_comprador_padrao', 'data_pedido', 'nome_comprador']].rename(columns={'data_pedido': 'datahora', 'nome_comprador': 'nome'}).copy().drop_duplicates(subset=['email_comprador_padrao', 'datahora'])
    
    # df_festa: datahora (nome vem do split do 'nomes', que é nome_participante)
    df_festa_compradores = df_festa[['email_comprador_padrao', 'datahora', 'nomes']].copy()
    df_festa_compradores['nome'] = standardize_name(df_festa_compradores['nomes'].apply(lambda x: str(x).split(',')[0].strip()))
    df_festa_compradores = df_festa_compradores.drop(columns=['nomes'])
    
    # Consolida TUDO
    df_compradores_consolidado = pd.concat([df_confra_compradores, df_camisas_compradores, df_festa_compradores], ignore_index=True)
    df_compradores_consolidado = df_compradores_consolidado.dropna(subset=['datahora', 'email_comprador_padrao'])
    df_compradores_consolidado = df_compradores_consolidado.rename(columns={'email_comprador_padrao': 'email'})
    
    # Garantir que o nome do comprador seja único por email (usando a última versão do nome)
    df_nomes_unicos = df_compradores_consolidado.drop_duplicates(subset=['email'], keep='last')[['email', 'nome']]


    # -------------------------------------------------------------------------
    # 1. VISUALIZAÇÃO: ARRECADAÇÃO TOTAL POR EVENTO (Barras Agrupadas)
    # -------------------------------------------------------------------------
    st.markdown("### Arrecadação e Participação Consolidadas")
    
    total_arrecadado_camisas = df_camisas_expanded['preco_individual'].sum()
    total_arrecadado_confra = df_confra['valor_pix'].sum()
    total_arrecadado_festa = resultados_festa_kpis[1] 

    df_arrecadacao = pd.DataFrame({
        'Evento': ['Confra', 'Camisas', 'Festa 8 Anos'],
        'Arrecadação (R$)': [total_arrecadado_confra, total_arrecadado_camisas, total_arrecadado_festa]
    })
    
    fig_arrecadacao = px.bar(
        df_arrecadacao, 
        x='Evento', 
        y='Arrecadação (R$)', 
        title='💰 Arrecadação Total por Evento',
        color='Evento',
        color_discrete_sequence=['#4C72B0', '#55A868', '#C44E52']
    )
    st.plotly_chart(fig_arrecadacao, use_container_width=True)

    # -------------------------------------------------------------------------
    # 2. VISUALIZAÇÃO: CRESCIMENTO DE COMPRADORES ATIVOS (Gráfico de Área)
    # -------------------------------------------------------------------------
    st.markdown("#### Crescimento de Compradores Ativos (Email Único)")

    df_crescimento_email = df_compradores_consolidado[['email', 'datahora']].copy()
    
    df_crescimento_email = df_crescimento_email.sort_values('datahora') 
    df_crescimento_email['data_dia'] = df_crescimento_email['datahora'].dt.date
    df_crescimento_email['is_new'] = ~df_crescimento_email['email'].duplicated()
    compras_por_dia = df_crescimento_email.groupby('data_dia')['is_new'].sum().rename('novos_participantes')
    
    compras_cumulativas = compras_por_dia.cumsum().rename('participantes_acumulados').reset_index()
    compras_cumulativas['data_dia'] = pd.to_datetime(compras_cumulativas['data_dia'])

    participantes_ativos_totais = compras_cumulativas['participantes_acumulados'].iloc[-1]
    
    st.metric("👥 Total de Compradores Únicos (Base Ativa)", f"{participantes_ativos_totais}")
    
    fig_email = px.area(
        compras_cumulativas,
        x='data_dia',
        y='participantes_acumulados',
        title='📈 Crescimento Acumulado de Compradores (Baseado em Email Único)',
        labels={'data_dia': 'Data', 'participantes_acumulados': 'Compradores Acumulados'}
    )
    st.plotly_chart(fig_email, use_container_width=True)

    
    # -------------------------------------------------------------------------
    # 3. LISTA COMPLETA DE COMPRADORES (DETALHADA COM CLUSTER)
    # -------------------------------------------------------------------------
    st.markdown("#### Lista Completa de Compradores (Detalhe de Itens e Gasto)")
    
    # --- PREPARAR A BASE COMPLETA (DF_LISTA) ---
    df_gasto_confra = df_confra.groupby('email_comprador_padrao').agg(gasto_confra=('valor_pix', 'sum')).reset_index().rename(columns={'email_comprador_padrao': 'email'})
    df_gasto_camisa = df_camisas_expanded.groupby('email_comprador_padrao').agg(gasto_camisa=('preco_individual', 'sum')).reset_index().rename(columns={'email_comprador_padrao': 'email'})
    df_gasto_festa = df_festa_expanded.groupby('email_comprador_padrao').agg(gasto_festa=('preco_unitario', 'sum')).reset_index().rename(columns={'email_comprador_padrao': 'email'})
    df_lista = pd.merge(df_gasto_confra, df_gasto_camisa, on='email', how='outer').fillna(0)
    df_lista = pd.merge(df_lista, df_gasto_festa, on='email', how='outer').fillna(0)
    
    df_qtd_confra = df_confra.groupby('email_comprador_padrao').agg(qtd_ing_confra=('qtd_confra', 'sum'), qtd_copo_confra=('qtd_copo', 'sum')).reset_index().rename(columns={'email_comprador_padrao': 'email'})
    df_qtd_camisas = df_camisas_expanded.groupby('email_comprador_padrao').agg(qtd_camisa=('tipo_individual', 'size')).reset_index().rename(columns={'email_comprador_padrao': 'email'})
    df_qtd_festa = df_festa_expanded.groupby('email_comprador_padrao').agg(qtd_ing_festa=('quantidade', 'sum')).reset_index().rename(columns={'email_comprador_padrao': 'email'})

    df_lista = pd.merge(df_lista, df_qtd_confra, on='email', how='outer').fillna(0)
    df_lista = pd.merge(df_lista, df_qtd_camisas, on='email', how='outer').fillna(0)
    df_lista = pd.merge(df_lista, df_qtd_festa, on='email', how='outer').fillna(0)

    df_lista['gasto_total'] = df_lista['gasto_confra'] + df_lista['gasto_camisa'] + df_lista['gasto_festa']
    df_lista['qtd_ingressos'] = df_lista['qtd_ing_confra'] + df_lista['qtd_ing_festa']
    df_lista['qtd_copo_total'] = df_lista['qtd_copo_confra']
    df_lista['qtd_camisas'] = df_lista['qtd_camisa']
    df_lista['qtd_total_comprada'] = df_lista['qtd_ingressos'] + df_lista['qtd_copo_total'] + df_lista['qtd_camisas']
    
    df_lista = pd.merge(df_lista, df_nomes_unicos, on='email', how='left')
    
    # --- PREPARAR BASE PARA CLUSTERING (Necessário para obter a coluna 'cluster') ---
    df_clientes_for_cluster = df_lista[['email']].copy()
    
    df_num_compras_confra = df_confra.groupby('email_comprador_padrao').size().reset_index(name='num_compras_confra').rename(columns={'email_comprador_padrao': 'email'})
    df_num_compras_camisas = df_camisas_expanded.drop_duplicates(subset=['id']).groupby('email_comprador_padrao').size().reset_index(name='num_compras_camisas').rename(columns={'email_comprador_padrao': 'email'})
    df_num_compras_festa = df_festa.groupby('email_comprador_padrao').size().reset_index(name='num_compras_festa').rename(columns={'email_comprador_padrao': 'email'})
    
    df_clientes_for_cluster = pd.merge(df_clientes_for_cluster, df_num_compras_confra, on='email', how='left').fillna(0)
    df_clientes_for_cluster = pd.merge(df_clientes_for_cluster, df_num_compras_camisas, on='email', how='left').fillna(0)
    df_clientes_for_cluster = pd.merge(df_clientes_for_cluster, df_num_compras_festa, on='email', how='left').fillna(0)

    df_clientes_for_cluster['gasto_total'] = df_lista['gasto_total']
    df_clientes_for_cluster['qtd_ingressos'] = df_lista['qtd_ingressos']
    df_clientes_for_cluster['qtd_copo_total'] = df_lista['qtd_copo_total']
    df_clientes_for_cluster['qtd_camisas'] = df_lista['qtd_camisas']
    
    features = ['gasto_total', 'qtd_ingressos', 'qtd_copo_total', 'qtd_camisas', 'num_compras_confra', 'num_compras_camisas', 'num_compras_festa']
    X_cluster = df_clientes_for_cluster[features].astype(float) 
    X_cluster = X_cluster[(X_cluster != 0).any(axis=1)].copy() 
    df_clientes_clustered = df_clientes_for_cluster.iloc[X_cluster.index].reset_index(drop=True)
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_cluster)
    K = calculate_optimal_k(X_scaled) 
    kmeans = KMeans(n_clusters=K, random_state=42, n_init=10)
    df_clientes_clustered['cluster'] = 'Cluster ' + kmeans.fit_predict(X_scaled).astype(str)

    # Adicionar o cluster na lista completa (df_lista)
    df_lista = pd.merge(df_lista, df_clientes_clustered[['email', 'cluster']], on='email', how='left').fillna({'cluster': 'Não Class.'})
    
    # Ordenação e Renomeação para exibição
    df_lista = df_lista.sort_values(by='gasto_total', ascending=False).reset_index(drop=True)
    df_lista['Ranking'] = df_lista.index + 1
    
    df_display_compradores = df_lista[[
        'cluster', 'Ranking', 'email', 'nome', 'gasto_total', 'qtd_total_comprada', 
        'qtd_ingressos', 'qtd_copo_total', 'qtd_camisas'
    ]].rename(columns={
        'cluster': 'Cluster',
        'nome': 'Nome Completo',
        'gasto_total': 'Gasto Total (R$)',
        'qtd_total_comprada': 'Qtd. Total',
        'qtd_ingressos': 'Qtd. Ingressos (Confra+Festa)',
        'qtd_copo_total': 'Qtd. Copos',
        'qtd_camisas': 'Qtd. Camisas'
    })
    
    df_display_compradores['Gasto Total (R$)'] = df_display_compradores['Gasto Total (R$)'].apply(lambda x: f"R$ {x:,.2f}".replace(',', 'x').replace('.', ',').replace('x', '.'))

    st.markdown("**Lista de E-mails e Detalhes de Compra**")
    st.dataframe(df_display_compradores.drop(columns=['Nome Completo']), use_container_width=True, hide_index=True)
    
    st.markdown("**Lista de Nomes e Detalhes de Compra**")
    st.dataframe(df_display_compradores.drop(columns=['email']), use_container_width=True, hide_index=True)


    # -------------------------------------------------------------------------
    # 4. MAPA DE CALOR CONSOLIDADO
    # -------------------------------------------------------------------------
    st.markdown("#### 🔥 Mapa de Calor Consolidado: Todos os Eventos (Dia vs. Hora)")
    
    df_confra_mapa = df_confra[['data_pedido']].rename(columns={'data_pedido': 'datahora'}).copy()
    df_camisas_mapa = df_camisas_expanded[['data_pedido']].rename(columns={'data_pedido': 'datahora'}).copy().drop_duplicates() 
    df_festa_mapa = df_festa[['datahora']].copy()
    
    df_eventos_consolidados = pd.concat([df_confra_mapa, df_camisas_mapa, df_festa_mapa], ignore_index=True).dropna(subset=['datahora'])
    
    if df_eventos_consolidados.empty:
        st.warning("Dados de evento insuficientes para o Mapa de Calor Consolidado.")
    else:
        df_eventos_consolidados['dia_semana_pt'] = df_eventos_consolidados['datahora'].dt.day_name().map({
            'Monday': 'Segunda', 'Tuesday': 'Terça', 'Wednesday': 'Quarta', 'Thursday': 'Quinta', 'Friday': 'Sexta', 'Saturday': 'Sábado', 'Sunday': 'Domingo'})
        df_eventos_consolidados['hora'] = df_eventos_consolidados['datahora'].dt.hour
        ordem_dias_pt = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']

        mapa_calor_consolidado = df_eventos_consolidados.groupby(['dia_semana_pt', 'hora']).size().reset_index(name='quantidade')

        fig_heatmap_consolidado = px.density_heatmap(
            mapa_calor_consolidado,
            x="hora",
            y="dia_semana_pt",
            z="quantidade",
            histfunc="sum",
            category_orders={'y': ordem_dias_pt},
            title="Períodos de Pico de Compra (Todos os Eventos)",
            labels={"hora": "Hora do Dia", "dia_semana_pt": "Dia da Semana", "z": "Nº de Pedidos"},
            color_continuous_scale="Reds" 
        )
        st.plotly_chart(fig_heatmap_consolidado, use_container_width=True)
    
    st.markdown("---")
    
    # -------------------------------------------------------------------------
    # 5. ML VISUALIZAÇÃO: SEGMENTAÇÃO DE CLIENTES (Clustering Heatmap)
    # -------------------------------------------------------------------------
    st.markdown("### 📊 Segmentação de Clientes (K-Means - Análise de Perfil)")
    
    if 'cluster' in df_clientes_clustered.columns:
        
        # 3. Visualização (Heatmap de Média por Cluster)
        features_to_show_for_mean = features 
        df_cluster_analysis = df_clientes_clustered.groupby('cluster')[features_to_show_for_mean].mean().reset_index()
        
        feature_mapping = {
            'gasto_total': 'GASTO TOTAL (R$)', 'qtd_ingressos': 'Qtd. Total Ingressos', 
            'qtd_copo_total': 'Qtd. Total Copos', 'qtd_camisas': 'Qtd. Total Camisas',
            'num_compras_confra': 'Pedidos Confra', 'num_compras_camisas': 'Pedidos Camisas',
            'num_compras_festa': 'Pedidos Festa'
        }
        
        df_cluster_analysis.columns = ['cluster'] + [feature_mapping.get(col, col) for col in features_to_show_for_mean]
        
        # Indexar pelo cluster para uso na função interpret_clusters
        df_cluster_analysis_indexed = df_cluster_analysis.set_index('cluster')
        df_heatmap = df_cluster_analysis_indexed.T 
        
        fig_cluster_heatmap = go.Figure(data=go.Heatmap(
            z=df_heatmap.values,
            x=df_heatmap.columns, 
            y=df_heatmap.index,
            colorscale='YlOrRd',
            hovertemplate='Cluster: %{x}<br>Característica: %{y}<br>Média: %{z:.2f}<extra></extra>'
        ))
        
        fig_cluster_heatmap.update_layout(
            title=f"Média das Características por Cluster (K={K})",
            xaxis_title="Cluster",
            yaxis_title="Característica",
            height=400,
            xaxis=dict(tickmode='array', tickvals=list(range(len(df_heatmap.columns))), ticktext=df_heatmap.columns) 
        )
        annotations = []
        for i, cluster_name in enumerate(df_heatmap.columns):
            for j, feature_name in enumerate(df_heatmap.index):
                mean_value = df_heatmap.iloc[j, i]
                annotations.append(dict(
                    x=cluster_name, y=feature_name, text=f'{mean_value:.2f}',
                    showarrow=False, font=dict(color="black" if mean_value < df_heatmap.values.mean() else "white")
                ))
        fig_cluster_heatmap.update_layout(annotations=annotations)


        st.plotly_chart(fig_cluster_heatmap, use_container_width=True)
            
    else:
        st.warning("Não foi possível gerar a segmentação. Verifique se há clientes com transações registradas.")
        
# =========================================================================
# === BLOCO PRINCIPAL DE EXECUÇÃO (Fluxo) =================================
# =========================================================================

# 1. Busca os dados de todas as tabelas
df_confra_bruto = buscar_dados_supabase('compra_confra')
df_camisas_bruto = buscar_dados_supabase('compra_camisas')
df_festa_bruto = buscar_dados_supabase('compra_ingressos')


# 2. Processa os dados
df_festa = pd.DataFrame() 
df_festa_expanded = pd.DataFrame()
resultados_festa_kpis = None
df_ingressos_expanded = pd.DataFrame()
df_copos_expanded = pd.DataFrame()

try:
    # Confra
    (total_ingressos_pagantes, total_criancas_gratis, total_copos, 
     total_arrecadado_pix, df_confra, df_ingressos_expanded, df_copos_expanded) = processar_dados_confra(df_confra_bruto)

    # Camisas
    df_camisas_expanded = processar_dados_camisas(df_camisas_bruto)
    
    # Festa 8 Anos 
    resultados_festa_kpis = processar_dados_festa_8anos(df_festa_bruto)
    
    # Desempacota os resultados para ter o DF padronizado
    if resultados_festa_kpis is not None:
        total_vendido, total_arrecadado, percentual_ocupacao, velocidade_media, df_festa, df_festa_expanded = resultados_festa_kpis
    
except Exception as e:
    st.error(f"❌ ERRO FATAL no Processamento de Dados: {e}")
    st.stop()


# --- TÍTULO GERAL ---
st.title("💰 Painel de Vendas - Chapiuski")
st.markdown("Acompanhamento das vendas da **Confra**, **Camisas** e **Festa 8 Anos**.")
st.divider()


# =========================================================================
# 🛑 CHAMADA DA SEÇÃO DE ANÁLISES AVANÇADAS E CONSOLIDAÇÃO 🛑
# =========================================================================
# Executa e exibe todas as visualizações de ML no topo.
if not (df_confra.empty and df_camisas_expanded is None and df_festa.empty):
    # Passamos os DataFrames para a função, que cuida da consolidação e clustering
    gerar_analises_avancadas(df_confra, df_camisas_expanded, df_festa, resultados_festa_kpis)

st.divider()


# =========================================================================
# === 1. ACOMPANHAMENTO DA CONFRA (KPIS E VISUALIZAÇÕES BÁSICAS) =========
# =========================================================================

st.header("🍻 Vendas da Confra 2025")

if df_confra.empty:
    st.info("Nenhum pedido de Confra encontrado.")
else:
    # EXIBIÇÃO DOS KPIS DA CONFRA
    col_c1, col_c2, col_c3, col_c4 = st.columns(4)
    col_c1.metric("🎫 Ingressos Pagantes", f"{total_ingressos_pagantes}")
    col_c2.metric("👶 Ingressos Gratuitos", f"{total_criancas_gratis}")
    col_c3.metric("🍺 Copos Personalizados", f"{total_copos}")
    col_c4.metric("💰 Arrecadado Total (PIX)", f"R$ {total_arrecadado_pix:,.2f}".replace(',', '.'))
    
    st.markdown("---")
    
    st.subheader("Análise Detalhada da Confra")
    
    # 1. Vendas Acumuladas
    vendas_dia_confra = df_confra.groupby(df_confra['data_pedido'].dt.date)['valor_pix'].sum().reset_index(name='arrecadado_dia')
    vendas_dia_confra['acumulado'] = vendas_dia_confra['arrecadado_dia'].cumsum()
    vendas_dia_confra['data_pedido'] = pd.to_datetime(vendas_dia_confra['data_pedido'])
    
    fig_confra_acumulada = px.line(
        vendas_dia_confra,
        x='data_pedido',
        y='acumulado',
        title="📈 Arrecadação Acumulada da Confra (PIX)",
        labels={'data_pedido': 'Data do Pedido', 'acumulado': 'Arrecadado Total Acumulado (R$)'},
        markers=True
    )
    st.plotly_chart(fig_confra_acumulada, use_container_width=True)

    # 🎯 CORREÇÃO: Resumo Quantitativo em 4 Barras
    
    # 1. Quantidades base
    total_ingressos = total_ingressos_pagantes + total_criancas_gratis
    total_kits_transactions = len(df_confra[(df_confra['qtd_confra'] > 0) & (df_confra['qtd_copo'] > 0)])
    
    df_bar_data = pd.DataFrame({
        'Métrica': ['Qtd. Copos', 'Qtd. Ingressos', 'Qtd. Kits (Pedidos)', 'Qtd. Crianças'],
        'Quantidade': [total_copos, total_ingressos, total_kits_transactions, total_criancas_gratis],
        'Cor': ['Copos', 'Ingressos', 'Kits', 'Crianças'] # Para cores consistentes
    })
    
    # Simple bar chart for the four metrics
    fig_confra_bar = px.bar(
        df_bar_data,
        x='Métrica',
        y='Quantidade',
        color='Cor',
        title='Resumo Quantitativo de Itens da Confra',
        labels={'Métrica': 'Métrica', 'Quantidade': 'Quantidade Total'},
        color_discrete_map={'Copos': '#1f77b4', 'Ingressos': '#55A868', 'Kits': '#C44E52', 'Crianças': '#ff9900'},
        text='Quantidade'
    )
    fig_confra_bar.update_traces(textposition='outside')
    fig_confra_bar.update_layout(xaxis={'categoryorder':'array', 'categoryarray': ['Qtd. Copos', 'Qtd. Ingressos', 'Qtd. Kits (Pedidos)', 'Qtd. Crianças']})

    st.plotly_chart(fig_confra_bar, use_container_width=True)

    # ---------------------------------------------------------------------------------
    
    # --- TABELAS DETALHADAS (LOGÍSTICA) ---
    st.markdown("---")
    st.subheader("Listas Detalhadas para o Evento")
    
    # ⭐️ TABELA 1: DADOS DE INGRESSOS/PARTICIPANTES 
    if not df_ingressos_expanded.empty:
        with st.expander("🎫 LISTA DE PARTICIPANTES (1 linha por Ingresso)"):
            df_ingressos_display = df_ingressos_expanded[[
                'data_pedido', 'nome_comprador', 'nome_participante', 
                'documento_participante', 'e_crianca_flag'
            ]].rename(columns={
                'data_pedido': 'Data Compra',
                'nome_comprador': 'Comprador Resp.',
                'nome_participante': 'Participante',
                'documento_participante': 'Documento',
                'e_crianca_flag': 'É Criança?'
            })
            df_ingressos_display['Data Compra'] = df_ingressos_display['Data Compra'].dt.strftime('%d/%m/%Y %H:%M')
            
            st.dataframe(df_ingressos_display, use_container_width=True, hide_index=True)

    # ⭐️ TABELA 2: DADOS DE COPOS
    if not df_copos_expanded.empty:
        with st.expander("🍺 LISTA DE COPOS PERSONALIZADOS (1 linha por Copo)"):
            df_copos_display = df_copos_expanded[[
                'data_pedido', 'nome_comprador', 'nome_no_copo'
            ]].rename(columns={
                'data_pedido': 'Data Compra',
                'nome_comprador': 'Comprador Resp.',
                'nome_no_copo': 'Nome no Copo'
            })
            df_copos_display['Data Compra'] = df_copos_display['Data Compra'].dt.strftime('%d/%m/%Y %H:%M')
            
            st.dataframe(df_copos_display, use_container_width=True, hide_index=True)
            
    # TABELA 3: DADOS BRUTOS (para referência)
    with st.expander("📄 Ver pedidos de Confra BRUTOS (1 linha por Compra)"):
        df_confra_display = df_confra[[
            'data_pedido', 'nome_comprador', 'email_comprador_padrao', 'qtd_confra', 
            'qtd_copo', 'valor_pix', 'nomes_participantes', 'e_crianca'
        ]].rename(columns={
            'data_pedido': 'Data/Hora',
            'nome_comprador': 'Comprador',
            'email_comprador_padrao': 'Email',
            'qtd_confra': 'Qtd. Ingressos',
            'qtd_copo': 'Qtd. Copos',
            'valor_pix': 'Valor Pago (R$)',
            'nomes_participantes': 'Participantes',
            'e_crianca': 'É Criança?'
        })
        df_confra_display['Data/Hora'] = df_confra_display['Data/Hora'].dt.strftime('%d/%m/%Y %H:%M')
        df_confra_display['Valor Pago (R$)'] = df_confra_display['Valor Pago (R$)'].apply(lambda x: f"R$ {x:,.2f}".replace(',', 'x').replace('.', ',').replace('x', '.'))

        st.dataframe(df_confra_display, use_container_width=True)


st.divider()


# =========================================================================
# === 2. ACOMPANHAMENTO DAS CAMISAS =======================================
# =========================================================================

st.header("👕 Vendas de Camisas 2025")

if df_camisas_expanded is None or df_camisas_expanded.empty:
    st.info("Nenhum pedido de camisa encontrado.")
else:
    # CÁLCULO DOS KPIS DAS CAMISAS
    total_camisas_vendidas = len(df_camisas_expanded)
    total_arrecadado_camisas = df_camisas_expanded['preco_individual'].sum()
    camisas_jogador = len(df_camisas_expanded[df_camisas_expanded['tipo_individual'] == 'Jogador'])
    camisas_torcedor = len(df_camisas_expanded[df_camisas_expanded['tipo_individual'] == 'Torcedor'])

    # EXIBIÇÃO DOS KPIS DAS CAMISAS
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("👕 Total de Camisas Vendidas", f"{total_camisas_vendidas}")
    col2.metric("💰 Total Arrecadado", f"R$ {total_arrecadado_camisas:,.2f}".replace(',', '.'))
    col3.metric("⚽ Camisas de Jogador", f"{camisas_jogador}")
    col4.metric("📣 Camisas de Torcedor", f"{camisas_torcedor}")
    st.markdown("---")

    st.subheader("Análise Detalhada das Camisas")

    col_graf1, col_graf2 = st.columns(2)

    with col_graf1:
        # Gráfico de Pizza: Distribuição por Tipo de Camisa
        df_tipo = df_camisas_expanded['tipo_individual'].value_counts().reset_index(name='count')
        fig_tipo = px.pie(
            df_tipo,
            values='count',
            names='tipo_individual',
            title="📊 Distribuição por Tipo de Camisa",
            color_discrete_map={'Jogador': 'gold', 'Torcedor': 'black'}
        )
        st.plotly_chart(fig_tipo, use_container_width=True)

    with col_graf2:
        # Gráfico de Barras: Vendas por Tamanho
        tamanhos_ordem = ["P", "M", "G", "GG", "G1", "G2", "G3", "G4", "G5"]
        df_tamanho = df_camisas_expanded.groupby(['tamanho_individual', 'tipo_individual']).size().reset_index(name='count')
        fig_tamanho = px.bar(
            df_tamanho,
            x='tamanho_individual',
            y='count',
            color = 'tipo_individual',
            title="📏 Composição de Vendas por Tamanho",
            labels={'tamanho_individual': 'Tamanho', 'count': 'Quantidade Vendida', 'tipo_individual': 'Tipo de Camisa'},
            category_orders={'tamanho_individual': tamanhos_ordem}
        )
        st.plotly_chart(fig_tamanho, use_container_width=True)

    # Grafico da quantidade vendida por número
    st.markdown("---")
    df_numeros = df_camisas_expanded['numero_individual'].value_counts().reset_index(name='count')
    df_numeros = df_numeros[df_numeros['numero_individual'] != '']
    df_numeros['numero_individual'] = pd.to_numeric(df_numeros['numero_individual'], errors='coerce').fillna(0).astype(int)
    df_numeros = df_numeros.sort_values('numero_individual')
    df_numeros = df_numeros[df_numeros['numero_individual'] != 0]
    
    fig_numeros = px.bar(
        df_numeros,
        x = 'numero_individual',
        y = 'count',
        title = '#️⃣ Números Mais Pedidos nas Camisas',
        labels = {'numero_individual': 'Número da Camisa', 'count': 'Quantidade de Pedidos'}
    )
    fig_numeros.update_xaxes(type='category')
    st.plotly_chart(fig_numeros, use_container_width=True)


    # Gráfico de Linha: Vendas Acumuladas ao Longo do Tempo (Camisas)
    vendas_por_dia = df_camisas_expanded.groupby(df_camisas_expanded['data_pedido'].dt.date).size().reset_index(name='quantidade')
    vendas_por_dia['acumulada'] = vendas_por_dia['quantidade'].cumsum()
    vendas_por_dia['data_pedido'] = pd.to_datetime(vendas_por_dia['data_pedido'])

    fig_acumulada = px.line(
        vendas_por_dia,
        x='data_pedido',
        y='acumulada',
        title="📈 Vendas Acumuladas de Camisas ao Longo do Tempo",
        labels={'data_pedido': 'Data do Pedido', 'acumulada': 'Total de Camisas Vendidas'},
        markers=True
    )
    st.plotly_chart(fig_acumulada, use_container_width=True)


    # Heatmap: Vendas por Hora e Dia da Semana (Camisas) - MANTIDO PARA DETALHE DO EVENTO
    df_camisas_expanded['hora'] = df_camisas_expanded['data_pedido'].dt.hour
    
    dias_pt = {
        'Monday': 'Segunda', 'Tuesday': 'Terça', 'Wednesday': 'Quarta', 
        'Thursday': 'Quinta', 'Friday': 'Sexta', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
    }
    ordem_dias_pt = list(dias_pt.values())
    df_camisas_expanded['dia_semana_pt'] = df_camisas_expanded['data_pedido'].dt.day_name().map(dias_pt)

    mapa_calor = df_camisas_expanded.groupby(['dia_semana_pt', 'hora']).size().reset_index(name='quantidade')

    fig_heatmap = px.density_heatmap(
        mapa_calor,
        x="hora",
        y="dia_semana_pt",
        z="quantidade",
        histfunc="sum",
        category_orders={'y': ordem_dias_pt},
        title="🔥 Mapa de Calor - Horários de Pico de Vendas (Camisas)",
        labels={"hora": "Hora do Dia", "dia_semana_pt": "Dia da Semana", "z": "Vendas"},
        color_continuous_scale="Reds"
    )
    st.plotly_chart(fig_heatmap, use_container_width=True)


    # --- TABELA DE DADOS BRUTOS (CAMISAS) ---
    with st.expander("📄 Ver todos os pedidos de Camisas detalhados"):
        df_display = df_camisas_expanded[[
            'data_pedido', 'nome_comprador', 'email_comprador_padrao', 'nome_na_camisa', 'numero_individual',
            'tipo_individual', 'tamanho_individual', 'preco_individual'
        ]].rename(columns={
            'data_pedido': 'Data do Pedido',
            'nome_comprador': 'Nome do Comprador',
            'email_comprador_padrao': 'Email do Comprador',
            'nome_na_camisa': 'Nome na Camisa',
            'numero_individual': 'Número',
            'tipo_individual': 'Tipo',
            'tamanho_individual': 'Tamanho',
            'preco_individual': 'Preço (R$)'
        })
        
        df_display['Data do Pedido'] = df_display['Data do Pedido'].dt.strftime('%d/%m/%Y %H:%M')
        df_display['Preço (R$)'] = df_display['Preço (R$)'].apply(lambda x: f"R$ {x:,.2f}".replace(',', 'x').replace('.', ',').replace('x', '.'))

        st.dataframe(df_display, use_container_width=True)


st.divider()


# =========================================================================
# === 3. ACOMPANHAMENTO FESTA 8 ANOS ======================================
# =========================================================================

st.header("🎟️ Vendas de Ingressos - Festa Chapiuski 8 anos")

if resultados_festa_kpis is None:
    st.info("Nenhum pedido da Festa 8 Anos encontrado na tabela 'compra_ingressos'.")
else:
    # Usa as variáveis desempacotadas
    # (total_vendido, total_arrecadado, percentual_ocupacao, velocidade_media, df_festa, df_festa_expanded)
    
    # 🔝 KPIs no topo
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    col_f1.metric("🎟️ Total Vendido", total_vendido)
    col_f2.metric("📦 Percentual Vendido", f"{percentual_ocupacao:.2f}%")
    col_f3.metric("💰 Total Arrecadado (R$)", f"R$ {total_arrecadado:,.2f}".replace(',', '.'))
    col_f4.metric("🚀 Venda Média por Dia", round(velocidade_media, 2))

    st.markdown("---")
    
    st.subheader("Análise Detalhada da Festa 8 Anos")
    
    # 📅 Gráfico de Venda Acumulada
    venda_por_dia = df_festa_expanded.groupby(df_festa_expanded['datahora'].dt.date).size().reset_index(name='quantidade')
    venda_por_dia['datahora'] = pd.to_datetime(venda_por_dia['datahora'])
    venda_por_dia['acumulada'] = venda_por_dia['quantidade'].cumsum()
    
    fig_acumulada = px.line(
        venda_por_dia,
        x='datahora',
        y='acumulada',
        title="📈 Venda Acumulada de Ingressos",
        labels={'datahora': 'Data', 'acumulada': 'Ingressos Acumulados'},
        markers=True
    )
    st.plotly_chart(fig_acumulada, use_container_width=True)

    # 🔥 Heatmap Hora x Dia da Semana - MANTIDO PARA DETALHE DO EVENTO
    df_festa_expanded['hora'] = df_festa_expanded['datahora'].dt.hour
    
    dias_pt = {
        'Monday': 'Segunda', 'Tuesday': 'Terça', 'Wednesday': 'Quarta', 
        'Thursday': 'Quinta', 'Friday': 'Sexta', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
    }
    ordem_dias_pt = list(dias_pt.values())
    df_festa_expanded['dia_semana_pt'] = df_festa_expanded['datahora'].dt.day_name().map(dias_pt)

    mapa_calor = df_festa_expanded.groupby(['dia_semana_pt', 'hora']).size().reset_index(name='quantidade')
    
    fig_heatmap = px.density_heatmap(
        mapa_calor,
        x="hora",
        y="dia_semana_pt",
        z="quantidade",
        histfunc="sum",
        category_orders={'y': ordem_dias_pt},
        title="🔥 Mapa de Calor - Vendas por Hora e Dia da Semana",
        labels={"hora": "Hora do Dia", "dia_semana_pt": "Dia da Semana", "z": "Vendas"},
        color_continuous_scale="Reds"
    )
    st.plotly_chart(fig_heatmap, use_container_width=True)

    # 📄 Dados brutos (Lista de Presença)
    with st.expander("📄 LISTA DE PRESENÇA (1 linha por Ingresso)"):
        df_display = df_festa_expanded[[
            'datahora', 'email_comprador_padrao', 'nome_participante', 'documento_participante', 'lote', 'preco_unitario'
        ]].rename(columns={
            'datahora': 'Data/Hora Compra',
            'email_comprador_padrao': 'Email Compra',
            'nome_participante': 'Participante',
            'documento_participante': 'Documento',
            'lote': 'Lote',
            'preco_unitario': 'Preço (R$)'
        })
    
        # A coluna 'Comprador Resp.' será o nome do participante (que é o comprador para o primeiro ingresso)
        df_display.insert(2, 'Comprador Resp.', df_display['Participante']) 
        
        df_display['Data/Hora Compra'] = df_display['Data/Hora Compra'].dt.strftime('%d/%m/%Y %H:%M')
        df_display['Preço (R$)'] = df_display['Preço (R$)'].apply(lambda x: f"R$ {x:,.2f}".replace(',', 'x').replace('.', ',').replace('x', '.'))

        st.dataframe(df_display, use_container_width=True, hide_index=True)