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
#df = df[df['Data'].dt.year == 2025]
df['Jogador'] = df['Jogador'].str.strip()  # Padroniza nomes

# Lista de jogadores e posições
jogadores_convocados = [
    'Tuaf', 'Renan', 'Marrone', 'Renato', 'Daniel Rodrigues', 'Felipe', 'Kauan',
    'Dody', 'Allan', 'Hassan', 'Kenneth', 'Dembele', 'Tutão', 'Zanardo', 'Isaías',
    'Joel', 'Léo Leite', 'Biel', 'Marquezini', 'JP', 'Gabriel Andrade', 'Xandinho', 'Kevin', 'Fernando'
]

jogadores_convocados = [j.strip() for j in jogadores_convocados]

jogadores_convocados_posicao = {
    'Tuaf': 'Goleiro', 'Renan': 'Goleiro', 'Marrone': 'Zagueiro', 'Renato': 'Zagueiro',
    'Daniel Rodrigues': 'Zagueiro', 'Felipe': 'Zagueiro', 'Kauan': 'Zagueiro', 'Dody': 'Zagueiro',
    'Allan': 'Zagueiro', 'Hassan': 'Atacante', 'Kenneth': 'Atacante', 'Dembele': 'Atacante',
    'Tutão': 'Atacante', 'Zanardo': 'Atacante', 'Isaías': 'Atacante', 'Joel': 'Atacante',
    'Léo Leite': 'Atacante', 'Biel': 'Meia', 'Marquezini': 'Meia', 'JP': 'Meia',
    'Gabriel Andrade': 'Meia', 'Xandinho': 'Meia', 'Kevin': 'Meia', 'Fernando': 'Meia'
}

# Filtra apenas jogadores convocados
jogadores_convocados_df = df[df['Jogador'].isin(jogadores_convocados)].copy()
jogadores_convocados_df['Semana'] = jogadores_convocados_df['Data'].dt.isocalendar().week

# Lista final de jogadores para garantir presença nas matrizes
todos_jogadores = sorted(jogadores_convocados)

# --- MÉDIA DE GOLS POR JOGO JUNTOS ---
gols_soma = Counter()
gols_semanas = Counter()
for semana, grupo in jogadores_convocados_df.groupby('Semana'):
    jogadores = grupo['Jogador'].unique()
    for par in combinations(sorted(jogadores), 2):
        if all(j in jogadores for j in par):
            soma_gols = grupo[grupo['Jogador'].isin(par)]['Gol'].sum()
            gols_soma[par] += soma_gols
            gols_semanas[par] += 1
media_gols = {par: gols_soma[par]/gols_semanas[par] if gols_semanas[par] > 0 else 0 for par in gols_soma}
matriz_media_gols = pd.DataFrame(0.0, index=todos_jogadores, columns=todos_jogadores)
for (j1, j2), media in media_gols.items():
    matriz_media_gols.loc[j1, j2] = media
    matriz_media_gols.loc[j2, j1] = media

# --- MÉDIA DE ASSISTÊNCIAS POR JOGO JUNTOS ---
assist_soma = Counter()
assist_semanas = Counter()
for semana, grupo in jogadores_convocados_df.groupby('Semana'):
    jogadores = grupo['Jogador'].unique()
    for par in combinations(sorted(jogadores), 2):
        if all(j in jogadores for j in par):
            soma_assist = grupo[grupo['Jogador'].isin(par)]['Assistência'].sum()
            assist_soma[par] += soma_assist
            assist_semanas[par] += 1
media_assist = {par: assist_soma[par]/assist_semanas[par] if assist_semanas[par] > 0 else 0 for par in assist_soma}
matriz_media_assist = pd.DataFrame(0.0, index=todos_jogadores, columns=todos_jogadores)
for (j1, j2), media in media_assist.items():
    matriz_media_assist.loc[j1, j2] = media
    matriz_media_assist.loc[j2, j1] = media

# --- MÉDIA DE VITÓRIAS POR JOGO JUNTOS ---
vitorias_soma = Counter()
vitorias_semanas = Counter()
for semana, grupo in jogadores_convocados_df.groupby('Semana'):
    jogadores = grupo['Jogador'].unique()
    venceu = grupo[grupo['Situação'] == 'Vitória']['Jogador'].unique()
    for par in combinations(sorted(jogadores), 2):
        if all(j in jogadores for j in par):
            vitorias_semanas[par] += 1
            if par[0] in venceu and par[1] in venceu:
                vitorias_soma[par] += 1
