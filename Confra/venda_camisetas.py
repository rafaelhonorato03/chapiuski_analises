import os
import re
import smtplib
import time
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders

import streamlit as st
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv

# ==== Configuração da Página (DEVE SER O PRIMEIRO COMANDO STREAMLIT) ====
st.set_page_config(
    layout="centered",
    page_title="Venda de Camisas",
    page_icon="👕"
)

# ==== Configurações Iniciais e Variáveis de Ambiente ====
load_dotenv()

# Conexão com o Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configurações de E-mail
EMAIL_REMETENTE = os.getenv("EMAIL_REMETENTE")
EMAIL_SENHA = os.getenv("EMAIL_SENHA")
EMAIL_DESTINATARIO = os.getenv("EMAIL_DESTINATARIO")

# ==== Constantes do Aplicativo ====
JOGADORES_FIXOS = {
    1: "Renan G", 2: "Renato", 3: "Arthur Garcia", 4: "Rafa Crispim", 6: "Kelvim", 7: "Kenneth",
    8: "Hassan", 9: "Marquezini", 10: "Biel", 11: "Dembele", 12: "Tuaf", 13: "Kauan", 14: "Marrone",
    17: "João Pedro", 19: "Léo Leite", 20: "Arthur", 21: "Yago", 22: "Zanardo", 23: "Rafa Castilho",
    28: "Vini Castilho", 29: "Dani R", 35: "Brisa", 43: "Allan", 44: "Felipinho", 71: "Tutão",
    80: "Gabriel Baby", 89: "Dody", 91: "Vitão", 98: "Askov", 99: "Isaías"
}

LINKS_PAGAMENTO = {
    "1 Camisa Jogador": "https://link_pagamento_jogador",
    "1 Camisa Jogador + 1 Camisa Torcedor": "https://link_pagamento_jogador_torcedor",
    "1 Camisa Torcedor": "https://link_pagamento_torcedor",
    "2 Camisas Torcedor": "https://link_pagamento_dois_torcedores"
}

# ==== Funções Auxiliares ====
def email_valido(email):
    if email:
        return re.match(r"[^@]+@[^@]+\.[^@]+", email)
    return False

def enviar_email_confirmacao(remetente, senha, destinatarios, assunto, corpo, comprovante, caminho_csv=None):
    msg = MIMEMultipart()
    msg['Subject'] = assunto
    msg['From'] = remetente
    msg['To'] = ", ".join(destinatarios)
    msg.attach(MIMEText(corpo, 'plain'))

    if comprovante is not None:
        part_comprovante = MIMEBase('application', "octet-stream")
        part_comprovante.set_payload(comprovante.getvalue())
        encoders.encode_base64(part_comprovante)
        part_comprovante.add_header('Content-Disposition', f'attachment; filename="{comprovante.name}"')
        msg.attach(part_comprovante)

    if caminho_csv and os.path.exists(caminho_csv):
        with open(caminho_csv, "rb") as attachment:
            part_csv = MIMEBase('application', "octet-stream")
            part_csv.set_payload(attachment.read())
        encoders.encode_base64(part_csv)
        part_csv.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(caminho_csv)}"')
        msg.attach(part_csv)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(remetente, senha)
        server.sendmail(remetente, destinatarios, msg.as_string())

# ==== Interface do Streamlit ====

st.title("👕 Venda de Camisas Oficiais")
st.divider()

# --- SEÇÃO INTERATIVA (FORA DO FORM) ---
opcao_compra_key = st.selectbox(
    "Selecione sua opção de compra",
    [
        "1 Camisa Jogador",
        "1 Camisa Jogador + 1 Camisa Torcedor",
        "1 Camisa Torcedor",
        "2 Camisas Torcedor"
    ],
    help="Escolha o pacote de camisas que deseja adquirir."
)

if "Jogador" in opcao_compra_key and "Torcedor" in opcao_compra_key:
    tipos_camisas = ["Jogador", "Torcedor"]; preco_total = 260
elif "1 Camisa Jogador" in opcao_compra_key:
    tipos_camisas = ["Jogador"]; preco_total = 150
elif "2 Camisas Torcedor" in opcao_compra_key:
    tipos_camisas = ["Torcedor", "Torcedor"]; preco_total = 220
else:
    tipos_camisas = ["Torcedor"]; preco_total = 110

st.subheader(f"💰 Valor total: R$ {preco_total},00")
st.subheader("👕 Detalhes das Camisas")

