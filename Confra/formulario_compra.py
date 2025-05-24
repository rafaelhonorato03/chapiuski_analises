import os
from datetime import datetime
import streamlit as st
from supabase import create_client, Client
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from pprint import pprint
from dotenv import load_dotenv

# === Carregar Variáveis de Ambiente ===
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
EMAIL_REMETENTE = os.getenv("EMAIL_REMETENTE")

# === Inicializar Supabase ===
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# === Função para buscar total de ingressos vendidos ===
def buscar_total_vendido():
    response = supabase.table("compras_ingressos").select("quantidade").execute()
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

# === Layout Streamlit ===
st.title("Compra de Ingressos - Confra Chapiuski 2025")
st.subheader(f"Lote atual: {lote_atual}")
if lote_info:
    st.info(lote_info)

if estoque_disponivel == 0:
    st.warning("🚫 Ingressos esgotados!")
    st.stop()

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

    comprovante = st.file_uploader(
        "Envie o comprovante de pagamento (imagem ou PDF)",
        type=["png", "jpg", "jpeg", "pdf"]
    )

    enviado = st.form_submit_button("Reservar ingresso e enviar confirmação")

# === Processamento ===
if enviado:
    try:
        # --- Salvar no Supabase ---
        data = {
            "email": email,
            "quantidade": quantidade,
            "nomes": ', '.join(nomes),
            "documentos": ', '.join(documentos),
            "datahora": datetime.now().isoformat(),
            "lote": lote_atual
        }
        resposta = supabase.table("compras_ingressos").insert(data).execute()

        if resposta.data:
            st.success("✅ Pedido salvo no banco de dados com sucesso!")
        else:
            st.error("❌ Erro ao salvar no banco de dados.")

        # --- Enviar e-mail com Brevo ---
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = BREVO_API_KEY

        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(configuration)
        )

        subject = "Confirmação de Ingresso - Confra Chapiuski"
        sender = {"name": "Confra Chapiuski", "email": EMAIL_REMETENTE}
        to = [{"email": email}]

        html_content = f"""
        <h3>🎟️ Seu pedido de ingresso foi recebido!</h3>
        <p><b>Quantidade:</b> {quantidade}</p>
        <p><b>Participantes:</b></p>
        <ul>
        {''.join([f"<li>{n} - {d}</li>" for n, d in zip(nomes, documentos)])}
        </ul>
        <p><b>Lote:</b> {lote_atual}</p>
        <p><b>Link para pagamento:</b> {link_pagamento}</p>
        <p>Obrigado por participar da Confra Chapiuski 🎉🍻!</p>
        """

        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=to,
            sender=sender,
            subject=subject,
            html_content=html_content
        )

        api_response = api_instance.send_transac_email(send_smtp_email)
        st.success("📧 E-mail enviado com sucesso!")

    except ApiException as e:
        st.error(f"Erro ao enviar e-mail via Brevo: {e}")
    except Exception as e:
        st.error(f"Erro geral: {e}")