media_vitorias = {par: vitorias_soma[par]/vitorias_semanas[par] if vitorias_semanas[par] > 0 else 0 for par in vitorias_soma}
matriz_media_vitorias = pd.DataFrame(0.0, index=todos_jogadores, columns=todos_jogadores)
for (j1, j2), media in media_vitorias.items():
    matriz_media_vitorias.loc[j1, j2] = media
    matriz_media_vitorias.loc[j2, j1] = media

# --- MATRIZES GARANTIDAS COM TODOS OS JOGADORES ---
matriz_media_vitorias = matriz_media_vitorias.reindex(index=todos_jogadores, columns=todos_jogadores, fill_value=0)
matriz_media_gols = matriz_media_gols.reindex(index=todos_jogadores, columns=todos_jogadores, fill_value=0)
matriz_media_assist = matriz_media_assist.reindex(index=todos_jogadores, columns=todos_jogadores, fill_value=0)

# --- GRÁFICOS DE CORRELAÇÃO ---
g = sns.clustermap(matriz_media_vitorias, annot=True, fmt='.2f', cmap='Blues', figsize=(14, 10))
g.fig.suptitle('Vitórias', fontsize=11)
plt.show()

g = sns.clustermap(matriz_media_gols, annot=True, fmt='.2f', cmap='Greens', figsize=(14, 10))
g.fig.suptitle('Gols', fontsize=11)
plt.show()

g = sns.clustermap(matriz_media_assist, annot=True, fmt='.2f', cmap='Purples', figsize=(14, 10))
g.fig.suptitle('Assistências', fontsize=11)
plt.show()

# --- TIME IDEAL POR CORRELAÇÃO ---
formacao = {'Goleiro': 1, 'Zagueiro': 4, 'Meia': 3, 'Atacante': 3}
df_score = pd.DataFrame({
    'Jogador': todos_jogadores,
    'Score': [0]*len(todos_jogadores),  # Score não é usado na montagem por correlação
    'Posição': [jogadores_convocados_posicao[j] for j in todos_jogadores]
})

from itertools import combinations

def score_time(time, matriz_vit, matriz_gol, matriz_assist, pesos=(1,1,1)):
    score = 0
    for j1, j2 in combinations(time, 2):
        score += (
            pesos[0] * matriz_vit.loc[j1, j2] +
            pesos[1] * matriz_gol.loc[j1, j2] +
            pesos[2] * matriz_assist.loc[j1, j2]
        )
    return score

def montar_time_ideal(df_score, formacao, matriz_vit, matriz_gol, matriz_assist, jogadores_excluidos=None):
    time = []
    excluidos = set(jogadores_excluidos) if jogadores_excluidos else set()
    for posicao, qtd in formacao.items():
        disponiveis = df_score[(df_score['Posição'] == posicao) & (~df_score['Jogador'].isin(excluidos))]
        melhores = disponiveis['Jogador'].tolist()
        # Seleção gulosa: adiciona um por vez maximizando o entrosamento
        for _ in range(qtd):
            melhor_jogador = None
            melhor_score = -np.inf
            for jogador in melhores:
                if jogador in time or jogador in excluidos:
                    continue
                teste_time = time + [jogador]
                s = score_time(teste_time, matriz_vit, matriz_gol, matriz_assist)
                if s > melhor_score:
                    melhor_score = s
                    melhor_jogador = jogador
            if melhor_jogador:
                time.append(melhor_jogador)
                melhores.remove(melhor_jogador)
    return time

# Monta o time ideal maximizando o entrosamento por médias
time1 = montar_time_ideal(df_score, formacao, matriz_media_vitorias, matriz_media_gols, matriz_media_assist)
print('\nTime Ideal 1 (máxima correlação por média):')
for jogador in time1:
    print(f"{jogador} - {jogadores_convocados_posicao[jogador]}")

time2 = montar_time_ideal(df_score, formacao, matriz_media_vitorias, matriz_media_gols, matriz_media_assist, jogadores_excluidos=time1)
print('\nTime Ideal 2 (máxima correlação por média):')
for jogador in time2:
    print(f"{jogador} - {jogadores_convocados_posicao[jogador]}")