nomes_camisa, numeros_camisa, tamanhos_camisa = [], [], []
for i, tipo in enumerate(tipos_camisas):
    with st.container(border=True):
        st.markdown(f"**Camisa #{i+1} ({tipo})**")
        col1, col2, col3 = st.columns(3)
        with col1: nome = st.text_input(f"Nome na camisa #{i+1}", key=f"nome_{i}")
        with col2: numero = st.number_input(f"Número (0-99)", min_value=0, max_value=99, key=f"num_{i}")
        with col3: tamanho = st.selectbox("Tamanho", ["P", "M", "G", "GG", "XG"], key=f"tamanho_{i}")
        
        nomes_camisa.append(nome); numeros_camisa.append(numero); tamanhos_camisa.append(tamanho)
        
        if tipo == "Jogador" and numero in JOGADORES_FIXOS:
            st.warning(f"⚠️ Atenção: O número {numero} já pertence ao jogador {JOGADORES_FIXOS[numero]}.")

# --- SEÇÃO DE SUBMISSÃO (DENTRO DO FORM) ---
st.divider()
with st.form("finalizar_compra_form"):
    st.subheader("✉️ Seus Dados e Pagamento")
    
    # >>> CAMPO DE NOME DO COMPRADOR ADICIONADO <<<
    nome_comprador = st.text_input("Seu nome completo")
    email_comprador = st.text_input("Seu melhor e-mail para contato")
    
    link_pagamento = LINKS_PAGAMENTO.get(opcao_compra_key, '#')
    st.info("Realize o pagamento no link abaixo e depois volte para esta guia para anexar o comprovante.")
    st.markdown(f"🔗 [PAGAR AGORA (R$ {preco_total},00)]({link_pagamento})")
    comprovante = st.file_uploader("Anexe o comprovante de pagamento aqui", type=["png", "jpg", "jpeg", "pdf"])
    
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        finalizar_btn = st.form_submit_button("Finalizar Compra", use_container_width=True)
    with col2:
        nova_compra_btn = st.form_submit_button("Finalizar e Nova Compra", use_container_width=True)


# --- LÓGICA DE PROCESSAMENTO APÓS CLICAR EM QUALQUER UM DOS BOTÕES ---
if finalizar_btn or nova_compra_btn:
    erro = False
    # >>> VALIDAÇÃO DO NOME DO COMPRADOR ADICIONADA <<<
    if not nome_comprador.strip(): st.error("❌ Por favor, preencha seu nome completo."); erro = True
    if not email_valido(email_comprador): st.error("❌ E-mail inválido."); erro = True
    if any(nome.strip() == "" for nome in nomes_camisa): st.error("❌ Preencha o nome para todas as camisas."); erro = True
    if not comprovante: st.error("❌ O comprovante de pagamento é obrigatório."); erro = True

    if not erro:
        with st.spinner("Processando sua compra..."):
            try:
                dados_para_supabase = {
                    "nome_compra": ", ".join(nomes_camisa), "e_mail": email_comprador,
                    "tamanho": ", ".join(tamanhos_camisa), "quantidade": len(tipos_camisas),
                    "valor_total": preco_total, "status_pagam": "Aguardando Confirmação",
                    "tipo_camisa": ", ".join(tipos_camisas)
                }
                supabase.table("compra_camisas").insert(dados_para_supabase).execute()

                response = supabase.table("compra_camisas").select("*").order("created_at", desc=True).execute()
                caminho_csv = None
                if response.data:
                    df = pd.DataFrame(response.data)
                    caminho_csv = "export_total_pedidos.csv"
                    df.to_csv(caminho_csv, index=False, encoding='utf-8-sig')
                
                destinatarios = [d.strip() for d in EMAIL_DESTINATARIO.split(",")]
                assunto_email = f"Novo Pedido de Camisa - {nome_comprador}"
                detalhes_camisas = "\n".join([f"  - Camisa {i+1} ({tipos_camisas[i]}): {nomes_camisa[i]}, Nº {numeros_camisa[i]}, Tam. {tamanhos_camisa[i]}" for i in range(len(tipos_camisas))])
                
                # >>> NOME DO COMPRADOR ADICIONADO AO CORPO DO E-MAIL <<<
                corpo_email = f"""
Novo pedido de camisas recebido.

DADOS DO COMPRADOR:
- Nome: {nome_comprador}
- E-mail: {email_comprador}
- Valor Total: R$ {preco_total},00

DETALHES DO PEDIDO:
{detalhes_camisas}

O comprovante de pagamento e o CSV atualizado de todos os pedidos estão em anexo.
"""
                
                enviar_email_confirmacao(EMAIL_REMETENTE, EMAIL_SENHA, destinatarios, assunto_email, corpo_email, comprovante, caminho_csv)
                
                if finalizar_btn:
                    # >>> MENSAGEM DE SUCESSO PERSONALIZADA <<<
                    primeiro_nome = nome_comprador.split()[0]
                    st.success(f"✅ Compra finalizada com sucesso! Obrigado, {primeiro_nome}!")
                    st.balloons()
                
                elif nova_compra_btn:
                    st.toast("✅ Compra registrada! A página será reiniciada.", icon="🎉")
                    time.sleep(2)
                    st.rerun()

            except Exception as e:
                st.error(f"Ocorreu um erro ao processar seu pedido: {e}")