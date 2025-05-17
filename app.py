import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from math import pi

# Carrega os dados
df = pd.read_excel('Chapiuski Dados.xlsx')
df['Data'] = pd.to_datetime(df['Data'])
df['Semana'] = df['Data'].dt.isocalendar().week
df['Jogador'] = df['Jogador'].str.strip()

# --- PÁGINA INICIAL COM DESTAQUES ---

st.title('Painel Chapiuski - Dados do Campeonato')

# Destaques gerais
total_jogos = df['Semana'].nunique()
total_gols = int(df['Gol'].sum())
total_assist = int(df['Assistência'].sum())
total_vitorias = int((df['Situação'] == 'Vitória').sum())
jogador_mais_frequente = df['Jogador'].value_counts().idxmax()
artilheiro = df.groupby('Jogador')['Gol'].sum().idxmax()
maior_assistente = df.groupby('Jogador')['Assistência'].sum().idxmax()

col1, col2, col3 = st.columns(3)
col1.metric("Total de Jogos (Semanas)", total_jogos)
col2.metric("Total de Gols", total_gols)
col3.metric("Total de Assistências", total_assist)

col4, col5, col6 = st.columns(3)
col4.metric("Total de Vitórias", total_vitorias)
col5.metric("Jogador Mais Frequente", jogador_mais_frequente)
col6.metric("Artilheiro", artilheiro)

col7, _ = st.columns(2)
col7.metric("Maior Assistente", maior_assistente)

st.markdown("""
---
### 📊 Explore os dados usando os filtros abaixo!
- Veja a evolução dos jogadores ao longo do tempo.
- Compare desempenhos, entrosamento e regularidade.
- Descubra destaques, recordes e tendências do campeonato.
---
""")

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

    max_gols_semana = gols_semana.max().max()
    semana_pico = gols_semana.sum(axis=1).idxmax()
    st.info(f"Maior número de gols em uma semana: {max_gols_semana} (Semana {semana_pico})")
else:
    st.warning('Nenhum dado para os filtros selecionados.')

# --- COMPARAÇÃO DE JOGADORES (RADAR) ---
st.header('Comparação de Jogadores')

# Seleção dos jogadores para comparação
jogadores_disp = df['Jogador'].value_counts().index.tolist()
jogador1 = st.selectbox('Jogador 1', jogadores_disp, index=0)
jogador2 = st.selectbox('Jogador 2', jogadores_disp, index=1)

def stats_jogador(jogador, df_filt):
    dados = df_filt[df_filt['Jogador'] == jogador]
    jogos = dados['Semana'].nunique()
    gols = dados['Gol'].sum()
    assist = dados['Assistência'].sum()
    vitorias = (dados['Situação'] == 'Vitória').sum()
    return {
        'Gols': gols,
        'Gols/Jogo': gols / jogos if jogos > 0 else 0,
        'Assistências': assist,
        'Assist/Jogo': assist / jogos if jogos > 0 else 0,
        'Frequência': jogos,
        'Vitórias': vitorias,
        'Vit/Jogo': vitorias / jogos if jogos > 0 else 0
    }

# Use o dataframe filtrado por data!
stats_all = [stats_jogador(j, df_filt) for j in jogadores_disp]
max_stats = {k: max([s[k] for s in stats_all]) if stats_all else 1 for k in stats_all[0].keys()}

# Dados dos jogadores selecionados
stats1 = stats_jogador(jogador1, df_filt)
stats2 = stats_jogador(jogador2, df_filt)

# Normaliza para o radar (pico = melhor do campeonato)
labels = list(stats1.keys())
values1 = [stats1[k]/max_stats[k] if max_stats[k] > 0 else 0 for k in labels]
values2 = [stats2[k]/max_stats[k] if max_stats[k] > 0 else 0 for k in labels]

# Radar plot
angles = [n / float(len(labels)) * 2 * pi for n in range(len(labels))]
values1 += values1[:1]
values2 += values2[:1]
angles += angles[:1]

fig, ax = plt.subplots(figsize=(6,6), subplot_kw=dict(polar=True))
ax.plot(angles, values1, linewidth=2, linestyle='solid', label=jogador1)
ax.fill(angles, values1, alpha=0.25)
ax.plot(angles, values2, linewidth=2, linestyle='solid', label=jogador2)
ax.fill(angles, values2, alpha=0.25)
ax.set_xticks(angles[:-1])
ax.set_xticklabels(labels)
ax.set_yticklabels([])
ax.set_title('Comparativo de Desempenho (Normalizado)')
ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
st.pyplot(fig)

# --- HEATMAP DE PARTICIPAÇÃO POR SEMANA ---

if not df_filt.empty:
    st.subheader('Heatmap de Participação dos Jogadores por Semana')
    # Garante que todos os jogadores e semanas do filtro estejam no heatmap
    semanas = sorted(df_filt['Semana'].unique())
    idx = pd.MultiIndex.from_product([jogadores, semanas], names=['Jogador', 'Semana'])
    participacao = (
        df_filt.groupby(['Jogador', 'Semana']).size()
        .reindex(idx, fill_value=0)
        .unstack()
    )
    fig, ax = plt.subplots(figsize=(10, len(jogadores)*0.5 + 2))
    sns.heatmap(participacao, cmap='Greens', cbar=False, linewidths=0.5, linecolor='gray', ax=ax)
    ax.set_xlabel('Semana')
    ax.set_ylabel('Jogador')
    st.pyplot(fig)