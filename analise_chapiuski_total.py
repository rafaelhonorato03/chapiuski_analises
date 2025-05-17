import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from itertools import combinations
from collections import Counter
from sklearn.cluster import KMeans
import networkx as nx

# Carrega e filtra dados
df = pd.read_excel('Chapiuski Dados.xlsx')
df['Data'] = pd.to_datetime(df['Data'])
df = df[df['Data'].dt.year == 2025]
df['Jogador'] = df['Jogador'].str.strip()

# Seleciona os 15 jogadores mais frequentes
top_jogadores = df['Jogador'].value_counts().head(15).index.tolist()
df_top = df[df['Jogador'].isin(top_jogadores)].copy()
df_top['Semana'] = df_top['Data'].dt.isocalendar().week

# --- MATRIZES DE MÉDIA POR PAR ---
def matriz_media_scout(df, scout):
    soma = Counter()
    semanas = Counter()
    for semana, grupo in df.groupby('Semana'):
        jogadores = grupo['Jogador'].unique()
        for par in combinations(sorted(jogadores), 2):
            if all(j in jogadores for j in par):
                soma_scout = grupo[grupo['Jogador'].isin(par)][scout].sum()
                soma[par] += soma_scout
                semanas[par] += 1
    media = {par: soma[par]/semanas[par] if semanas[par] > 0 else 0 for par in soma}
    matriz = pd.DataFrame(0.0, index=top_jogadores, columns=top_jogadores)
    for (j1, j2), val in media.items():
        matriz.loc[j1, j2] = val
        matriz.loc[j2, j1] = val
    return matriz, media

matriz_media_gols, media_gols = matriz_media_scout(df_top, 'Gol')
matriz_media_assist, media_assist = matriz_media_scout(df_top, 'Assistência')

# Vitórias é especial: conta 1 se ambos venceram na semana
vitorias_soma = Counter()
vitorias_semanas = Counter()
for semana, grupo in df_top.groupby('Semana'):
    jogadores = grupo['Jogador'].unique()
    venceu = grupo[grupo['Situação'] == 'Vitória']['Jogador'].unique()
    for par in combinations(sorted(jogadores), 2):
        if all(j in jogadores for j in par):
            vitorias_semanas[par] += 1
            if par[0] in venceu and par[1] in venceu:
                vitorias_soma[par] += 1
media_vitorias = {par: vitorias_soma[par]/vitorias_semanas[par] if vitorias_semanas[par] > 0 else 0 for par in vitorias_soma}
matriz_media_vitorias = pd.DataFrame(0.0, index=top_jogadores, columns=top_jogadores)
for (j1, j2), val in media_vitorias.items():
    matriz_media_vitorias.loc[j1, j2] = val
    matriz_media_vitorias.loc[j2, j1] = val

# --- GRÁFICOS DE CORRELAÇÃO (APENAS TOP 15) ---
g = sns.clustermap(matriz_media_vitorias, annot=True, fmt='.2f', cmap='Blues', figsize=(12, 8))
g.fig.suptitle('Vitórias', fontsize=11)
plt.show()

g = sns.clustermap(matriz_media_gols, annot=True, fmt='.2f', cmap='Greens', figsize=(12, 8))
g.fig.suptitle('Gols', fontsize=11)
plt.show()

g = sns.clustermap(matriz_media_assist, annot=True, fmt='.2f', cmap='Purples', figsize=(12, 8))
g.fig.suptitle('Assistências', fontsize=11)
plt.show()

# --- ANÁLISE TEMPORAL: Gráficos cumulativos por semana (TOP 15) ---
# Top 5 em cada scout, mas só entre os top 15 frequentes
top_goleadores = df_top.groupby('Jogador')['Gol'].sum().sort_values(ascending=False).head(5).index.tolist()
top_assist = df_top.groupby('Jogador')['Assistência'].sum().sort_values(ascending=False).head(5).index.tolist()
top_vitorias = df_top[df_top['Situação'] == 'Vitória'].groupby('Jogador').size().sort_values(ascending=False).head(5).index.tolist()

# GOLS cumulativos por semana
plt.figure(figsize=(12, 5))
for jogador in top_goleadores:
    dados = df_top[df_top['Jogador'] == jogador].groupby('Semana')['Gol'].sum().cumsum()
    plt.plot(dados.index, dados.values, marker='o', label=jogador)
