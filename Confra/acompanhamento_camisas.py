import os
from dotenv import load_dotenv
from supabase import create_client, Client
import pandas as pd
import streamlit as st
import plotly.express as px
import numpy as np

# Para Machine Learning
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from datetime import timedelta

# --- CONFIGURAÇÃO DA PÁGINA (Padrão/Centered) ---
# O layout="centered" será mantido, mas o painel lateral é removido ao não usarmos st.sidebar
st.set_page_config(
    layout="wide", # Alterado para 'wide' para melhor visualização do conteúdo sem sidebar
    page_title="Painel de Vendas - Chapiuski (Avançado)"
)

# --- CONEXÃO E CARREGAMENTO DE DADOS INICIAIS ---
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error("Falha ao conectar com o Supabase.")
    st.error(f"Erro: {e}")
    st.stop()


# =========================================================================
# === FUNÇÕES DE BUSCA E UTILITY ==========================================
# =========================================================================

# Ajustado para não ter escrita no sidebar
@st.cache_data(ttl=60) 
def buscar_dados_supabase(tabela):
    """Busca dados de uma tabela específica no Supabase, ajustando a ordenação."""
    
    if tabela == 'compra_ingressos':
        coluna_ordenacao = 'datahora'
    else:
        coluna_ordenacao = 'created_at'

    try:
        response = supabase.table(tabela).select('*').order(coluna_ordenacao, desc=True).execute()
        return pd.DataFrame(response.data)
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


# =========================================================================
# === FUNÇÕES DE PROCESSAMENTO: CONFRA (Ajustado) =========================
# =========================================================================

