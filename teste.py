import pandas as pd

url = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vQqKawlrhvZxCUepOzcl4jG9ejActoqNd11Hs6hDverwxV0gv9PRYjwVxs6coMWsoopfH41EuSLRN-v/pub?gid=0&single=true&output=csv'

df = pd.read_csv(url)

print(df)