# --- CLUSTERIZAÇÃO DOS JOGADORES ---
# Exemplo: clusterizar jogadores por média de gols, assistências e vitórias
X = []
for jogador in todos_jogadores:
    gols = matriz_media_gols.loc[jogador].mean()
    assist = matriz_media_assist.loc[jogador].mean()
    vitorias = matriz_media_vitorias.loc[jogador].mean()
    X.append([gols, assist, vitorias])

kmeans = KMeans(n_clusters=3, random_state=0).fit(X)
for jogador, cluster in zip(todos_jogadores, kmeans.labels_):
    print(f"{jogador}: Cluster {cluster}")

# Adiciona o cluster ao DataFrame de jogadores
df_clusters = pd.DataFrame({
    'Jogador': todos_jogadores,
    'Cluster': kmeans.labels_,
    'Posição': [jogadores_convocados_posicao[j] for j in todos_jogadores]
})

# Mostra os jogadores de cada cluster
X_np = np.array(X)
for c in sorted(df_clusters['Cluster'].unique()):
    idx = df_clusters['Cluster'] == c
    print(f"\nCluster {c} - Médias: Gols={X_np[idx,0].mean():.2f}, Assist={X_np[idx,1].mean():.2f}, Vitórias={X_np[idx,2].mean():.2f}")

# Jogadores sozinhos em um cluster
for c in sorted(df_clusters['Cluster'].unique()):
    cluster_jogs = df_clusters[df_clusters['Cluster'] == c]
    if len(cluster_jogs) == 1:
        print(f"\nDestaque absoluto: {cluster_jogs.iloc[0]['Jogador']} (sozinho no Cluster {c})")

# Jogadores com maior média de gols, assistências ou vitórias
X_np = np.array(X)
idx_gol = np.argmax(X_np[:,0])
idx_assist = np.argmax(X_np[:,1])
idx_vit = np.argmax(X_np[:,2])
print(f"\nMaior média de gols: {todos_jogadores[idx_gol]} ({X_np[idx_gol,0]:.2f})")
print(f"Maior média de assistências: {todos_jogadores[idx_assist]} ({X_np[idx_assist,1]:.2f})")
print(f"Maior média de vitórias: {todos_jogadores[idx_vit]} ({X_np[idx_vit,2]:.2f})")