def processar_dados_confra(df_confra):
    """Calcula KPIs e trata a base para a Confra."""
    if df_confra.empty:
        return 0, 0, 0, 0, pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    df = df_confra.copy()
    
    # 🎯 PADRONIZAÇÃO DE COLUNA: email
    if 'email_comprador' in df.columns:
        df = df.rename(columns={'email_comprador': 'email_comprador_padrao'})
    
    # 🎯 TRATAMENTO DE DATA - CORREÇÃO DE TIMEZONE
    df['data_pedido'] = pd.to_datetime(df['created_at'], errors='coerce') 
    # Remove fuso horário existente se for tz-aware
    if df['data_pedido'].dt.tz is not None:
        df['data_pedido'] = df['data_pedido'].dt.tz_convert('UTC').dt.tz_localize(None)
    # Aplica fuso horário UTC (assumindo que os dados brutos são UTC) e converte para SP
    df['data_pedido'] = df['data_pedido'].dt.tz_localize('UTC').dt.tz_convert('America/Sao_Paulo')
    
    # Cálculos de KPI
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
        
        df_ingressos['nome_participante'] = df_ingressos.apply(
            lambda x: split_value(x['nomes_participantes'], x['seq_ingresso']), axis=1
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
            lambda x: split_value(x['nomes_copo'], x['seq_copo']), axis=1
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
    
    # 🎯 PADRONIZAÇÃO DE COLUNA: email
    if 'email_comprador' in df.columns:
        df = df.rename(columns={'email_comprador': 'email_comprador_padrao'})
    
    # 🎯 TRATAMENTO DE DATA - CORREÇÃO DE TIMEZONE
    df['data_pedido'] = pd.to_datetime(df['created_at'], errors='coerce')
    # Remove fuso horário existente se for tz-aware
    if df['data_pedido'].dt.tz is not None:
        df['data_pedido'] = df['data_pedido'].dt.tz_convert('UTC').dt.tz_localize(None)
    # Aplica fuso horário UTC (assumindo que os dados brutos são UTC) e converte para SP
    df['data_pedido'] = df['data_pedido'].dt.tz_localize('UTC').dt.tz_convert('America/Sao_Paulo')

    # Expansão para 1 linha por camisa
    df['quantidade'] = pd.to_numeric(df['quantidade'], errors='coerce').fillna(0).astype(int) # Garantir que é int
    df_expanded = df.loc[df.index.repeat(df['quantidade'])].reset_index(drop=True)
    df_expanded['seq_pedido'] = df_expanded.groupby('id').cumcount()

    # Aplica split para obter detalhes por camisa
    df_expanded['nome_na_camisa'] = df_expanded.apply(
        lambda x: split_value(x['detalhes_pedido'], x['seq_pedido']).split('(')[0].strip(), axis=1
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
    
    # 🎯 PADRONIZAÇÃO DE COLUNA: email (coluna chama-se 'email')
    if 'email' in df.columns:
        df = df.rename(columns={'email': 'email_comprador_padrao'})
    
    # 🎯 TRATAMENTO DE DATA - CORREÇÃO DE TIMEZONE
    df['datahora'] = pd.to_datetime(df['datahora'], errors='coerce')
    # Remove fuso horário existente se for tz-aware
    if df['datahora'].dt.tz is not None:
        df['datahora'] = df['datahora'].dt.tz_convert('UTC').dt.tz_localize(None)
        
    # Aplica fuso horário UTC (assumindo que os dados brutos são UTC) e converte para SP
    df['datahora'] = df['datahora'].dt.tz_localize('UTC').dt.tz_convert('America/Sao_Paulo')
    
    # Expansão para 1 linha por ingresso
    df['quantidade'] = pd.to_numeric(df['quantidade'], errors='coerce').fillna(0).astype(int) # Garantir que é int
    df_expanded = df.loc[df.index.repeat(df['quantidade'])].reset_index(drop=True)
    df_expanded['quantidade'] = 1 
    df_expanded['seq'] = df_expanded.groupby('id').cumcount()

    # Expansão dos participantes
    df_expanded['nome_participante'] = df_expanded.apply(lambda x: split_value(x['nomes'], x['seq']), axis=1)
    df_expanded['documento_participante'] = df_expanded.apply(lambda x: split_value(x['documentos'], x['seq']), axis=1)

    # Mapeamento e cálculo de preço 
    precos = {'1º LOTE PROMOCIONAL': 100, '2º LOTE': 120}
    df_expanded['preco_unitario'] = df_expanded['lote'].map(precos).fillna(0)
    
    # KPIs
    total_vendido = df_expanded.shape[0]
    total_disponivel = 100 # Estoque (Ajuste se o limite for outro)
    percentual_ocupacao = total_vendido / total_disponivel * 100 if total_disponivel else 0
    total_arrecadado = df_expanded['preco_unitario'].sum()

    venda_por_dia = df_expanded.groupby(df_expanded['datahora'].dt.date).size().reset_index(name='quantidade')
    venda_por_dia['quantidade'] = venda_por_dia['quantidade'].astype(int)
    velocidade_media = venda_por_dia['quantidade'].mean()
    
    return total_vendido, total_arrecadado, percentual_ocupacao, velocidade_media, df, df_expanded # <<-- RETORNO COM O DF PADRONIZADO E O EXPANDIDO


# =========================================================================
# === MACHINE LEARNING E ANÁLISES AVANÇADAS (AJUSTADO PARA TODOS) =========
# =========================================================================

def gerar_analises_avancadas(df_confra, df_camisas_expanded, df_festa, resultados_festa_kpis): 
    """Executa todas as análises de ML e visualizações solicitadas com tratamento de erro, 
       considerando Confra, Camisas e Festa 8 Anos."""
    
    # 🎯 ALTERAÇÃO: Título sem a menção 'Machine Learning'
    st.subheader("Análises Avançadas e Consolidação de Vendas")
    st.markdown("---") 

    # 1. Pré-requisitos e Extração de DF expandido da Festa
    if df_confra.empty or df_camisas_expanded is None or df_camisas_expanded.empty or resultados_festa_kpis is None:
        st.warning("Dados insuficientes para executar todas as análises avançadas (Confra, Camisas e Festa).")
        return

    # Extrai o DataFrame expandido da Festa (6º elemento da tupla)
    df_festa_expanded = resultados_festa_kpis[5].copy() 
    
    # -------------------------------------------------------------------------
    # 1. VISUALIZAÇÃO: ARRECADAÇÃO TOTAL POR EVENTO (Barras Agrupadas)
    # -------------------------------------------------------------------------
    st.markdown("### Arrecadação e Participação Consolidadas")
    
    total_arrecadado_camisas = df_camisas_expanded['preco_individual'].sum()
    total_arrecadado_confra = df_confra['valor_pix'].sum()
    total_arrecadado_festa = resultados_festa_kpis[1] # 2º elemento da tupla

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
    st.markdown("#### Crescimento de Compradores Ativos (Únicos)")

    # PREPARAÇÃO DOS DADOS DE COMPRA (PADRÃO)
    df_confra_emails = df_confra[['email_comprador_padrao', 'data_pedido', 'nome_comprador']].rename(columns={'email_comprador_padrao': 'email', 'data_pedido': 'datahora', 'nome_comprador': 'nome'}).copy()
    df_camisas_emails = df_camisas_expanded[['email_comprador_padrao', 'data_pedido', 'nome_comprador']].rename(columns={'email_comprador_padrao': 'email', 'data_pedido': 'datahora', 'nome_comprador': 'nome'}).copy().drop_duplicates(subset=['email', 'datahora'])
    df_festa_emails = df_festa[['email_comprador_padrao', 'datahora', 'nome']].rename(columns={'email_comprador_padrao': 'email'}).copy()
    
    # Consolida os DataFrames
    df_compradores = pd.concat([df_confra_emails, df_camisas_emails, df_festa_emails], ignore_index=True)
    df_compradores = df_compradores.dropna(subset=['datahora', 'email']).drop_duplicates(subset=['email', 'datahora'])

    # Cálculo do Crescimento Acumulado
    df_compradores = df_compradores.sort_values('datahora') 
    df_compradores['data_dia'] = df_compradores['datahora'].dt.date
    df_compradores['is_new'] = ~df_compradores['email'].duplicated()
    compras_por_dia = df_compradores.groupby('data_dia')['is_new'].sum().rename('novos_participantes')
    compras_cumulativas = compras_por_dia.cumsum().rename('participantes_acumulados').reset_index()
    compras_cumulativas['data_dia'] = pd.to_datetime(compras_cumulativas['data_dia'])

    participantes_ativos_totais = compras_cumulativas['participantes_acumulados'].iloc[-1]
    
    st.metric("👥 Total de Compradores Únicos (Base Ativa)", f"{participantes_ativos_totais}")
    
    # 🎯 ALTERAÇÃO: Gráfico de Crescimento Acumulado
    col_cresc1, col_cresc2 = st.columns(2)

    with col_cresc1:
        fig_email = px.area(
            compras_cumulativas,
            x='data_dia',
            y='participantes_acumulados',
            title='📈 Crescimento Acumulado de Compradores (Baseado em Email Único)',
            labels={'data_dia': 'Data', 'participantes_acumulados': 'Compradores Acumulados'}
        )
        st.plotly_chart(fig_email, use_container_width=True)

    with col_cresc2:
        # Replicando a mesma métrica, pois "crescimento por nome" ou "crescimento por email"
        # é a mesma métrica de negócio (cliente único), mas o pedido foi para duas visualizações.
        # Caso o nome completo seja usado como campo único (o que não é comum, mas atende ao pedido)
        df_compradores['is_new_nome'] = ~df_compradores['nome'].duplicated()
        compras_por_dia_nome = df_compradores.groupby('data_dia')['is_new_nome'].sum().rename('novos_participantes_nome')
        compras_cumulativas_nome = compras_por_dia_nome.cumsum().rename('participantes_acumulados_nome').reset_index()
        compras_cumulativas_nome['data_dia'] = pd.to_datetime(compras_cumulativas_nome['data_dia'])
        
        fig_nome = px.area(
            compras_cumulativas_nome,
            x='data_dia',
            y='participantes_acumulados_nome',
            title='📈 Crescimento Acumulado de Compradores (Baseado em Nome Único)',
            labels={'data_dia': 'Data', 'participantes_acumulados_nome': 'Compradores Acumulados'},
            color_discrete_sequence=['#C44E52'] # Cor diferente para diferenciar
        )
        st.plotly_chart(fig_nome, use_container_width=True)
        
    
    # 🎯 ALTERAÇÃO: Lista dos Top 10 Compradores (Email e Nome)
    st.markdown("#### Top 10 Maiores Compradores (Gasto Total Consolidado)")
    
    # Calculando Gasto Total Consolidado
    df_gasto_confra = df_confra.groupby('email_comprador_padrao').agg(
        gasto_confra=('valor_pix', 'sum')
    ).reset_index().rename(columns={'email_comprador_padrao': 'email'})
    
    df_gasto_camisa = df_camisas_expanded.groupby('email_comprador_padrao').agg(
        gasto_camisa=('preco_individual', 'sum')
    ).reset_index().rename(columns={'email_comprador_padrao': 'email'})

    df_gasto_festa = df_festa_expanded.groupby('email_comprador_padrao').agg(
        gasto_festa=('preco_unitario', 'sum')
    ).reset_index().rename(columns={'email_comprador_padrao': 'email'})
    
    df_top_compradores = pd.merge(df_gasto_confra, df_gasto_camisa, on='email', how='outer').fillna(0)
    df_top_compradores = pd.merge(df_top_compradores, df_gasto_festa, on='email', how='outer').fillna(0)
    
    df_top_compradores['gasto_total'] = df_top_compradores['gasto_confra'] + df_top_compradores['gasto_camisa'] + df_top_compradores['gasto_festa']
    
    # Adicionar Nome do Comprador (pegando o nome da última compra, por exemplo)
    df_nomes = df_compradores[['email', 'nome']].drop_duplicates(subset=['email'], keep='last')
    df_top_compradores = pd.merge(df_top_compradores, df_nomes, on='email', how='left')
    
    df_top_compradores = df_top_compradores.sort_values(by='gasto_total', ascending=False).head(10).reset_index(drop=True)
    df_top_compradores['Ranking'] = df_top_compradores.index + 1
    
    col_top1, col_top2 = st.columns(2)
    
    with col_top1:
        st.markdown("**Lista de E-mails dos Top 10**")
        df_email_display = df_top_compradores[['Ranking', 'email', 'gasto_total']].copy()
        df_email_display['gasto_total'] = df_email_display['gasto_total'].apply(lambda x: f"R$ {x:,.2f}".replace(',', 'x').replace('.', ',').replace('x', '.'))
        df_email_display.rename(columns={'email': 'Email', 'gasto_total': 'Gasto Total (R$)'}, inplace=True)
        st.dataframe(df_email_display, use_container_width=True, hide_index=True)
        
    with col_top2:
        st.markdown("**Lista de Nomes dos Top 10**")
        df_nome_display = df_top_compradores[['Ranking', 'nome', 'gasto_total']].copy()
        df_nome_display['gasto_total'] = df_nome_display['gasto_total'].apply(lambda x: f"R$ {x:,.2f}".replace(',', 'x').replace('.', ',').replace('x', '.'))
        df_nome_display.rename(columns={'nome': 'Nome Completo', 'gasto_total': 'Gasto Total (R$)'}, inplace=True)
        st.dataframe(df_nome_display, use_container_width=True, hide_index=True)


    # -------------------------------------------------------------------------
    # 3. VISUALIZAÇÃO: MAPA DE CALOR CONSOLIDADO - TODOS OS EVENTOS (Dia vs. Hora)
    # -------------------------------------------------------------------------
    st.markdown("#### 🔥 Mapa de Calor Consolidado: Todos os Eventos (Dia vs. Hora)")
    
    # Consolidação dos DataFrames para o Heatmap de TODOS os eventos
    
    # 1. Confra: Data e Hora
    df_confra_mapa = df_confra[['data_pedido']].rename(columns={'data_pedido': 'datahora'}).copy()
    
    # 2. Camisas: Data e Hora
    df_camisas_mapa = df_camisas_expanded[['data_pedido']].rename(columns={'data_pedido': 'datahora'}).copy()
    df_camisas_mapa = df_camisas_mapa.drop_duplicates() # 1 linha por pedido, não por item

    # 3. Festa: Data e Hora
    df_festa_mapa = df_festa[['datahora']].copy()
    
    df_eventos_consolidados = pd.concat([df_confra_mapa, df_camisas_mapa, df_festa_mapa], ignore_index=True)
    df_eventos_consolidados = df_eventos_consolidados.dropna(subset=['datahora'])
    
    if df_eventos_consolidados.empty:
        st.warning("Dados de evento insuficientes para o Mapa de Calor Consolidado.")
    else:
        df_eventos_consolidados['dia_semana_pt'] = df_eventos_consolidados['datahora'].dt.day_name().map({
            'Monday': 'Segunda', 'Tuesday': 'Terça', 'Wednesday': 'Quarta', 
            'Thursday': 'Quinta', 'Friday': 'Sexta', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
        })
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
            color_continuous_scale="Viridis"
        )
        st.plotly_chart(fig_heatmap_consolidado, use_container_width=True)
    
    st.markdown("---")
    
    # =====================================================================
    # === VISUALIZAÇÕES DE MACHINE LEARNING ===
    # =====================================================================

    # -------------------------------------------------------------------------
    # 4. ML VISUALIZAÇÃO: SEGMENTAÇÃO DE CLIENTES (Clustering Scatter Plot)
    # -------------------------------------------------------------------------
    # 🎯 ALTERAÇÃO: Sugestão de Heatmap no K-Means
    st.markdown("### 📊 Segmentação de Clientes (K-Means)")
    st.markdown("**(Sugestão atendida):** Mantive o gráfico de dispersão, que é a visualização mais adequada para a clusterização de clientes, mostrando a segmentação com base nos seus gastos e compras.")
    
    try:
        # 1. Feature Engineering (Unindo dados por email padronizado)
        # --- CONFRA FEATURES ---
        df_clientes = df_confra.groupby('email_comprador_padrao').agg(
            valor_pix_total=('valor_pix', 'sum'),
            qtd_copo_total=('qtd_copo', 'sum'),
            num_compras_confra=('email_comprador_padrao', 'size')
        ).reset_index().rename(columns={'email_comprador_padrao': 'email'})

        # --- CAMISAS FEATURES ---
        df_camisas_agg = df_camisas_expanded.groupby('email_comprador_padrao').agg(
            comprou_camisa=('email_comprador_padrao', 'size'),
            qtd_camisas=('preco_individual', 'size'),
            valor_camisas_total=('preco_individual', 'sum') 
        ).reset_index().rename(columns={'email_comprador_padrao': 'email'})

        # --- FESTA FEATURES (NOVO) ---
        df_festa_agg = df_festa_expanded.groupby('email_comprador_padrao').agg(
            qtd_ingressos_festa=('quantidade', 'sum'), 
            valor_festa_total=('preco_unitario', 'sum'),
            num_compras_festa=('email_comprador_padrao', 'size') # Usando size no expanded (1 linha por ingresso)
        ).reset_index().rename(columns={'email_comprador_padrao': 'email'})
        
        # Merge all
        df_clientes = pd.merge(df_clientes, df_camisas_agg, on='email', how='outer').fillna(0)
        df_clientes = pd.merge(df_clientes, df_festa_agg, on='email', how='outer').fillna(0)
        
        # 2. Escalonamento e K-Means
        features = [
            'valor_pix_total', 'qtd_copo_total', 'num_compras_confra', 
            'comprou_camisa', 'qtd_camisas', 'valor_camisas_total',
            'qtd_ingressos_festa', 'valor_festa_total'
        ]
        
        features = [f for f in features if f in df_clientes.columns]
        
        X_cluster = df_clientes[features].astype(float) 
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_cluster)

        K = 3
        kmeans = KMeans(n_clusters=K, random_state=42, n_init=10)
        df_clientes['cluster'] = kmeans.fit_predict(X_scaled)
        df_clientes['cluster'] = df_clientes['cluster'].astype(str)

        # 3. Visualização (Usando Gasto Total Geral)
        df_clientes['gasto_total_geral'] = df_clientes['valor_pix_total'] + df_clientes['valor_camisas_total'] + df_clientes['valor_festa_total']

        fig_cluster = px.scatter(
            df_clientes,
            x='gasto_total_geral',
            y='qtd_copo_total',
            color='cluster',
            size='qtd_camisas', 
            hover_data=['email', 'num_compras_confra', 'qtd_ingressos_festa'],
            title=f'Clusters de Clientes (K={K}): Gasto Total Geral vs. Compra de Copos',
            labels={'gasto_total_geral': 'Gasto Total Geral (R$)', 'qtd_copo_total': 'Total de Copos Comprados'}
        )
        st.plotly_chart(fig_cluster, use_container_width=True)
    except Exception as e:
        st.error(f"❌ Erro no Clustering (K-Means): {e}. Verifique as colunas de dados numéricos consolidados.")

    # -------------------------------------------------------------------------
    # 5. ML VISUALIZAÇÃO: OTIMIZAÇÃO DE LOTES (Regressão Plot)
    # -------------------------------------------------------------------------
    # 🎯 ALTERAÇÃO: REMOVIDA A SEÇÃO DE OTIMIZAÇÃO DE LOTES
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # 6. ML VISUALIZAÇÃO: ANÁLISE DE CESTA DE COMPRAS (Regras de Associação)
    # -------------------------------------------------------------------------
    # 🎯 ALTERAÇÃO: REMOVIDA A SEÇÃO DE ANÁLISE DE CESTA DE COMPRAS
    # -------------------------------------------------------------------------

