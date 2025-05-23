from dotenv import load_dotenv
import streamlit as st
import pandas as pd
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
import re

load_dotenv()

# --- Funções auxiliares ---

def email_valido(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

def enviar_email(remetente, senha, destinatarios, assunto, corpo, comprovante):
    msg = MIMEMultipart()
    msg['Subject'] = assunto
    msg['From'] = remetente
    msg['To'] = ", ".join(destinatarios)
    msg.attach(MIMEText(corpo, 'plain'))
    if comprovante is not None:
        file_data = comprovante.read()
        part = MIMEBase('application', "octet-stream")
        part.set_payload(file_data)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{comprovante.name}"')
        msg.attach(part)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(remetente, senha)
        server.sendmail(remetente, destinatarios, msg.as_string())

# --- Interface ---

arquivo = "compras_ingressos.csv"

estoque_lotes = {
    "1º LOTE PROMOCIONAL": 2,
    "2º LOTE": 1,
}

# Verifica o número de ingressos já vendidos
if os.path.exists(arquivo):
    df_compras = pd.read_csv(arquivo)
    total_vendidos = df_compras['Quantidade'].sum()
else:
    total_vendidos = 0

# Define o lote atual
if total_vendidos < estoque_lotes["1º LOTE PROMOCIONAL"]:
    lote_atual = "1º LOTE PROMOCIONAL"
    link_pagamento = "https://pag.ae/7_FMHdgNJ"
    estoque_disponivel = estoque_lotes["1º LOTE PROMOCIONAL"] - total_vendidos
    lote_info = "R&#36; 100,00 no PIX ou R&#36; 105,00 no link (em até 10x)"
elif total_vendidos < (estoque_lotes["1º LOTE PROMOCIONAL"] + estoque_lotes["2º LOTE"]):
    lote_atual = "2º LOTE"
    link_pagamento = "https://pag.ae/7_FMKBcQs"
    estoque_disponivel = (estoque_lotes["1º LOTE PROMOCIONAL"] + estoque_lotes["2º LOTE"]) - total_vendidos
    lote_info = "R&#36; 120,00 no PIX ou R&#36; 125,00 no link (em até 10x)"
else:
    lote_atual = "Ingressos esgotados"
    link_pagamento = None
    estoque_disponivel = 0
    lote_info = ""

# Centraliza o logo
col1, col2, col3 = st.columns([1,2,1])
with col2:
    st.image("Confra/chapiuski.jpg", width=800)

st.title("Compra de Ingressos - Confra Chapiuski 2025")

st.markdown("""
**🥩🍻 OPEN FOOD & OPEN BAR!**
- Churrasco, guarnições, lanches de cupim e costela, chopp, vodka, cachaça, refrigerantes, sucos e água à vontade!

**🎶 ATRAÇÃO IMPERDÍVEL!**
- Grupo de pagode com o Alemão! Das 17h às 20h30 (com pausa de 30 min)

**⏰ Encerramento: 22h**

**💰 VALORES**
- 1º LOTE PROMOCIONAL: **R&#36; 100,00 no PIX** ou **R&#36; 105,00 no link** (em até 10x)
- 2º e 3º LOTE: valores e datas a definir após o término do lote promocional.

**💳 FORMAS DE PAGAMENTO**
- PIX com desconto: **(11)99499-1465**
- Débito e Crédito: Link de pagamento (até 10x com taxa)

**⚠️ REGRAS**
- Crianças até 12 anos não pagam. A partir de 13 anos, pagam integral.
- Documento com foto obrigatório na entrada.
- Elevador: uso exclusivo para idosos e PCD.
- Proibido drogas ilícitas e narguilé.
- Preencha o site e envie o comprovante para validar sua compra.

🎊 **Garanta já seu ingresso e venha comemorar o 8° ano do Chapiuski!** 🎊
""")

# Exibe o lote acima da quantidade
st.markdown(f"### {lote_atual}")
if lote_info:
    st.markdown(f"**{lote_info}**")

if estoque_disponivel > 0:
    quantidade = st.number_input(
        "Quantidade de ingressos",
        min_value=1,
        max_value=int(estoque_disponivel),
        value=1,
        step=1,
        key="quantidade_ingressos"
    )
else:
    st.warning("Ingressos esgotados.")
    st.stop()

with st.form("formulario_ingresso"):
    email = st.text_input("E-mail para contato")

    nomes = []
    documentos = []
    for i in range(int(quantidade)):
        col1, col2 = st.columns(2)
        with col1:
            nome = st.text_input(f"Nome do participante #{i+1}", key=f"nome_{i}")
        with col2:
            doc = st.text_input(f"Documento do participante #{i+1}", key=f"doc_{i}")
        nomes.append(nome)
        documentos.append(doc)

    if link_pagamento:
        st.markdown(f"### 💳 [Clique aqui para pagar seu ingresso]({link_pagamento})")

    comprovante = st.file_uploader("Envie o comprovante de pagamento (imagem ou PDF)", type=["png", "jpg", "jpeg", "pdf"])

    enviado = st.form_submit_button("Reservar ingresso e Enviar Pedido")

    if enviado:
        # Validação dos campos
        if (
            email.strip() == "" or
            not email_valido(email) or
            any(nome.strip() == "" for nome in nomes) or
            any(doc.strip() == "" for doc in documentos) or
            comprovante is None
        ):
            st.warning("Por favor, preencha todos os campos corretamente e envie o comprovante antes de enviar o pedido.")
        else:
            datahora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            novo_pedido = {
                'E-mail': email,
                'Quantidade': quantidade,
                'Nomes': ', '.join(nomes),
                'Documentos': ', '.join(documentos),
                'DataHora': datahora
            }
            # Salva no Excel (cria se não existir)
            if os.path.exists(arquivo):
                df = pd.read_csv(arquivo)
                df = pd.concat([df, pd.DataFrame([novo_pedido])], ignore_index=True)
            else:
                df = pd.DataFrame([novo_pedido])
            df.to_csv(arquivo, index=False)
            st.success(f"Ingressos reservados para: {', '.join(nomes)}. Confira seu e-mail para mais informações.")

            # Envia o pedido por e-mail com comprovante
            remetente = st.secrets["EMAIL_REMETENTE"]
            senha = st.secrets["EMAIL_SENHA"]
            destinatario = st.secrets["EMAIL_DESTINATARIO"]

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
""" + "\n".join([f"{i+1}. Nome: {nomes[i]}, Documento: {documentos[i]}" for i in range(int(quantidade))])

            try:
                enviar_email(remetente, senha, lista_destinatarios, "Novo pedido de ingresso", corpo, comprovante)
                st.success("Dados enviados por e-mail para a organização!")
            except Exception as e:
                st.error(f"Erro ao enviar e-mail: {e}")