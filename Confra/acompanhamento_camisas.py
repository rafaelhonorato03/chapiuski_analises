import os
from dotenv import load_dotenv
from supabase import create_client, Client
import pandas as pd
import streamlit as st
import plotly.express as px

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    layout="wide",
    page_title="Acompanhamento - Venda de Camisas"
)

# --- CONEXÃO E CARREGAMENTO DE DADOS ---
# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    # Seleciona dados da tabela de camisas, ordenando pelos mais recentes
    response = supabase.table('compra_camisas').select('*').order('created_at', desc=True).execute()
    
    if not response.data:
        st.warning("Nenhum pedido de camisa encontrado na tabela 'compra_camisas'.")
        st.stop()
        
    df = pd.DataFrame(response.data)

except Exception as e:
    st.error("Falha ao conectar ou buscar dados do Supabase.")
    st.error(f"Erro: {e}")
    st.stop()


# --- TÍTULO DO PAINEL ---
st.title("⚽ Acompanhamento - Venda de Camisas 2025")
st.markdown("Painel para visualização em tempo real dos pedidos de camisas da temporada.")


# --- TRATAMENTO E ENRIQUECIMENTO DOS DADOS ---

# 1. Converte a coluna de data para o formato datetime
df['data_pedido'] = pd.to_datetime(df['created_at'])
df['data_pedido'] = df['data_pedido'].dt.tz_convert('America/Sao_Paulo')

# 2. "Explode" o DataFrame: cria uma linha para cada camisa individual comprada
#    Isso é essencial para analisar cada item separadamente.
df_expanded = df.loc[df.index.repeat(df['quantidade'])].reset_index(drop=True)

# 3. Função para separar valores em colunas que contêm múltiplas informações
def split_value(row_value, index):
    """Separa um valor de uma string delimitada por vírgulas com base em um índice."""
    try:
        parts = str(row_value).split(',')
        return parts[index].strip()
    except IndexError:
        # Se houver menos itens que o esperado, retorna o último item disponível
        return parts[-1].strip() if parts else ""

# 4. Cria uma sequência para identificar cada camisa dentro de um mesmo pedido
df_expanded['seq_pedido'] = df_expanded.groupby('id').cumcount()

# 5. Aplica a função split para separar os detalhes de cada camisa
# <<< ALTERAÇÃO 1: CORREÇÃO DA EXTRAÇÃO DOS DETALHES DA CAMISA >>>
# Aponta para a coluna 'detalhes_pedido' e extrai apenas o nome (removendo o tipo entre parênteses)
df_expanded['nome_na_camisa'] = df_expanded.apply(
    lambda x: split_value(x['detalhes_pedido'], x['seq_pedido']).split('(')[0].strip(), 
    axis=1
)
df_expanded['tamanho_individual'] = df_expanded.apply(lambda x: split_value(x['tamanho'], x['seq_pedido']), axis=1)
df_expanded['tipo_individual'] = df_expanded.apply(lambda x: split_value(x['tipo_camisa'], x['seq_pedido']), axis=1)
df_expanded['numero_individual'] = df_expanded.apply(lambda x: split_value(x['numero_camisa'], x['seq_pedido']), axis=1)

# 6. Mapeia o preço para cada tipo de camisa
precos = {'Jogador': 150, 'Torcedor': 115}
df_expanded['preco_individual'] = df_expanded['tipo_individual'].map(precos).fillna(0)


# --- CÁLCULO DOS KPIs (INDICADORES-CHAVE) ---
total_camisas_vendidas = len(df_expanded)
total_arrecadado = df_expanded['preco_individual'].sum()
camisas_jogador = len(df_expanded[df_expanded['tipo_individual'] == 'Jogador'])
camisas_torcedor = len(df_expanded[df_expanded['tipo_individual'] == 'Torcedor'])

# --- EXIBIÇÃO DOS KPIs ---
st.divider()
col1, col2, col3, col4 = st.columns(4)
col1.metric("👕 Total de Camisas Vendidas", f"{total_camisas_vendidas}")
col2.metric("💰 Total Arrecadado", f"R$ {total_arrecadado:,.2f}".replace(',', '.'))
col3.metric("👨‍‍👧‍👦 Camisas de Jogador", f"{camisas_jogador}")
col4.metric("📣 Camisas de Torcedor", f"{camisas_torcedor}")
st.divider()