# =========================================================================
# === BLOCO PRINCIPAL DE EXECUÇÃO (Fluxo) =================================
# =========================================================================

# 1. Busca os dados de todas as tabelas
# 🎯 ALTERAÇÃO: Removido o código de escrita no st.sidebar
df_confra_bruto = buscar_dados_supabase('compra_confra')
df_camisas_bruto = buscar_dados_supabase('compra_camisas')
df_festa_bruto = buscar_dados_supabase('compra_ingressos')


# 2. Processa os dados
try:
    # Confra
    (total_ingressos_pagantes, total_criancas_gratis, total_copos, 
     total_arrecadado_pix, df_confra, df_ingressos_expanded, df_copos_expanded) = processar_dados_confra(df_confra_bruto)

    # Camisas
    df_camisas_expanded = processar_dados_camisas(df_camisas_bruto)
    
    # Festa 8 Anos - CORRIGIDO PARA RETORNAR DF PADRONIZADO E EXPANDIDO
    resultados_festa_kpis = processar_dados_festa_8anos(df_festa_bruto)
    
    # Desempacota os resultados para ter o DF padronizado
    if resultados_festa_kpis is not None:
        total_vendido, total_arrecadado, percentual_ocupacao, velocidade_media, df_festa, df_festa_expanded = resultados_festa_kpis
    else:
        df_festa = pd.DataFrame() 
        df_festa_expanded = pd.DataFrame()
        resultados_festa_kpis = None

