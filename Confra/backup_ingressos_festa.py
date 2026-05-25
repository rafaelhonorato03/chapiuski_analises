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
import re
from dotenv import load_dotenv
import io  # Importado para processar o CSV diretamente na memória RAM

# === Carregar Variáveis de Ambiente ===
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
EMAIL_REMETENTE = os.getenv("EMAIL_REMETENTE")

st.set_page_config(page_title="Ingressos - Festa Chapiuski", layout="wide")

# === Inicializar Supabase ===
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def email_valido(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)


def enviar_email(remetente, senha, destinatarios, assunto, corpo, comprovante, csv_bytes):
    msg = MIMEMultipart()
    msg['Subject'] = assunto
    msg['From'] = remetente
    msg['To'] = ", ".join(destinatarios)
    msg.attach(MIMEText(corpo, 'plain'))

    # Anexo do Comprovante (Upload do usuário)
    if comprovante is not None:
        part = MIMEBase('application', "octet-stream")
        file_data = comprovante.getvalue()
        part.set_payload(file_data)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{comprovante.name}"')
        msg.attach(part)

    # Anexo do CSV Filtrado (Gerado dinamicamente na memória)
    if csv_bytes is not None:
        part_csv = MIMEBase('application', "octet-stream")
        part_csv.set_payload(csv_bytes)
        encoders.encode_base64(part_csv)
        part_csv.add_header('Content-Disposition', 'attachment; filename="compras_ingressos.csv"')
        msg.attach(part_csv)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(remetente, senha)
        server.sendmail(remetente, destinatarios, msg.as_string())


# =========================================================================
# === CONTROLE MANUAL DE LOTES E LINKS (VIRE AQUI QUANDO PRECISAR) ========
# =========================================================================
LOTE_MANUAL = "UNICO"  # Opções: "UNICO" ou "PORTA"
# =========================================================================

MAX_INGRESSOS = 3 

# Título do App
st.title("Ingressos - Festa Chapiuski 2026")

# Seleção de quantidade de ingressos
quantidade = st.number_input(
    "Quantidade de ingressos",
    min_value=1,
    max_value=MAX_INGRESSOS,
    value=1,
    step=1
)

# Lógica de mapeamento dos links
if LOTE_MANUAL == "UNICO":
    lote_atual = "Lote Geral"
    links_lote = {
        1: ("https://pag.ae/81NJ3DfBa", "R$ 130,00 - R$ 135,41"),
        2: ("https://pag.ae/81NJ3_6wa", "R$ 260,00 - R$ 270,82"),
        3: ("https://pag.ae/81NJ4qHQv", "R$ 390,00 - R$ 406,23")
    }
    link_pagamento, preco_lote = links_lote[quantidade]
    lote_info = f"Valor para {quantidade} ingresso(s): {preco_lote} no link."
else:
    lote_atual = "Lote Porta"
    links_lote = {
        1: ("https://pag.ae/81NJ4Xzb6", "R$ 155,00 - R$ 161,45"),
        2: ("https://pag.ae/81NJ5qNKv", "R$ 310,00 - R$ 322,89"),
        3: ("https://pag.ae/81NJ5JD2M", "R$ 465,00 - R$ 484,35")
    }
    link_pagamento, preco_lote = links_lote[quantidade]
    lote_info = f"Valor para {quantidade} ingresso(s): {preco_lote} no link."

st.subheader(f"Lote atual: {lote_atual}")
if lote_info:
    st.info(lote_info)

st.markdown("""
**💰 VALORES**
- Lote Único: **R$ 130,00** (Dinheiro/Pix) ou no link de acordo com a quantidade.
- Lote Porta: **R$ 155,00** (Dinheiro/Pix) ou no link de acordo com a quantidade.

**💳 FORMAS DE PAGAMENTO**
- PIX com desconto: **(13)99133-7100**
- Débito e Crédito: Link de pagamento gerado abaixo automaticamente após escolher a quantidade.

**⚠️ REGRAS**
- 👧👦 Crianças até 12 anos não pagam, mas é obrigatório enviar os dados da criança (nome completo e documento) para o WhatsApp (13) 99133-7100 para liberação da entrada.
- A partir de 13 anos, pagam valor integral.
- Documento com foto obrigatório na entrada.
- Elevador: uso exclusivo para idosos e PCD.
- Proibido drogas ilícitas e narguilé.
- Preencha o site e envie o comprovante para validar sua compra.

⚠️ Atenção: Compras realizadas não poderão ser canceladas nem reembolsadas.

🎊 **Garanta já seu ingresso e venha comemorar o 9° ano do Chapiuski!** 🎊
""")

