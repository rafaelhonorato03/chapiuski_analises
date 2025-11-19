import os
from dotenv import load_dotenv
from supabase import create_client
import streamlit as st
from datetime import datetime

# ==============================
# 🔧 CONFIG
# ==============================
load_dotenv()
st.set_page_config(page_title="Votação", page_icon="🏆", layout="centered")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("❌ Erro: Variáveis de ambiente do Supabase não carregadas.")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

VOTACAO_TABLE = "compra_ingressos"

# ==============================
# LISTA PARA VOTAR
# ==============================
OPCOES = [
    "Isaías (Bandido)", "Hassan", "Kevin", "JP", "Renato", "Kauan", 
    "Marrone", "Dody", "Kenneth", "Marquezini", "Joel", "Xandinho",
    "Biel", "Tutão", "Dembele", "Rafa Crispim", "Renan Silva", "Renan",
    "Daniel Rodrigues", "Rafa Castilho"
]

# ==============================
# FUNÇÃO PARA SALVAR VOTOS
# ==============================
def salvar_voto(nome, votos):
    data = datetime.now().isoformat()

    payload = [
        {"nome_eleitor": nome, "craque_escolhido": v, "datahora": data}
        for v in votos
    ]

    supabase.table(VOTACAO_TABLE).insert(payload).execute()


# ==============================
# UI
# ==============================
st.title("🏆 Votação Chapiuski - Escolha 3 Craques da Galera")

with st.form("form"):
    nome = st.text_input("Seu nome:")

    votos = st.multiselect(
        "Escolha exatamente 3 jogadores:", 
        OPCOES,
        max_selections=3
    )

    enviado = st.form_submit_button("CONFIRMAR VOTO")

# ==============================
# LÓGICA DE ENVIO
# ==============================
if enviado:
    if not nome.strip():
        st.error("⚠️ Preencha seu nome.")
    elif len(votos) != 3:
        st.error("⚠️ Você deve escolher **exatamente 3 jogadores**.")
    else:
        salvar_voto(nome.strip(), votos)
        st.success("🎉 Voto registrado com sucesso!")
