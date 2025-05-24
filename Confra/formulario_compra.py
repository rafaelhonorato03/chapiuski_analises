import os
from datetime import datetime
import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from supabase import create_client, Client
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from pprint import pprint
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials
import re
import json
import time

# === Carregar Variáveis de Ambiente ===
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
EMAIL_REMETENTE = os.getenv("EMAIL_REMETENTE")

# === Inicializar Supabase ===
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

arquivo_csv = os.path.join(os.path.dirname(__file__), "compras_ingressos.csv")

def email_valido(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

def enviar_email(remetente, senha, destinatarios, assunto, corpo, comprovante, arquivo_csv):
    msg = MIMEMultipart()
    msg['Subject'] = assunto
    msg['From'] = remetente
    msg['To'] = ", ".join(destinatarios)
    msg.attach(MIMEText(corpo, 'plain'))

    # Anexa o comprovante
    if comprovante is not None:
        part = MIMEBase('application', "octet-stream")
        file_data = comprovante.getvalue()
        part.set_payload(file_data)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{comprovante.name}"')
        msg.attach(part)

    # Anexa o CSV como backup
    if os.path.exists(arquivo_csv):
        with open(arquivo_csv, "rb") as f:
            part_csv = MIMEBase('application', "octet-stream")
            part_csv.set_payload(f.read())
            encoders.encode_base64(part_csv)
            part_csv.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(arquivo_csv)}"')
            msg.attach(part_csv)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(remetente, senha)
        server.sendmail(remetente, destinatarios, msg.as_string())

# === Função para buscar total de ingressos vendidos ===
def buscar_total_vendido():
    response = supabase.table("compra_ingressos").select("quantidade").execute()
    if response.data:
        total = sum(item["quantidade"] for item in response.data)
        return total
    return 0

# === Controle de Lotes ===
estoque_lotes = {
    "1º LOTE PROMOCIONAL": 2,
    "2º LOTE": 2,
}

total_vendidos = buscar_total_vendido()

if total_vendidos < estoque_lotes["1º LOTE PROMOCIONAL"]:
    lote_atual = "1º LOTE PROMOCIONAL"
    link_pagamento = "https://pag.ae/7_FMHdgNJ"
    estoque_disponivel = estoque_lotes["1º LOTE PROMOCIONAL"] - total_vendidos
    lote_info = "RS 100,00 no PIX ou RS 105,00 no link (até 10x)"
elif total_vendidos < (estoque_lotes["1º LOTE PROMOCIONAL"] + estoque_lotes["2º LOTE"]):
    lote_atual = "2º LOTE"
    link_pagamento = "https://pag.ae/7_FMKBcQs"
    estoque_disponivel = (estoque_lotes["1º LOTE PROMOCIONAL"] + estoque_lotes["2º LOTE"]) - total_vendidos
    lote_info = "RS 120,00 no PIX ou RS 125,00 no link (até 10x)"
else:
    lote_atual = "Ingressos esgotados"
    link_pagamento = None
    estoque_disponivel = 0
    lote_info = ""

# === Função para sincronizar o CSV com o Supabase ===
def sincronizar_csv_com_supabase():
    try:
        response = supabase.table("compra_ingressos").select("*").execute()
        if response.data:
            df = pd.DataFrame(response.data)
            df.to_csv(arquivo_csv, index=False, encoding="utf-8")
            print("✅ CSV sincronizado com o Supabase.")
        else:
            # Se não houver dados, cria um CSV vazio com as colunas padrão
            colunas = ["email", "quantidade", "nomes", "documentos", "datahora", "lote"]
            df = pd.DataFrame(columns=colunas)
            df.to_csv(arquivo_csv, index=False, encoding="utf-8")
            print("⚠️ CSV criado vazio, sem dados no Supabase.")
    except Exception as e:
        print(f"❌ Erro ao sincronizar CSV com Supabase: {e}")

# === Layout Streamlit ===
st.title("Compra de Ingressos - Confra Chapiuski 2025")
st.subheader(f"Lote atual: {lote_atual}")
if lote_info:
    st.info(lote_info)

if estoque_disponivel == 0:
    st.warning("🚫 Ingressos esgotados!")
    st.stop()

# --- Layout ---
col1, col2, col3 = st.columns([1,2,1])
with col2:
    st.image("Confra/chapiuski.jpg", width=800)