plt.title('Gols Acumulados por Semana (Top 5 Goleadores)')
plt.xlabel('Semana')
plt.ylabel('Gols Acumulados')
plt.legend()
plt.grid(True, linestyle='--', alpha=0.5)
plt.tight_layout()
plt.show()

# ASSISTÊNCIAS cumulativas por semana
plt.figure(figsize=(12, 5))
for jogador in top_assist:
    dados = df_top[df_top['Jogador'] == jogador].groupby('Semana')['Assistência'].sum().cumsum()
    plt.plot(dados.index, dados.values, marker='o', label=jogador)
plt.title('Assistências Acumuladas por Semana (Top 5 Assistentes)')
plt.xlabel('Semana')
plt.ylabel('Assistências Acumuladas')
plt.legend()
plt.grid(True, linestyle='--', alpha=0.5)
plt.tight_layout()
plt.show()

# VITÓRIAS cumulativas por semana
plt.figure(figsize=(12, 5))
for jogador in top_vitorias:
    dados = df_top[df_top['Jogador'] == jogador].groupby('Semana').apply(lambda x: (x['Situação'] == 'Vitória').sum()).cumsum()
    plt.plot(dados.index, dados.values, marker='o', label=jogador)
plt.title('Vitórias Acumuladas por Semana (Top 5 em Vitórias)')
plt.xlabel('Semana')
plt.ylabel('Vitórias Acumuladas')
plt.legend()
plt.grid(True, linestyle='--', alpha=0.5)
plt.tight_layout()
plt.show()

# --- REDE DE ENTROSAMENTO POR VITÓRIAS ---
G = nx.Graph()
for (j1, j2), media in media_vitorias.items():
    if media > 0:
        G.add_edge(j1, j2, weight=media)
plt.figure(figsize=(12, 8))
pos = nx.spring_layout(G, seed=42)
edges = G.edges(data=True)
weights = [d['weight']*3 for (u, v, d) in edges]
nx.draw_networkx_nodes(G, pos, node_color='skyblue', node_size=700)
nx.draw_networkx_edges(G, pos, width=weights, alpha=0.7)
nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold')
top_duplas = sorted(edges, key=lambda x: x[2]['weight'], reverse=True)[:5]
for u, v, d in top_duplas:
    nx.draw_networkx_edges(G, pos, edgelist=[(u, v)], width=5, edge_color='red')
plt.title('Rede de Entrosamento por Vitórias')
plt.axis('off')
plt.tight_layout()
plt.show()

# --- REDE DE ENTROSAMENTO POR GOLS ---
G = nx.Graph()
for (j1, j2), media in media_gols.items():
    if media > 0:
        G.add_edge(j1, j2, weight=media)
plt.figure(figsize=(12, 8))
pos = nx.spring_layout(G, seed=42)
edges = G.edges(data=True)
weights = [d['weight']*0.2 for (u, v, d) in edges]
nx.draw_networkx_nodes(G, pos, node_color='lightgreen', node_size=700)
nx.draw_networkx_edges(G, pos, width=weights, alpha=0.7)
nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold')
top_duplas = sorted(edges, key=lambda x: x[2]['weight'], reverse=True)[:5]
for u, v, d in top_duplas:
    nx.draw_networkx_edges(G, pos, edgelist=[(u, v)], width=3, edge_color='red')
plt.title('Rede de Entrosamento por Gols')
plt.axis('off')
plt.tight_layout()
plt.show()

# --- REDE DE ENTROSAMENTO POR ASSISTÊNCIAS ---
G = nx.Graph()
for (j1, j2), media in media_assist.items():
    if media > 0:
        G.add_edge(j1, j2, weight=media)
plt.figure(figsize=(12, 8))
pos = nx.spring_layout(G, seed=42)
edges = G.edges(data=True)
weights = [d['weight']*0.2 for (u, v, d) in edges]
nx.draw_networkx_nodes(G, pos, node_color='violet', node_size=700)
nx.draw_networkx_edges(G, pos, width=weights, alpha=0.7)
nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold')
top_duplas = sorted(edges, key=lambda x: x[2]['weight'], reverse=True)[:5]
for u, v, d in top_duplas:
    nx.draw_networkx_edges(G, pos, edgelist=[(u, v)], width=3, edge_color='red')
