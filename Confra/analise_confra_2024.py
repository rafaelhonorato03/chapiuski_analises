import pandas as pd
import matplotlib.pyplot as plt

festa = pd.read_excel('Confra\chapiuski_festa.xlsx')

print(festa)
print(festa['Lote'].value_counts())

# cOnta o número de ingressos por data
festa['Data'] = pd.to_datetime(festa['Data'])
ingressos_por_data = festa['Data'].value_counts().sort_index()
ingressos_cumulativos = ingressos_por_data.cumsum()

# Grafico de linha cumulativo
plt.figure(figsize=(10,5))
plt.plot(ingressos_cumulativos.index, ingressos_cumulativos.values, marker='o', color='royalblue')
plt.xlabel('Data')
plt.ylabel('Número de Ingressos')
plt.title('Número de Ingressos por Data')
plt.xticks(rotation=45)
plt.grid(True, linestyle='--', alpha=0.5)
plt.tight_layout()
plt.show()