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

# A tabela será usada para armazenar os votos
VOTACAO_TABLE = "compra_ingressos"

# ==============================
# UI - CONTEÚDO SUPERIOR
# ==============================
# Inserção da imagem craque.jpg (assumindo que o arquivo está no mesmo diretório ou caminho acessível)
try:
    st.image("C:\Users\tabat\Documents\GitHub\chapiuski_analises\Confra\craque.jpg", use_column_width=True)
except FileNotFoundError:
    st.warning("⚠️ Imagem 'craque.jpg' não encontrada. Verifique o caminho.")

st.markdown("""
Salve, nação aurinegra! 💛🖤

Nessa confraternização teremos uma novidade e precisamos da ajuda de vocês para definir quem será o **Craque da Galera** ou, quais serão eles.

A brincadeira é fácil, funcionará por votação através do link abaixo, pedimos se atentar as regras, pois **não serão contabilizados votos em duplicidade** e só serão contabilizados votos de mensalistas anuais e/ou participantes da confraternização, ou seja, apenas quem comprou o ingresso.

Para simplificar e garantir o voto, cada pessoa apta para votar está recebendo essa mensagem no privado e seu código pessoal junto do link. O seu código deverá ser informado.

Abra o link, leia as regras e vote com atenção uma única vez inserindo o seu nome e **código pessoal**. **Não compartilhe seu código.**
---
""")

st.title("🏆 Votação Chapiuski - Escolha 3 Craques da Galera")


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
def salvar_voto(nome, codigo, votos):
    data = datetime.now().isoformat()

    # O payload agora inclui a coluna 'codigo'
    payload = [
        {"nome_eleitor": nome, "codigo": codigo, "craque_escolhido": v, "datahora": data}
        for v in votos
    ]

    # Note: A lógica para evitar votos duplicados por código (quem já votou) deve ser implementada antes do INSERT,
    # por exemplo, usando um SELECT para verificar se o código já existe na tabela de votos.
    # Essa implementação é apenas o INSERT básico.
    supabase.table(VOTACAO_TABLE).insert(payload).execute()


# ==============================
# UI - FORMULÁRIO DE VOTAÇÃO
# ==============================
with st.form("form"):
    nome = st.text_input("Seu nome:")
    codigo = st.text_input("Seu código pessoal:") # NOVO CAMPO
    
    votos = st.multiselect(
        "Escolha exatamente 3 jogadores:", 
        OPCOES,
        max_selections=3
    )

    enviado = st.form_submit_button("CONFIRMAR VOTO")

# ==============================
# LÓGICA DE ENVIO E VALIDAÇÃO
# ==============================
if enviado:
    # 1. Validação do Nome
    if not nome.strip():
        st.error("⚠️ Preencha seu nome.")
    # 2. Validação do Código
    elif not codigo.strip():
        st.error("⚠️ Preencha seu código pessoal.")
    # 3. Validação da Quantidade de Votos
    elif len(votos) != 3:
        st.error("⚠️ Você deve escolher **exatamente 3 jogadores**.")
    else:
        # Lógica de validação de duplicidade:
        # Você deve adicionar aqui a verificação no Supabase
        # para garantir que o 'codigo' informado ainda não tenha votado.
        
        # Exemplo BÁSICO de como seria a chamada:
        try:
            # Chama a função de salvamento com o nome, código e votos
            salvar_voto(nome.strip(), codigo.strip(), votos)
            st.success("🎉 Voto registrado com sucesso!")
        except Exception as e:
            st.error(f"❌ Erro ao registrar o voto. Tente novamente. Detalhe: {e}")