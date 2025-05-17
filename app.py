import streamlit as st
import pandas as pd

# Carrega os dados
df = pd.read_excel('Chapiuski Dados.xlsx')
df['Data'] = pd.to_datetime(df['Data'])
df['Semana'] = df['Data'].dt.isocalendar().week
df['Jogador'] = df['Jogador'].str.strip()

# Filtros interativos
todos_jogadores = sorted(df['Jogador'].unique())
jogadores = st.multiselect('Selecione Jogador(es):', todos_jogadores, default=todos_jogadores[:3])
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
    gols_semana = (
        df_filt.groupby(['Semana', 'Jogador'])['Gol'].sum()
        .groupby(level=1).cumsum()
        .unstack()
        .fillna(0)
    )
    st.line_chart(gols_semana)

    st.subheader('Assistências por Semana')
    assist_semana = df_filt.groupby(['Semana', 'Jogador'])['Assistência'].sum().unstack().fillna(0)
    st.line_chart(assist_semana)
else:
    st.warning('Nenhum dado para os filtros selecionados.')