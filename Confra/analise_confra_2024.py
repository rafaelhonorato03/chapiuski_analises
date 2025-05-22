import streamlit as st
import pandas as pd
import os
from datetime import datetime

arquivo = "compras_ingressos.xlsx"

st.image("Confra\chapiuski.png", width=200)  # ajuste o caminho e o tamanho conforme necessário
st.title("Compra de Ingressos - Festa Chapiuski")

email = st.text_input("E-mail para contato")
quantidade = st.number_input("Quantidade de ingressos", min_value=1, max_value=10, value=1)

# Campos dinâmicos para nomes e documentos dos participantes
nomes = []
documentos = []
for i in range(int(quantidade)):
    nome = st.text_input(f"Nome do participante #{i+1}")
    doc = st.text_input(f"Documento do participante #{i+1}")
    nomes.append(nome)
    documentos.append(doc)

# Link de pagamento (exemplo, ajuste conforme seu lote)
link_pagamento = "https://pag.ae/7_FMHdgNJ"

# Dados do novo pedido
novo_pedido = {
    'E-mail': email,
    'Quantidade': quantidade,
    'Nomes': ', '.join(nomes),
    'Documentos': ', '.join(documentos),
    'DataHora': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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

    st.markdown(f"### 💳 [Clique aqui para pagar seu ingresso]({link_pagamento})")

    st.info("Após o pagamento, envie o comprovante abaixo:")

    comprovante = st.file_uploader("Envie o comprovante de pagamento (imagem ou PDF)", type=["png", "jpg", "jpeg", "pdf"])
    if comprovante is not None:
        # Salva o comprovante na pasta 'comprovantes'
        os.makedirs("comprovantes", exist_ok=True)
        caminho = f"comprovantes/{email.replace('@','_').replace('.','_')}_{comprovante.name}"
        with open(caminho, "wb") as f:
            f.write(comprovante.getbuffer())
        st.success("Comprovante enviado com sucesso!")