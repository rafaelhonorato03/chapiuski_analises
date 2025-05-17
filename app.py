import streamlit as st
import pandas as pd

# Carrega os dados
df = pd.read_excel('Chapiuski Dados.xlsx')
df['Data'] = pd.to_datetime(df['Data'])
df['Semana'] = df['Data'].dt.isocalendar().week
df['Jogador'] = df['Jogador'].str.strip()

# Filtros interativos
# Ordena jogadores do mais frequente para o menos frequente
freq_jogadores = df['Jogador'].value_counts().index.tolist()
jogadores = st.multiselect('Selecione Jogador(es):', freq_jogadores, default=freq_jogadores[:3])
datas = sorted(df['Data'].dt.date.unique())
data_sel = st.slider(
    'Selecione intervalo de datas:',
    min_value=min(datas),
    max_value=max(datas),
    value=(min(datas), max(datas))
)

df_filt = df[
    (df['Jogador'].isin(jogadores)) &
    (df['Data'].dt.date >= data_sel[0]) &
    (df['Data'].dt.date <= data_sel[1])
]

st.write('Dados filtrados:', df_filt)

# Gráfico de gols acumulados por semana
if not df_filt.empty:
    st.subheader('Gols Acumulados por Semana')
    # Cria MultiIndex com todas as combinações de semana e jogador selecionado
    semanas = sorted(df_filt['Semana'].unique())
    idx = pd.MultiIndex.from_product([semanas, jogadores], names=['Semana', 'Jogador'])
    gols_semana = (
        df_filt.groupby(['Semana', 'Jogador'])['Gol'].sum()
        .reindex(idx, fill_value=0)
        .unstack()
        .cumsum()
    )
    st.line_chart(gols_semana)

    st.subheader('Assistências Acumuladas por Semana')
    assist_semana = (
        df_filt.groupby(['Semana', 'Jogador'])['Assistência'].sum()
        .reindex(idx, fill_value=0)
        .unstack()
        .cumsum()
    )
    st.line_chart(assist_semana)
else:
    st.warning('Nenhum dado para os filtros selecionados.')