plt.title('Rede de Entrosamento por Assistências')
plt.axis('off')
plt.tight_layout()
plt.show()

# --- HEATMAP DE PARTICIPAÇÃO POR SEMANA ---
participacao = pd.crosstab(df_top['Jogador'], df_top['Semana'])
plt.figure(figsize=(16, 8))
sns.heatmap(participacao, cmap='Greens', cbar=False, linewidths=0.5, linecolor='gray')
plt.title('Heatmap de Participação dos Jogadores por Semana')
plt.xlabel('Semana')
plt.ylabel('Jogador')
plt.tight_layout()
plt.show()

# --- ANÁLISE DE SUBSTITUIÇÕES: Impacto de cada jogador nos gols do time ---

resultados = []
for jogador in top_jogadores:
    semanas_com = df_top[df_top['Jogador'] == jogador]['Semana'].unique()
    semanas_sem = [s for s in df_top['Semana'].unique() if s not in semanas_com]

    # Média de gols do time nas semanas em que o jogador jogou
    gols_com = df_top[df_top['Semana'].isin(semanas_com)].groupby('Semana')['Gol'].sum()
    media_gol_com = gols_com.mean() if len(gols_com) > 0 else np.nan

    # Média de gols do time nas semanas em que o jogador NÃO jogou
    gols_sem = df_top[df_top['Semana'].isin(semanas_sem)].groupby('Semana')['Gol'].sum()
    media_gol_sem = gols_sem.mean() if len(gols_sem) > 0 else np.nan

    resultados.append({
        'Jogador': jogador,
        'Gols_com': media_gol_com,
        'Gols_sem': media_gol_sem,
        'Diferença': media_gol_com - media_gol_sem if (media_gol_com is not np.nan and media_gol_sem is not np.nan) else np.nan
    })

df_subs = pd.DataFrame(resultados).sort_values('Diferença', ascending=False)

print("\nImpacto de cada jogador na média de gols do time (com x sem):")
print(df_subs[['Jogador', 'Gols_com', 'Gols_sem', 'Diferença']].to_string(index=False))

# Opcional: gráfico de barras
plt.figure(figsize=(12, 6))
plt.bar(df_subs['Jogador'], df_subs['Diferença'], color='orange')
plt.axhline(0, color='gray', linestyle='--')
plt.ylabel('Diferença na Média de Gols do Time (com - sem)')
plt.title('Impacto de Cada Jogador na Média de Gols do Time')
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()

# --- ANÁLISE DE SUBSTITUIÇÕES: Impacto de cada jogador nas assistências do time ---

resultados_assist = []
for jogador in top_jogadores:
    semanas_com = df_top[df_top['Jogador'] == jogador]['Semana'].unique()
    semanas_sem = [s for s in df_top['Semana'].unique() if s not in semanas_com]

    # Média de assistências do time nas semanas em que o jogador jogou
    assist_com = df_top[df_top['Semana'].isin(semanas_com)].groupby('Semana')['Assistência'].sum()
    media_assist_com = assist_com.mean() if len(assist_com) > 0 else np.nan

    # Média de assistências do time nas semanas em que o jogador NÃO jogou
    assist_sem = df_top[df_top['Semana'].isin(semanas_sem)].groupby('Semana')['Assistência'].sum()
    media_assist_sem = assist_sem.mean() if len(assist_sem) > 0 else np.nan

    resultados_assist.append({
        'Jogador': jogador,
        'Assist_com': media_assist_com,
        'Assist_sem': media_assist_sem,
        'Diferença': media_assist_com - media_assist_sem if (media_assist_com is not np.nan and media_assist_sem is not np.nan) else np.nan
    })

df_subs_assist = pd.DataFrame(resultados_assist).sort_values('Diferença', ascending=False)

print("\nImpacto de cada jogador na média de assistências do time (com x sem):")
print(df_subs_assist[['Jogador', 'Assist_com', 'Assist_sem', 'Diferença']].to_string(index=False))

# Opcional: gráfico de barras
plt.figure(figsize=(12, 6))
plt.bar(df_subs_assist['Jogador'], df_subs_assist['Diferença'], color='purple')
plt.axhline(0, color='gray', linestyle='--')
plt.ylabel('Diferença na Média de Assistências do Time (com - sem)')
plt.title('Impacto de Cada Jogador na Média de Assistências do Time')
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()


