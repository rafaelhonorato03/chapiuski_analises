import os
from dotenv import load_dotenv
from supabase import create_client, Client
import pandas as pd
import streamlit as st
import plotly.express as px

# 🔑 Carregar variáveis de ambiente
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Acompanhamento de Ingressos")

st.title("🎟️ Acompanhamento de Ingressos - Festa Chapiuski 8 anos")

# 📦 Carregar dados
data = supabase.table('compra_ingressos').select('*').execute()

if data.data:
    df = pd.DataFrame(data.data)

    # 🧹 Tratamento dos dados
    df['datahora'] = pd.to_datetime(df['datahora'])
    df['email'] = df['email'].str.lower()

    df_expanded = df.loc[df.index.repeat(df['quantidade'])].reset_index(drop=True)
    df_expanded['quantidade'] = 1

    def split_value(val, idx):
        parts = str(val).split(',')
        return parts[idx].strip() if idx < len(parts) else parts[-1].strip()

    df_expanded['seq'] = df_expanded.groupby('id').cumcount()
    df_expanded['nomes'] = df_expanded.apply(lambda x: split_value(x['nomes'], x['seq']), axis=1)
    df_expanded['documentos'] = df_expanded.apply(lambda x: split_value(x['documentos'], x['seq']), axis=1)

    precos = {'1º LOTE PROMOCIONAL': 100, '2º LOTE': 120}
    df_expanded['preco'] = df_expanded['lote'].map(precos)

    # 📊 KPIs
    total_vendido = df_expanded.shape[0]
    total_disponivel = 100
    percentual_ocupacao = total_vendido / total_disponivel * 100 if total_disponivel else 0
    total_arrecadado = df_expanded['preco'].sum()

    # 📅 Venda por dia
    venda_por_dia = df_expanded.groupby(df_expanded['datahora'].dt.date).size().reset_index(name='quantidade')
    venda_por_dia['datahora'] = pd.to_datetime(venda_por_dia['datahora'])
    venda_por_dia['acumulada'] = venda_por_dia['quantidade'].cumsum()

    velocidade_media = venda_por_dia['quantidade'].mean()

    # 🔥 Heatmaps
    df_expanded['hora'] = df_expanded['datahora'].dt.hour
    df_expanded['dia_semana'] = df_expanded['datahora'].dt.day_name()

    dias_ordem = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    df_expanded['dia_semana'] = pd.Categorical(df_expanded['dia_semana'], categories=dias_ordem, ordered=True)

    mapa_calor = df_expanded.groupby(['dia_semana', 'hora']).size().reset_index(name='quantidade')

    # 🔝 KPIs no topo
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🎟️ Total Vendido", total_vendido)
    col2.metric("📦 Percentual Vendido", f"{percentual_ocupacao:.2f}%")
    col3.metric("💰 Total Arrecadado (R$)", f"R$ {total_arrecadado}")
    col4.metric("🚀 Venda Média por Dia", round(velocidade_media, 2))

    # 📅 Venda por dia (real)
    fig_diaria_real = px.bar(venda_por_dia, x='datahora', y='quantidade',
                             title="📅 Vendas por Dia",
                             labels={'datahora': 'Data', 'quantidade': 'Quantidade'})
    st.plotly_chart(fig_diaria_real, use_container_width=True)

    # 📈 Venda acumulada real
    fig_acumulada = px.line(
        venda_por_dia,
        x='datahora',
        y='acumulada',
        title="📈 Venda Acumulada Real",
        labels={'datahora': 'Data', 'acumulada': 'Ingressos Acumulados'}
    )
    st.plotly_chart(fig_acumulada, use_container_width=True)

    # 🔥 Heatmap Hora x Dia da Semana
    fig_heatmap = px.density_heatmap(
        mapa_calor,
        x="hora",
        y="dia_semana",
        z="quantidade",
        histfunc="sum",
        nbinsx=24,
        title="🔥 Mapa de Calor - Vendas por Hora e Dia da Semana",
        labels={"hora": "Hora do Dia", "dia_semana": "Dia da Semana", "quantidade": "Vendas"},
        color_continuous_scale="Reds"
    )
    st.plotly_chart(fig_heatmap, use_container_width=True)

    # 📄 Dados brutos
    with st.expander("📄 Ver Dados"):
        st.dataframe(df_expanded)

else:
    st.warning("Nenhum dado encontrado na tabela.")