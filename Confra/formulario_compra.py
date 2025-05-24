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
import gspread
from google.oauth2.service_account import Credentials
import re
import json

# Carrega variáveis de ambiente
load_dotenv()

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

CREDENTIALS_JSON = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
st.text(f"Conteúdo bruto da credencial: {repr(CREDENTIALS_JSON)}")
sheet_id = os.getenv("GOOGLE_SHEET_ID")

if not CREDENTIALS_JSON:
    st.error("Variável de ambiente GOOGLE_SHEETS_CREDENTIALS não encontrada!")
    st.stop()

import re # Certifique-se que 'import re' está no topo do seu script
# ... outras importações

CREDENTIALS_JSON_RAW = os.getenv('GOOGLE_SHEETS_CREDENTIALS')

if not CREDENTIALS_JSON_RAW:
    st.error("Variável de ambiente GOOGLE_SHEETS_CREDENTIALS não encontrada!")
    st.stop()

st.text(f"Conteúdo bruto recebido: {repr(CREDENTIALS_JSON_RAW)}") # Linha de depuração

try:
    # Tentativa 1: Tentar carregar diretamente (pode funcionar em alguns casos)
    try:
        creds_info = json.loads(CREDENTIALS_JSON_RAW)
        st.success("JSON decodificado diretamente com sucesso!") # Linha de depuração
    except json.JSONDecodeError as e1:
        st.warning(f"Falha ao carregar diretamente: {e1}. Tentando normalizar a private_key...")

        # Tentativa 2: Normalizar novas linhas APENAS dentro do valor da private_key
        # Esta função auxiliar substitui \n por \\n dentro do conteúdo da chave privada
        def escape_newlines_in_key(match):
            key_content = match.group(1)
            # Substitui a nova linha literal por uma nova linha escapada para JSON
            escaped_content = key_content.replace('\n', '\\n') 
            return f'"private_key": "{escaped_content}"'

        # Regex para encontrar "private_key": "-----BEGIN ... -----END PRIVATE KEY-----\n"
        # Captura o conteúdo entre as aspas. re.DOTALL permite que '.' corresponda a novas linhas.
        pattern = r'"private_key":\s*"((?:-----BEGIN PRIVATE KEY-----(?:.|\n)*?-----END PRIVATE KEY-----))"'
        
        # Verifica se o padrão é encontrado antes de tentar substituir
        if re.search(pattern, CREDENTIALS_JSON_RAW, re.DOTALL):
             # Aplica a substituição usando a função auxiliar
             creds_json_normalized = re.sub(pattern, escape_newlines_in_key, CREDENTIALS_JSON_RAW, count=1, flags=re.DOTALL)
             st.text(f"Conteúdo após normalização da chave: {repr(creds_json_normalized)}") # Linha de depuração
             try:
                 # Tenta carregar o JSON com a chave privada normalizada
                 creds_info = json.loads(creds_json_normalized)
                 st.success("JSON decodificado com sucesso após normalização da chave!") # Linha de depuração
             except json.JSONDecodeError as e2:
                 st.error(f"Erro ao decodificar JSON após normalização da chave: {e2}")
                 st.text(f"Conteúdo normalizado que falhou: {repr(creds_json_normalized)}")
                 st.stop()
        else:
             # Se o padrão da chave privada não for encontrado (improvável, mas seguro verificar)
             st.error("Não foi possível encontrar o padrão 'private_key' no JSON para normalização.")
             st.text(f"Conteúdo bruto que falhou na busca do padrão: {repr(CREDENTIALS_JSON_RAW)}")
             st.stop()

except Exception as ex:
    # Captura outros erros inesperados durante o processo
    st.error(f"Ocorreu um erro inesperado ao processar as credenciais: {ex}")
    st.text(f"Conteúdo bruto no momento do erro: {repr(CREDENTIALS_JSON_RAW)}")
    st.stop()

# --- Continue com o resto do seu script usando creds_info ---
# Exemplo:
# creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
# gc = gspread.authorize(creds)
# ...

# Lembre-se de remover as linhas st.text de depuração quando confirmar que funciona.

creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
gc = gspread.authorize(creds)

spreadsheet = gc.open_by_key(sheet_id)

# Selecionar aba
sheet = spreadsheet.worksheet("Página1")  # ou pelo nome da aba

# Ler dados existentes
dados = sheet.get_all_records()

# Converter para DataFrame
df_compras = pd.DataFrame(dados)

total_vendidos = df_compras['Quantidade'].sum() if not df_compras.empty else 0

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


# --- Estoque ---
estoque_lotes = {
    "1º LOTE PROMOCIONAL": 2,
    "2º LOTE": 1,
}

# --- Definir lote atual ---
if total_vendidos < estoque_lotes["1º LOTE PROMOCIONAL"]:
    lote_atual = "1º LOTE PROMOCIONAL"
    link_pagamento = "https://pag.ae/7_FMHdgNJ"
    estoque_disponivel = estoque_lotes["1º LOTE PROMOCIONAL"] - total_vendidos
    lote_info = "RS 100,00 no PIX ou RS 105,00 no link (em até 10x)"
elif total_vendidos < (estoque_lotes["1º LOTE PROMOCIONAL"] + estoque_lotes["2º LOTE"]):
    lote_atual = "2º LOTE"
    link_pagamento = "https://pag.ae/7_FMKBcQs"
    estoque_disponivel = (estoque_lotes["1º LOTE PROMOCIONAL"] + estoque_lotes["2º LOTE"]) - total_vendidos
    lote_info = "RS 120,00 no PIX ou RS 125,00 no link (em até 10x)"
else:
    lote_atual = "Ingressos esgotados"
    link_pagamento = None
    estoque_disponivel = 0
    lote_info = ""

# --- Layout ---
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
- 1º LOTE PROMOCIONAL: **RS 100,00 no PIX** ou **RS 105,00 no link** (em até 10x)
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

# --- Lote ---
st.markdown(f"### {lote_atual}")
if lote_info:
    st.markdown(f"**{lote_info}**")

if estoque_disponivel == 0:
    st.warning("Ingressos esgotados.")
    st.stop()

quantidade = st.number_input(
    "Quantidade de ingressos",
    min_value=1,
    max_value=int(estoque_disponivel),
    value=1,
    step=1
)

# --- Formulário ---
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

    comprovante = st.file_uploader(
        "Envie o comprovante de pagamento (imagem ou PDF)", 
        type=["png", "jpg", "jpeg", "pdf"]
    )

    enviado = st.form_submit_button("Reservar ingresso e Enviar Pedido")

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
            datahora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            novo_pedido = {
                'E-mail': email,
                'Quantidade': quantidade,
                'Nomes': ', '.join(nomes),
                'Documentos': ', '.join(documentos),
                'DataHora': datahora
            }

            # --- Salvar CSV ---
            if os.path.exists(arquivo_csv):
                df = pd.read_csv(arquivo_csv)
                df = pd.concat([df, pd.DataFrame([novo_pedido])], ignore_index=True)
            else:
                df = pd.DataFrame([novo_pedido])
            df.to_csv(arquivo_csv, index=False)

            st.success(f"Ingressos reservados para: {', '.join(nomes)}. Confira seu e-mail para mais informações.")
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
""" + "\n".join([f"{i+1}. Nome: {nomes[i]}, Documento: {documentos[i]}" for i in range(int(quantidade))])

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

            # Enviar para Google Sheets
            sheet.append_row([
                email,
                quantidade,
                ', '.join(nomes),
                ', '.join(documentos),
                datahora
            ])