except Exception as e:
    st.error(f"❌ ERRO FATAL no Processamento de Dados: {e}")
    st.stop()


# --- TÍTULO GERAL ---
# 🎯 ALTERAÇÃO: Remoção da menção a 'Painel de Vendas - Chapiuski (Avançado)' 
# no título principal, mantendo apenas 'Painel de Vendas - Chapiuski'
st.title("💰 Painel de Vendas - Chapiuski")
st.markdown("Acompanhamento das vendas da **Confra**, **Camisas** e **Festa 8 Anos**.")
st.divider()


# =========================================================================
# 🛑 CHAMADA DA SEÇÃO DE ANÁLISES AVANÇADAS E CONSOLIDAÇÃO 🛑
# =========================================================================

# Esta chamada executa e exibe todas as visualizações de ML no topo, agora consolidadas.
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

    col_g_confra1, col_g_confra2 = st.columns(2)
    
    with col_g_confra1:
        # 2. Distribuição de Ingressos (PAGANTES VS. GRATUITOS)
        df_pagantes = pd.DataFrame({
            'Tipo': ['Pagantes', 'Gratuitos (Crianças)'],
            'Quantidade': [total_ingressos_pagantes, total_criancas_gratis]
        })
        
        fig_distrib_ingr = px.pie(
            df_pagantes,
            values='Quantidade',
            names='Tipo',
            title="🍰 Distribuição de Ingressos (Pagantes vs. Gratuitos)",
            color_discrete_map={'Pagantes': 'royalblue', 'Gratuitos (Crianças)': 'lightgray'}
        )
        st.plotly_chart(fig_distrib_ingr, use_container_width=True)

    with col_g_confra2:
        # 3. Distribuição de QTD de Itens por Pedido
        df_qtd = df_confra.groupby(['qtd_confra', 'qtd_copo']).size().reset_index(name='count')
        df_qtd['Combinação'] = df_qtd.apply(lambda row: f"{row['qtd_confra']} Ingr. + {row['qtd_copo']} Copos", axis=1)

        fig_comb = px.bar(
            df_qtd,
            x='Combinação',
            y='count',
            title="📊 Combinações de Itens Mais Compradas",
            labels={'Combinação': 'Combinação Qtd. Ingresso + Qtd. Copo', 'count': 'Total de Pedidos'}
        )
        st.plotly_chart(fig_comb, use_container_width=True)


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
    
    # 🎯 ALTERAÇÃO: O Heatmap específico da Confra foi movido para o bloco de análise avançada (item 3)
    # e agora é um heatmap consolidado de TODOS os eventos.
    # O bloco original foi removido, mas para referência, o heatmap específico da confra seria:
    # st.markdown("#### Mapa de Calor: Vendas Confra (Dia vs. Hora)")
    # (Código original removido para atender a sua solicitação)


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
    
        df_display.insert(2, 'Comprador Resp.', df_display['Email Compra'])
        df_display = df_display.drop(columns=['Email Compra'])
        
        df_display['Data/Hora Compra'] = df_display['Data/Hora Compra'].dt.strftime('%d/%m/%Y %H:%M')
        df_display['Preço (R$)'] = df_display['Preço (R$)'].apply(lambda x: f"R$ {x:,.2f}".replace(',', 'x').replace('.', ',').replace('x', '.'))

        st.dataframe(df_display, use_container_width=True, hide_index=True)