st.markdown("""
**🥩🍻 OPEN FOOD & OPEN BAR!**
- Churrasco, guarnições, lanches de cupim e costela, chopp, vodka, cachaça, refrigerantes, sucos e água à vontade!

**🎶 ATRAÇÃO IMPERDÍVEL!**
- Grupo de pagode com o Alemão! Das 17h às 20h30 (com pausa de 30 min)

**⏰ Encerramento: 22h**

**💰 VALORES**
- 1º LOTE PROMOCIONAL: **RS 100,00 no PIX** ou **RS 105,00 no link** (em até 10x)
- 2º e 3º LOTE: valores e datas a definir após o término do lote promocional.

**💳 FORMAS DE PAGAMENTO**
- PIX com desconto: **(11)99499-1465**
- Débito e Crédito: Link de pagamento abaixo (até 10x com taxa)

**⚠️ REGRAS**
- Crianças até 12 anos não pagam. A partir de 13 anos, pagam integral.
- Documento com foto obrigatório na entrada.
- Elevador: uso exclusivo para idosos e PCD.
- Proibido drogas ilícitas e narguilé.
- Preencha o site e envie o comprovante para validar sua compra.

🎊 **Garanta já seu ingresso e venha comemorar o 8° ano do Chapiuski!** 🎊
""")

quantidade = st.number_input(
    "Quantidade de ingressos",
    min_value=1,
    max_value=int(estoque_disponivel),
    value=1,
    step=1
)

# === Formulário ===
with st.form("formulario_ingresso"):
    email = st.text_input("E-mail para contato")
    nomes = []
    documentos = []

    for i in range(quantidade):
        col1, col2 = st.columns(2)
        with col1:
            nome = st.text_input(f"Nome do participante #{i+1}", key=f"nome_{i}")
        with col2:
            documento = st.text_input(f"Documento do participante #{i+1}", key=f"doc_{i}")
        nomes.append(nome)
        documentos.append(documento)
    
    if link_pagamento:
        st.markdown(f"### 💳 [Clique aqui para pagar seu ingresso]({link_pagamento})")

    comprovante = st.file_uploader(
        "Envie o comprovante de pagamento (imagem ou PDF)",
        type=["png", "jpg", "jpeg", "pdf"]
    )

    enviado = st.form_submit_button("Reservar ingresso e enviar confirmação")

# === Processamento ===
if enviado:
    # --- Validação dos campos ---
    if (
        email.strip() == "" or
        not email_valido(email) or
        any(nome.strip() == "" for nome in nomes) or
        any(doc.strip() == "" for doc in documentos) or
        comprovante is None
    ):
        st.warning("Por favor, preencha todos os campos corretamente e envie o comprovante antes de enviar o pedido.")
    else:
        try:
            # --- Salvar no Supabase ---
            datahora = datetime.now().isoformat()
            data = {
                "email": email,
                "quantidade": quantidade,
                "nomes": ', '.join(nomes),
                "documentos": ', '.join(documentos),
                "datahora": datetime.now().isoformat(),
                "lote": lote_atual
            }
            resposta = supabase.table("compra_ingressos").insert(data).execute()

            if resposta.data:
                st.success("✅ Pedido salvo no banco de dados com sucesso!")
            else:
                st.error("❌ Erro ao salvar no banco de dados.")

            # --- Sincronizar CSV com Supabase ---
            sincronizar_csv_com_supabase()

            if os.path.exists(arquivo_csv):
                df = pd.read_csv(arquivo_csv)
                df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)
            else:
                df = pd.DataFrame([data])
            df.to_csv(arquivo_csv, index=False)

            st.success(f"Ingressos reservados para: {', '.join(nomes)}. Confira seu e-mail para mais informações.")

            # --- Preparar e enviar e-mail ---
            remetente = os.getenv("EMAIL_REMETENTE")
            senha = os.getenv("EMAIL_SENHA")
            destinatario = os.getenv("EMAIL_DESTINATARIO")

            if not remetente or not senha or not destinatario:
                st.error("❌ Variáveis de ambiente não configuradas corretamente.")
                st.stop()

            lista_destinatarios = [d.strip() for d in destinatario.split(",")]

            corpo = f"""
Novo pedido de ingresso:

E-mail do responsável: {email}
Quantidade de ingressos: {quantidade}
Data/Hora do pedido: {datahora}

Participantes:
""" + "\n".join([f"{i+1}. Nome: {nomes[i]}, Documento: {documentos[i]}" for i in range(quantidade)])

            try:
                enviar_email(
                    remetente,
                    senha,
                    lista_destinatarios,
                    "Novo pedido de ingresso",
                    corpo,
                    comprovante,
                    arquivo_csv
                )
                st.success("Dados enviados por e-mail para a organização!")
            except Exception as e:
                st.error(f"Erro ao enviar e-mail: {e}")

        except Exception as e:
            st.error(f"Erro geral no processamento: {e}")
time.sleep(10)
st.experimental_rerun()