import os
from dotenv import load_dotenv
from supabase import create_client, Client
import pandas as pd
import streamlit as st
import plotly.express as px

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Acompanhamento de Ingressos", layout = "wide")

st.title("🎟️Acompanhamento de Ingressos Festa Chapiuski 8 anos")

data = supabase.table('compra_ingressos').select('*').execute()

if data.data:
    df = pd.DataFrame(data.data)

    st.subheader("Prévia dos dados")
    st.dataframe(df)

    df['datahora'] = pd.to_datetime(df['datahora'])

    ingresso_por_data = df.groupby(df['datahora'].dt.date).size().reset_index(name='quantidade')

    fig = px.bar(ingresso_por_data,
                 x = 'datahora',
                 y = 'quantidade',
                 title = 'Ingressos vendidos por data',
                 labels = {'datahora': 'Data',
                 'quantidade': 'Quantidade de Ingressos'},
                 text_auto = True)
    
    st.plotly_chart(fig, use_container_width = True)

    st.subheader("Detalhes por data")
    st.dataframe(ingresso_por_data)

else:
    st.warning("Nenhum dado encontrado na tabela.")
    
