import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import networkx as nx

from math import pi
from collections import Counter
from itertools import combinations

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
st.markdown("## 🆚 Comparação Direta (Radar)")
st.markdown("Compare dois jogadores em gols, assistências, frequência e vitórias. O valor máximo de cada scout é o pico do radar.")

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

# --- REDES DE ENTROSAMENTO ---
st.markdown("## 🔗 Redes de Entrosamento")
st.markdown("Visualize as duplas mais conectadas em gols, assistências e vitórias. As arestas mais grossas indicam maior entrosamento.")

def plot_rede(media_dict, scout_nome, color, width_factor=1.0):
    G = nx.Graph()
    for (j1, j2), val in media_dict.items():
        if val > 0 and j1 in jogadores and j2 in jogadores:
            G.add_edge(j1, j2, weight=val)
    if len(G.edges) == 0:
        st.info(f"Nenhuma dupla com {scout_nome} no período/seleção atual.")
        return
    pos = nx.spring_layout(G, seed=42)
    edges = G.edges(data=True)
    weights = [d['weight']*width_factor for (u, v, d) in edges]
    fig, ax = plt.subplots(figsize=(8, 6))
    nx.draw_networkx_nodes(G, pos, node_color=color, node_size=700, ax=ax)
    nx.draw_networkx_edges(G, pos, width=weights, alpha=0.7, ax=ax)
    nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold', ax=ax)
    top_duplas = sorted(edges, key=lambda x: x[2]['weight'], reverse=True)[:5]
    for u, v, d in top_duplas:
        nx.draw_networkx_edges(G, pos, edgelist=[(u, v)], width=5, edge_color='red', ax=ax)
    ax.set_title(f'Rede de Entrosamento por {scout_nome}')
    ax.axis('off')
    st.pyplot(fig)

# Calcula médias por dupla no filtro atual
def media_por_dupla(df_filt, scout):
    soma = Counter()
    semanas = Counter()
    for semana, grupo in df_filt.groupby('Semana'):
        jogs = grupo['Jogador'].unique()
        for par in combinations(sorted(jogs), 2):
            soma[par] += grupo[grupo['Jogador'].isin(par)][scout].sum()
            semanas[par] += 1
    return {par: soma[par]/semanas[par] if semanas[par]>0 else 0 for par in soma}

media_gols = media_por_dupla(df_filt, 'Gol')
media_assist = media_por_dupla(df_filt, 'Assistência')
# Vitórias: conta 1 se ambos venceram na semana
def media_vitorias_dupla(df_filt):
    soma = Counter()
    semanas = Counter()
    for semana, grupo in df_filt.groupby('Semana'):
        jogs = grupo['Jogador'].unique()
        venceu = grupo[grupo['Situação'] == 'Vitória']['Jogador'].unique()
        for par in combinations(sorted(jogs), 2):
            semanas[par] += 1
            if par[0] in venceu and par[1] in venceu:
                soma[par] += 1
    return {par: soma[par]/semanas[par] if semanas[par]>0 else 0 for par in soma}
media_vit = media_vitorias_dupla(df_filt)

plot_rede(media_gols, "Gols", "lightgreen", width_factor=2)
plot_rede(media_assist, "Assistências", "violet", width_factor=3)
plot_rede(media_vit, "Vitórias", "skyblue", width_factor=6)

# --- ANÁLISE DE SUBSTITUIÇÃO ---
st.markdown("## 🔄 Análise de Substituição")
st.markdown("Veja o impacto da presença/ausência de cada jogador na média de gols do time no período filtrado.")

resultados = []
for jogador in jogadores:
    semanas_com = df_filt[df_filt['Jogador'] == jogador]['Semana'].unique()
    semanas_sem = [s for s in df_filt['Semana'].unique() if s not in semanas_com]
    gols_com = df_filt[df_filt['Semana'].isin(semanas_com)].groupby('Semana')['Gol'].sum()
    media_gol_com = gols_com.mean() if len(gols_com) > 0 else np.nan
    gols_sem = df_filt[df_filt['Semana'].isin(semanas_sem)].groupby('Semana')['Gol'].sum()
    media_gol_sem = gols_sem.mean() if len(gols_sem) > 0 else np.nan
    resultados.append({
        'Jogador': jogador,
        'Gols_com': media_gol_com,
        'Gols_sem': media_gol_sem,
        'Diferença': media_gol_com - media_gol_sem if (media_gol_com is not np.nan and media_gol_sem is not np.nan) else np.nan
    })
df_subs = pd.DataFrame(resultados).sort_values('Diferença', ascending=False)
st.dataframe(df_subs[['Jogador', 'Gols_com', 'Gols_sem', 'Diferença']].round(2), use_container_width=True)
fig, ax = plt.subplots(figsize=(10, 4))
ax.bar(df_subs['Jogador'], df_subs['Diferença'], color='orange')
ax.axhline(0, color='gray', linestyle='--')
ax.set_ylabel('Diferença na Média de Gols (com - sem)')
ax.set_title('Impacto de Cada Jogador na Média de Gols do Time')
plt.xticks(rotation=45)
st.pyplot(fig)

# --- DETECÇÃO DE OUTLIERS ---
st.markdown("## 🚨 Detecção de Outliers")
st.markdown("Jogadores que destoam do grupo em gols e assistências (acima do limite superior do IQR).")

# Gols
gols_total = df_filt.groupby('Jogador')['Gol'].sum()
q1, q3 = gols_total.quantile([0.25, 0.75])
iqr = q3 - q1
limite_sup = q3 + 1.5 * iqr
outliers_gol = gols_total[gols_total > limite_sup]

# Assistências
assist_total = df_filt.groupby('Jogador')['Assistência'].sum()
q1a, q3a = assist_total.quantile([0.25, 0.75])
iqra = q3a - q1a
limite_supa = q3a + 1.5 * iqra
outliers_assist = assist_total[assist_total > limite_supa]

st.markdown(f"**Outliers em gols:** {', '.join(outliers_gol.index)}")
st.markdown(f"**Outliers em assistências:** {', '.join(outliers_assist.index)}")