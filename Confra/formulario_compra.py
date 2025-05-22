import streamlit as st
import pandas as pd
import os

arquivo = "compras_ingressos.xlsx"

st.title("Compra de Ingressos - Festa Chapiuski")

email = st.text_input("E-mail do responsável")
documento = st.text_input('Número de documento do responsável')
quantidade = st.number_input("Quantidade de ingressos", min_value=1, max_value=10, value=1)

# Campos dinâmicos para nomes dos participantes
nomes = []
for i in range(int(quantidade)):
    nome = st.text_input(f"Nome do participante #{i+1}")
    nomes.append(nome)

# Dados do novo pedido
novo_pedido = {
    'E-mail': email,
    'Documento': documento,
    'Quantidade': quantidade,
    'Nomes': ', '.join(nomes)
}

links_pagamento = {
    "1º Lote": "https://pag.ae/7_FMHdgNJ",
    "2º Lote": "https://pag.ae/7_FMKBcQs",
}

if st.button("Reservar ingresso"):
    # Salva no Excel (cria se não existir)
    if os.path.exists(arquivo):
        df = pd.read_excel(arquivo)
        df = pd.concat([df, pd.DataFrame([novo_pedido])], ignore_index=True)
    else:
        df = pd.DataFrame([novo_pedido])
    df.to_excel(arquivo, index=False)
    st.success(f"Ingressos reservados para: {', '.join(nomes)}. Confira seu e-mail para mais informações.")

    # Envio de e-mail (exemplo)
    import smtplib
    from email.mime.text import MIMEText

    remetente = st.secrets['email']['remetente']
    senha = st.secrets['email']['senha']
    destinatario = st.secrets['email']['destinatario']

    corpo = f"Novo pedido: {', '.join(nomes)}, {email}, {documento}, {quantidade} ingresso(s)."
    msg = MIMEText(corpo)
    msg['Subject'] = "Novo pedido de ingresso"
    msg['From'] = remetente
    msg['To'] = destinatario

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(remetente, senha)
        server.sendmail(remetente, destinatario, msg.as_string())