import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from itertools import combinations
from collections import Counter

df = pd.read_excel('Chapiuski Dados.xlsx')
print(df.head())
print(df.columns)
print(df.info())
print(df.describe())
print(df.isnull().sum())

# Listando jogadores únicos
jogadores_unicos = df['Jogador'].unique()
print(f'Jogadores únicos: {jogadores_unicos}')

# Localizar jogador
jogador_filtrado = df[df['Jogador'].str.contains('Fern', case=False, na=False)]
print(f'\nFiltrando jogadores convocados:\n{jogador_filtrado['Jogador'].unique()}')

# Filtrando jogadores convocados para um contra importante
jogadores_convocados = ['Tuaf', 'Renan', 'Marrone', 'Renato',
                        'Daniel Rodrigues', 'Felipe', 'Kauan',
                        'Dody', 'Allan', 'Hassan', 'Kenneth',
                        'Dembele', 'Tutão', 'Zanardo', 'Isaías',
                        'Joel', 'Léo Leite', 'Biel','Marquezini'
                        'JP', 'Gabriel Andrade', 'Xandinho', 'Kevin',
                        'Fernando']

# Base com jogadores convocados
jogadores_convocados = df[df['Jogador'].isin(jogadores_convocados)]
print(f'\nJogadores convocados:\n{jogadores_convocados}')

# Crie a coluna 'Semana' aqui, logo após criar jogadores_convocados
jogadores_convocados.loc[:, 'Semana'] = pd.to_datetime(jogadores_convocados['Data']).dt.isocalendar().week

# Agora sim, filtre as vitórias
vitorias = jogadores_convocados[jogadores_convocados['Situação'] == 'Vitória']

# Jogadore convocados mais frequentes
jogadores_frequentes = jogadores_convocados['Jogador'].value_counts()
print(f'\nJogadores convocados mais frequentes:\n{jogadores_frequentes}')

# Jogadores convocados mais frequentes em gráfico
plt.figure(figsize=(10, 6))
sns.countplot(data=jogadores_convocados, x='Jogador', order=jogadores_frequentes.index)
plt.title('Jogadores convocados mais frequentes')
plt.xticks(rotation=45)
plt.xlabel('Jogador')
plt.ylabel('Frequência')
plt.tight_layout()
plt.show()

# Jogadores convocados com mais gols
gols_jogadores = jogadores_convocados.groupby('Jogador')['Gol'].sum().reset_index()
gols_jogadores = gols_jogadores.sort_values(by='Gol', ascending=False)
print(f'\nJogadores convocados com mais gols:\n{gols_jogadores}')
# Jogadores convocados com mais gols em gráfico
plt.figure(figsize=(10, 6))
sns.barplot(data=gols_jogadores, x='Jogador', y='Gol', palette='viridis')
plt.title('Jogadores convocados com mais gols')
plt.xticks(rotation=45)
plt.xlabel('Jogador')
plt.ylabel('Gols')
plt.tight_layout()
plt.show()

# Jogadores convocados com mais assistências
assistencias_jogadores = jogadores_convocados.groupby('Jogador')['Assistência'].sum().reset_index()
assistencias_jogadores = assistencias_jogadores.sort_values(by='Assistência', ascending=False)
print(f'\nJogadores convocados com mais assistências:\n{assistencias_jogadores}')
# Jogadores convocados com mais assistências em gráfico
plt.figure(figsize=(10, 6))
sns.barplot(data=assistencias_jogadores, x='Jogador', y='Assistência', palette='viridis')
plt.title('Jogadores convocados com mais assistências')
plt.xticks(rotation=45)
plt.xlabel('Jogador')
plt.ylabel('Assistências')
plt.tight_layout()
plt.show()

# Jogadores convocados com mais vitórias
vitorias_jogadores = jogadores_convocados[jogadores_convocados['Situação'] == 'Vitória'].groupby('Jogador').size().reset_index(name='Vitórias')
vitorias_jogadores = vitorias_jogadores.sort_values(by='Vitórias', ascending=False)
print(f'\nJogadores convocados com mais vitórias:\n{vitorias_jogadores}')

# Jogadores convocados com mais vitórias em gráfico
plt.figure(figsize=(10, 6))
sns.barplot(data=vitorias_jogadores, x='Jogador', y='Vitórias', palette='crest')
plt.title('Jogadores convocados com mais vitórias')
plt.xticks(rotation=45)
plt.xlabel('Jogador')
plt.ylabel('Vitórias')
plt.tight_layout()
plt.show()

# Análise de coocorrência de vitórias por semana

# Se houver coluna de data, converter para semana (ajuste o nome da coluna se necessário)
jogadores_convocados['Semana'] = pd.to_datetime(jogadores_convocados['Data']).dt.isocalendar().week

# Filtra apenas vitórias
vitorias = jogadores_convocados[jogadores_convocados['Situação'] == 'Vitória']

# Cria uma matriz de coocorrência
coocorrencia = Counter()

for semana, grupo in vitorias.groupby('Semana'):
    jogadores = grupo['Jogador'].unique()
    for par in combinations(sorted(jogadores), 2):
        coocorrencia[par] += 1

# Converte para DataFrame para visualização
coocorrencia_df = pd.DataFrame(
    [(j1, j2, count) for (j1, j2), count in coocorrencia.items()],
    columns=['Jogador1', 'Jogador2', 'Vitorias_Juntos']
).sort_values(by='Vitorias_Juntos', ascending=False)

print('\nJogadores que mais venceram juntos por semana:')
print(coocorrencia_df.head(20))

# Cria uma matriz de coocorrência para heatmap
matriz_coocorrencia = coocorrencia_df.pivot(index='Jogador1', columns='Jogador2', values='Vitorias_Juntos').fillna(0)

