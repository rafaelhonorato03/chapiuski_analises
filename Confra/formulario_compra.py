import streamlit as st
import pandas as pd
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

arquivo = "compras_ingressos.xlsx"

st.markdown(
    """
    <div style="display: flex; justify-content: center;">
        <img src="Confra/chapiuski.png" width="200"/>
    </div>
    """,
    unsafe_allow_html=True
)

st.title("Compra de Ingressos - Festa Chapiuski")

email = st.text_input("E-mail para contato")
quantidade = st.number_input("Quantidade de ingressos", min_value=1, max_value=10, value=1)

# Campos dinâmicos para nomes dos participantes
nomes = []
documentos = []
for i in range(int(quantidade)):
    nome = st.text_input(f"Nome do participante #{i+1}")
    doc = st.text_input(f"Documento do participante #{i+1}")
    nomes.append(nome)
    documentos.append(doc)

# Link de pagamento (exemplo, ajuste conforme seu lote)
link_pagamento = "https://pag.ae/7_FMHdgNJ"
st.markdown(f"### 💳 [Clique aqui para pagar seu ingresso]({link_pagamento})")

# Upload do comprovante
comprovante = st.file_uploader("Envie o comprovante de pagamento (imagem ou PDF)", type=["png", "jpg", "jpeg", "pdf"])

# Dados do novo pedido
novo_pedido = {
    'E-mail': email,
    'Quantidade': quantidade,
    'Nomes': ', '.join(nomes),
    'Documentos': ', '.join(documentos)
}

if st.button("Reservar ingresso e Enviar Pedido"):
    # Salva no Excel (cria se não existir)
    if os.path.exists(arquivo):
        df = pd.read_excel(arquivo)
        df = pd.concat([df, pd.DataFrame([novo_pedido])], ignore_index=True)
    else:
        df = pd.DataFrame([novo_pedido])
    df.to_excel(arquivo, index=False)
    st.success(f"Ingressos reservados para: {', '.join(nomes)}. Confira seu e-mail para mais informações.")

    # Envia o pedido por e-mail com comprovante (se houver)
    remetente = st.secrets["email"]["remetente"]
    senha = st.secrets["email"]["senha"]
    destinatario = st.secrets["email"]["destinatario"]
    lista_destinatarios = [d.strip() for d in destinatario.split(",")]

    corpo = f"""
Novo pedido de ingresso:

E-mail do responsável: {email}
Quantidade de ingressos: {quantidade}

Participantes:
""" + "\n".join([f"{i+1}. Nome: {nomes[i]}, Documento: {documentos[i]}" for i in range(int(quantidade))])

    msg = MIMEMultipart()
    msg['Subject'] = "Novo pedido de ingresso"
    msg['From'] = remetente
    msg['To'] = destinatario
    msg.attach(MIMEText(corpo, 'plain'))

    # Anexa o comprovante, se houver
    if comprovante is not None:
        file_data = comprovante.read()
        part = MIMEBase('application', "octet-stream")
        part.set_payload(file_data)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{comprovante.name}"')
        msg.attach(part)

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(remetente, senha)
            server.sendmail(remetente, lista_destinatarios, msg.as_string())
        st.success("Dados enviados por e-mail para a organização!")
    except Exception as e:
        st.error(f"Erro ao enviar e-mail: {e}")