def montar_time_equilibrado(df_clusters, formacao):
    time = []
    usados = set()
    for posicao, qtd in formacao.items():
        pos_jogs = df_clusters[df_clusters['Posição'] == posicao]
        clusters = pos_jogs['Cluster'].unique()
        cluster_cycle = list(clusters) * ((qtd // len(clusters)) + 2)  # +2 para garantir sobra
        i = 0
        while len([j for j in time if df_clusters.set_index('Jogador').loc[j, 'Posição'] == posicao]) < qtd:
            if i >= len(cluster_cycle):
                # Se esgotou os clusters, pega qualquer jogador disponível da posição
                candidatos = pos_jogs[~pos_jogs['Jogador'].isin(usados)]
                if not candidatos.empty:
                    escolhido = candidatos.iloc[0]['Jogador']
                    time.append(escolhido)
                    usados.add(escolhido)
                else:
                    break  # Não há mais jogadores disponíveis para a posição
            else:
                cluster = cluster_cycle[i]
                candidatos = pos_jogs[(pos_jogs['Cluster'] == cluster) & (~pos_jogs['Jogador'].isin(usados))]
                if not candidatos.empty:
                    escolhido = candidatos.iloc[0]['Jogador']
                    time.append(escolhido)
                    usados.add(escolhido)
                i += 1
    return time

# Time Equilibrado 1
time_eq1 = montar_time_equilibrado(df_clusters, formacao)
print('\nTime Equilibrado 1 (por clusters):')
for jogador in time_eq1:
    print(f"{jogador} - {jogadores_convocados_posicao[jogador]} (Cluster {df_clusters.set_index('Jogador').loc[jogador, 'Cluster']})")

# Time Equilibrado 2 (sem repetir jogadores)
time_eq2 = montar_time_equilibrado(df_clusters[~df_clusters['Jogador'].isin(time_eq1)], formacao)
print('\nTime Equilibrado 2 (por clusters):')
for jogador in time_eq2:
    print(f"{jogador} - {jogadores_convocados_posicao[jogador]} (Cluster {df_clusters.set_index('Jogador').loc[jogador, 'Cluster']})")

# --- ANÁLISE TEMPORAL: Evolução das médias por semana ---

import matplotlib.pyplot as plt

# Escolha os jogadores que deseja analisar (exemplo: top 5 em gols)
top_goleadores = jogadores_convocados_df.groupby('Jogador')['Gol'].sum().sort_values(ascending=False).head(5).index.tolist()

# GOLS por semana
plt.figure(figsize=(12, 5))
for jogador in top_goleadores:
    dados = jogadores_convocados_df[jogadores_convocados_df['Jogador'] == jogador].groupby('Semana')['Gol'].mean()
    plt.plot(dados.index, dados.values, marker='o', label=jogador)
plt.title('Evolução da Média de Gols por Semana (Top 5 Goleadores)')
plt.xlabel('Semana')
plt.ylabel('Média de Gols')
plt.legend()
plt.grid(True, linestyle='--', alpha=0.5)
plt.tight_layout()
plt.show()

# ASSISTÊNCIAS por semana
top_assist = jogadores_convocados_df.groupby('Jogador')['Assistência'].sum().sort_values(ascending=False).head(5).index.tolist()
plt.figure(figsize=(12, 5))
for jogador in top_assist:
    dados = jogadores_convocados_df[jogadores_convocados_df['Jogador'] == jogador].groupby('Semana')['Assistência'].mean()
    plt.plot(dados.index, dados.values, marker='o', label=jogador)
plt.title('Evolução da Média de Assistências por Semana (Top 5 Assistentes)')
plt.xlabel('Semana')
plt.ylabel('Média de Assistências')
plt.legend()
plt.grid(True, linestyle='--', alpha=0.5)
plt.tight_layout()
plt.show()

# VITÓRIAS por semana
top_vitorias = jogadores_convocados_df[jogadores_convocados_df['Situação'] == 'Vitória'].groupby('Jogador').size().sort_values(ascending=False).head(5).index.tolist()
plt.figure(figsize=(12, 5))
for jogador in top_vitorias:
    # Marca 1 para vitória, 0 para não vitória
    dados = jogadores_convocados_df[jogadores_convocados_df['Jogador'] == jogador].groupby('Semana').apply(lambda x: (x['Situação'] == 'Vitória').mean())
    plt.plot(dados.index, dados.values, marker='o', label=jogador)
plt.title('Evolução da Proporção de Vitórias por Semana (Top 5 em Vitórias)')
plt.xlabel('Semana')
plt.ylabel('Proporção de Vitórias')
plt.legend()
plt.grid(True, linestyle='--', alpha=0.5)
plt.tight_layout()
plt.show()

# --- ANÁLISE TEMPORAL: Gráficos cumulativos por semana ---

# GOLS cumulativos por semana
plt.figure(figsize=(12, 5))
for jogador in top_goleadores:
    dados = jogadores_convocados_df[jogadores_convocados_df['Jogador'] == jogador].groupby('Semana')['Gol'].sum().cumsum()
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
    dados = jogadores_convocados_df[jogadores_convocados_df['Jogador'] == jogador].groupby('Semana')['Assistência'].sum().cumsum()
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
    dados = jogadores_convocados_df[jogadores_convocados_df['Jogador'] == jogador].groupby('Semana').apply(lambda x: (x['Situação'] == 'Vitória').sum()).cumsum()
    plt.plot(dados.index, dados.values, marker='o', label=jogador)
plt.title('Vitórias Acumuladas por Semana (Top 5 em Vitórias)')
plt.xlabel('Semana')
plt.ylabel('Vitórias Acumuladas')
plt.legend()
plt.grid(True, linestyle='--', alpha=0.5)
plt.tight_layout()
plt.show()

# --- REDE DE ENTROSAMENTO POR VITÓRIAS ---
# Cria o grafo de entrosamento por vitórias
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
weights = [d['weight']*0.2 for (u, v, d) in edges]  # Fator menor para não ficar grosso
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
weights = [d['weight']*0.2 for (u, v, d) in edges]  # Fator menor para assistências
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
participacao = pd.crosstab(jogadores_convocados_df['Jogador'], jogadores_convocados_df['Semana'])
plt.figure(figsize=(16, 8))
sns.heatmap(participacao, cmap='Greens', cbar=False, linewidths=0.5, linecolor='gray')
plt.title('Heatmap de Participação dos Jogadores por Semana')
plt.xlabel('Semana')
plt.ylabel('Jogador')
plt.tight_layout()
plt.show()