# --- GRÁFICOS E VISUALIZAÇÕES ---
col_graf1, col_graf2 = st.columns(2)

with col_graf1:
    # Gráfico de Pizza: Distribuição por Tipo de Camisa
    df_tipo = df_expanded['tipo_individual'].value_counts().reset_index()
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
    df_tamanho = df_expanded.groupby(['tamanho_individual', 'tipo_individual']).size().reset_index(name='count')
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
df_numeros = df_expanded['numero_individual'].value_counts().reset_index()
df_numeros = df_numeros[df_numeros['numero_individual'] != '']
df_numeros['numero_individual'] = pd.to_numeric(df_numeros['numero_individual'])
df_numeros = df_numeros.sort_values('numero_individual')

fig_numeros = px.bar(
    df_numeros,
    x = 'numero_individual',
    y = 'count',
    title = '#️⃣ Números Mais Pedidos nas Camisas',
    labels = {'número_individual': 'Número da Camisa', 'count': 'Quantidade de Pedidos'}
)
fig_numeros.update_xaxes(type='category')
st.plotly_chart(fig_numeros, use_container_width=True)


# Gráfico de Linha: Vendas Acumuladas ao Longo do Tempo
vendas_por_dia = df_expanded.groupby(df_expanded['data_pedido'].dt.date).size().reset_index(name='quantidade')
vendas_por_dia['acumulada'] = vendas_por_dia['quantidade'].cumsum()
vendas_por_dia['data_pedido'] = pd.to_datetime(vendas_por_dia['data_pedido'])

fig_acumulada = px.line(
    vendas_por_dia,
    x='data_pedido',
    y='acumulada',
    title="📈 Vendas Acumuladas ao Longo do Tempo",
    labels={'data_pedido': 'Data do Pedido', 'acumulada': 'Total de Camisas Vendidas'},
    markers=True
)
fig_acumulada.update_traces(line=dict(color='royalblue', width=3))
st.plotly_chart(fig_acumulada, use_container_width=True)


# Heatmap: Vendas por Hora e Dia da Semana
df_expanded['hora'] = df_expanded['data_pedido'].dt.hour
df_expanded['dia_semana'] = df_expanded['data_pedido'].dt.day_name()
dias_pt = {
    'Monday': 'Segunda', 'Tuesday': 'Terça', 'Wednesday': 'Quarta', 
    'Thursday': 'Quinta', 'Friday': 'Sexta', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
}
ordem_dias_pt = list(dias_pt.values())
df_expanded['dia_semana_pt'] = df_expanded['dia_semana'].map(dias_pt)

mapa_calor = df_expanded.groupby(['dia_semana_pt', 'hora']).size().reset_index(name='quantidade')

fig_heatmap = px.density_heatmap(
    mapa_calor,
    x="hora",
    y="dia_semana_pt",
    z="quantidade",
    histfunc="sum",
    category_orders={'dia_semana_pt': ordem_dias_pt},
    title="🔥 Mapa de Calor - Horários de Pico de Vendas",
    labels={"hora": "Hora do Dia", "dia_semana_pt": "Dia da Semana", "quantidade": "Vendas"},
    color_continuous_scale="Reds"
)
st.plotly_chart(fig_heatmap, use_container_width=True)


# --- TABELA DE DADOS BRUTOS ---
# <<< ALTERAÇÃO 2: CORREÇÃO DA TABELA FINAL >>>
with st.expander("📄 Ver todos os pedidos detalhados"):
    # Seleciona e renomeia colunas para exibição usando os nomes corretos da tabela
    df_display = df_expanded[[
        'data_pedido', 'nome_comprador', 'email_comprador', 'nome_na_camisa', 'numero_individual',
        'tipo_individual', 'tamanho_individual', 'preco_individual'
    ]].rename(columns={
        'data_pedido': 'Data do Pedido',
        'nome_comprador': 'Nome do Comprador',
        'email_comprador': 'Email do Comprador',
        'nome_na_camisa': 'Nome na Camisa',
        'numero_individual': 'Número',
        'tipo_individual': 'Tipo',
        'tamanho_individual': 'Tamanho',
        'preco_individual': 'Preço (R$)'
    })
    # Remove linhas duplicadas para uma visualização mais limpa
    st.dataframe(df_display, use_container_width=True)