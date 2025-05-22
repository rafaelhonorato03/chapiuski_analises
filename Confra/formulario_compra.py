import streamlit as st
import pandas as pd
import os

# filepath para salvar os dados
arquivo = "compras_ingressos.xlsx"

st.title("Compra de Ingressos - Festa Chapiuski")

nome = st.text_input("Nome completo")
email = st.text_input("E-mail")
documento = st.text_input('Número de documento')
quantidade = st.number_input("Quantidade", min_value=1, max_value=10, value=1)

# Dados do novo pedido
novo_pedido = {
    'Nome': nome,
    'E-mail': email,
    'Documento': documento,
    'Quantidade': quantidade
}

# Defina o link de pagamento para cada lote (exemplo)
links_pagamento = {
    "1º Lote": "https://pag.ae/7_FMHdgNJ",
    "2º Lote": "https://pag.ae/7_FMKBcQs",
}

# Salva no Excel (cria se não existir)
if os.path.exists(arquivo):
    df = pd.read_excel(arquivo)
    df = pd.concat([df, pd.DataFrame([novo_pedido])], ignore_index=True)
else:
    df = pd.DataFrame([novo_pedido])

df.to_excel(arquivo, index=False)

if st.button("Reservar ingresso"):
    st.success(f"Ingresso reservado para {nome} ({email}), {quantidade}.")
    # Aqui você pode salvar os dados em um arquivo ou banco de dados

import smtplib
from email.mime.text import MIMEText

remetente = st.secrets['email']['remetente']
senha = st.secrets['email']['senha']
destinatario = st.secrets['email']['destinatario']

def enviar_email(destinatario, assunto, corpo):
    remetente = st.secrets["email"]["remetente"]
    senha = st.secrets["email"]["senha"]
    destinatario = st.secrets["email"]["destinatario"]
    msg = MIMEText(corpo)
    msg['Subject'] = assunto
    msg['From'] = remetente
    msg['To'] = destinatario

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(remetente, senha)
        server.sendmail(remetente, destinatario, msg.as_string())

# Exemplo de uso:
corpo = f"Novo pedido: {nome}, {email}, {documento}, {quantidade} ingresso(s)."
enviar_email("rafael.honorato03@exemplo.com", "Novo pedido de ingresso", corpo)