plt.figure(figsize=(14, 10))
sns.heatmap(matriz_coocorrencia, annot=True, fmt='.0f', cmap='Blues')
plt.title('Heatmap de vitórias em conjunto por pares de jogadores')
plt.xlabel('Jogador 2')
plt.ylabel('Jogador 1')
plt.tight_layout()
plt.show()

# Cria uma matriz simétrica para o clustermap
todos_jogadores = sorted(set(coocorrencia_df['Jogador1']).union(coocorrencia_df['Jogador2']))
matriz_simetrica = pd.DataFrame(0, index=todos_jogadores, columns=todos_jogadores)

for _, row in coocorrencia_df.iterrows():
    matriz_simetrica.loc[row['Jogador1'], row['Jogador2']] = row['Vitorias_Juntos']
    matriz_simetrica.loc[row['Jogador2'], row['Jogador1']] = row['Vitorias_Juntos']

# Usa clustermap para agrupar jogadores semelhantes
sns.clustermap(matriz_simetrica, annot=True, fmt='.0f', cmap='Blues', figsize=(14, 10))
plt.title('Heatmap agrupado de vitórias em conjunto por pares de jogadores', pad=100)
plt.xlabel('Jogador')
plt.ylabel('Jogador')
plt.show()

# --- COOCORRÊNCIA DE GOLS JUNTOS ---
coocorrencia_gols = Counter()
for semana, grupo in jogadores_convocados.groupby('Semana'):
    # Só considera jogos com pelo menos 1 gol
    grupo_gols = grupo[grupo['Gol'] > 0]
    jogadores = grupo_gols['Jogador'].unique()
    for par in combinations(sorted(jogadores), 2):
        # Soma os gols feitos pelos dois juntos naquela semana
        gols_juntos = grupo_gols[grupo_gols['Jogador'].isin(par)]['Gol'].sum()
        coocorrencia_gols[par] += gols_juntos

coocorrencia_gols_df = pd.DataFrame(
    [(j1, j2, count) for (j1, j2), count in coocorrencia_gols.items()],
    columns=['Jogador1', 'Jogador2', 'Gols_Juntos']
).sort_values(by='Gols_Juntos', ascending=False)

matriz_gols = pd.DataFrame(0, index=todos_jogadores, columns=todos_jogadores)
for _, row in coocorrencia_gols_df.iterrows():
    matriz_gols.loc[row['Jogador1'], row['Jogador2']] = row['Gols_Juntos']
    matriz_gols.loc[row['Jogador2'], row['Jogador1']] = row['Gols_Juntos']

sns.clustermap(matriz_gols, annot=True, fmt='.0f', cmap='Greens', figsize=(14, 10))
plt.title('Heatmap agrupado de gols feitos em conjunto por pares de jogadores', pad=100)
plt.xlabel('Jogador')
plt.ylabel('Jogador')
plt.show()

# --- COOCORRÊNCIA DE ASSISTÊNCIAS JUNTOS ---
coocorrencia_assist = Counter()
for semana, grupo in jogadores_convocados.groupby('Semana'):
    grupo_assist = grupo[grupo['Assistência'] > 0]
    jogadores = grupo_assist['Jogador'].unique()
    for par in combinations(sorted(jogadores), 2):
        assist_juntos = grupo_assist[grupo_assist['Jogador'].isin(par)]['Assistência'].sum()
        coocorrencia_assist[par] += assist_juntos

coocorrencia_assist_df = pd.DataFrame(
    [(j1, j2, count) for (j1, j2), count in coocorrencia_assist.items()],
    columns=['Jogador1', 'Jogador2', 'Assist_Juntos']
).sort_values(by='Assist_Juntos', ascending=False)

matriz_assist = pd.DataFrame(0, index=todos_jogadores, columns=todos_jogadores)
for _, row in coocorrencia_assist_df.iterrows():
    matriz_assist.loc[row['Jogador1'], row['Jogador2']] = row['Assist_Juntos']
    matriz_assist.loc[row['Jogador2'], row['Jogador1']] = row['Assist_Juntos']

sns.clustermap(matriz_assist, annot=True, fmt='.0f', cmap='Purples', figsize=(14, 10))
plt.title('Heatmap agrupado de assistências em conjunto por pares de jogadores', pad=100)
plt.xlabel('Jogador')
plt.ylabel('Jogador')
plt.show()

# --- COOCORRÊNCIA DE DERROTAS JUNTOS ---
coocorrencia_derrotas = Counter()
for semana, grupo in jogadores_convocados[jogadores_convocados['Situação'] == 'Derrota'].groupby('Semana'):
    jogadores = grupo['Jogador'].unique()
    for par in combinations(sorted(jogadores), 2):
        coocorrencia_derrotas[par] += 1

coocorrencia_derrotas_df = pd.DataFrame(
    [(j1, j2, count) for (j1, j2), count in coocorrencia_derrotas.items()],
    columns=['Jogador1', 'Jogador2', 'Derrotas_Juntos']
).sort_values(by='Derrotas_Juntos', ascending=False)

matriz_derrotas = pd.DataFrame(0, index=todos_jogadores, columns=todos_jogadores)
for _, row in coocorrencia_derrotas_df.iterrows():
    matriz_derrotas.loc[row['Jogador1'], row['Jogador2']] = row['Derrotas_Juntos']
    matriz_derrotas.loc[row['Jogador2'], row['Jogador1']] = row['Derrotas_Juntos']

sns.clustermap(matriz_derrotas, annot=True, fmt='.0f', cmap='Reds', figsize=(14, 10))
plt.title('Heatmap agrupado de derrotas em conjunto por pares de jogadores', pad=100)
plt.xlabel('Jogador')
plt.ylabel('Jogador')
plt.show()