if "botao_enviado" not in st.session_state:
    st.session_state.botao_enviado = False

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
        st.markdown(f"### 💳 [Clique aqui para pagar seus {quantidade} ingresso(s)]({link_pagamento})")

    comprovante = st.file_uploader(
        "Envie o comprovante de pagamento (imagem ou PDF)",
        type=["png", "jpg", "jpeg", "pdf"]
    )

    enviado = st.form_submit_button("Reservar ingresso e enviar confirmação",
                                    disabled=st.session_state.botao_enviado)

if enviado and not st.session_state.botao_enviado:
    st.session_state.botao_enviado = True

# === Processamento ===
if enviado:
    if (
        email.strip() == "" or
        not email_valido(email) or
        any(nome.strip() == "" for nome in nomes) or
        any(doc.strip() == "" for doc in documentos) or
        comprovante is None
    ):
        st.warning("Por favor, preencha todos os campos corretamente e envie o comprovante antes de enviar o pedido.")
        st.session_state.botao_enviado = False 
    else:
        try:
            datahora = datetime.now().isoformat()
            data = {
                "email": email,
                "quantidade": quantidade,
                "nomes": ', '.join(nomes),
                "documentos": ', '.join(documentos),
                "datahora": datahora,
                "lote": lote_atual
            }
            
            # 1. Salva o novo registro no banco Supabase
            resposta = supabase.table("compra_ingressos").insert(data).execute()

            if resposta.data:
                st.success("✅ Pedido salvo no banco de dados com sucesso!")
            else:
                st.error("❌ Erro ao salvar no banco de dados.")

            st.success(f"Ingressos reservados para: {', '.join(nomes)}. Confira seu e-mail para mais informações.")

            # 2. Configurações de credenciais de e-mail
            remetente = os.getenv("EMAIL_REMETENTE")
            senha = os.getenv("EMAIL_SENHA")
            destinatario = os.getenv("EMAIL_DESTINATARIO")

            if not remetente or not senha or not destinatario:
                st.error("❌ Variáveis de ambiente não configuradas corretamente.")
                st.stop()

            lista_destinatarios = [d.strip() for d in destinatario.split(",")]

            # 3. GERAÇÃO DO CSV FILTRADO DIRETAMENTE DA MEMÓRIA
            csv_bytes = None
            try:
                # Busca todos os dados ordenando por 'datahora' para garantir consistência nas posições das linhas
                response_db = supabase.table("compra_ingressos").select("*").order("datahora", desc=False).execute()
                if response_db.data:
                    df_completo = pd.DataFrame(response_db.data)
                    
                    # .iloc[282:] corta da linha 283 em diante (Python começa no índice 0)
                    df_filtrado = df_completo[df_completo['id'] >= 283]
                    
                    # Filtra APENAS as colunas solicitadas
                    colunas_desejadas = ["id", "datahora", "email", "quantidade", "nomes", "documentos", "lote"]
                    
                    # O .filter() ignora colunas que porventura não existam para evitar que o código quebre
                    df_filtrado = df_filtrado[[col for col in colunas_desejadas if col in df_filtrado.columns]]

                    # Converte em bytes sem criar nenhum arquivo local no Streamlit
                    buffer_csv = io.BytesIO()
                    df_filtrado.to_csv(buffer_csv, index=False, encoding="utf-8")
                    csv_bytes = buffer_csv.getvalue()
            except Exception as e:
                st.error(f"Erro ao processar dados para o anexo CSV: {e}")

            # 4. Corpo do e-mail textualmente
            corpo = f"""
Novo pedido de ingresso ({lote_atual}):

E-mail do responsável: {email}
Quantidade de ingressos: {quantidade}
Data/Hora do pedido: {datahora}

Participantes:
""" + "\n".join([f"{i+1}. Nome: {nomes[i]}, Documento: {documentos[i]}" for i in range(quantidade)])

            # 5. Envia o e-mail passando os bytes do CSV virtual
            try:
                enviar_email(
                    remetente,
                    senha,
                    lista_destinatarios,
                    f"Novo pedido de ingresso - {lote_atual}",
                    corpo,
                    comprovante,
                    csv_bytes
                )
                st.success("Dados enviados por e-mail para a organização!")
            except Exception as e:
                st.error(f"Erro ao enviar e-mail: {e}")

        except Exception as e:
            st.error(f"Erro geral no processamento: {e}")
            st.session_state.botao_enviado = False