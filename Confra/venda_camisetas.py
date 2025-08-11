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
    page_title="Venda de Camisas 2025",
    page_icon="⚽"
)

# ==== Configurações Iniciais e Variáveis de Ambiente ====
# Certifique-se de ter um arquivo .env na raiz do projeto com estas variáveis
load_dotenv() 

# Conexão com o Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configurações de E-mail
EMAIL_REMETENTE = os.getenv("EMAIL_REMETENTE")
EMAIL_SENHA = os.getenv("EMAIL_SENHA")
EMAIL_DESTINATARIO = os.getenv("EMAIL_DESTINATARIO")


# ==== Constantes e Mapeamentos do Aplicativo ====
JOGADORES_FIXOS = {
    1: "Renan G", 2: "Renato", 3: "Arthur Garcia", 4: "Rafa Crispim", 6: "Kelvim", 7: "Kenneth",
    8: "Hassan", 9: "Marquezini", 10: "Biel", 11: "Dembele", 12: "Tuaf", 13: "Kauan", 14: "Marrone",
    17: "João Pedro", 19: "Léo Leite", 20: "Arthur", 21: "Yago", 22: "Zanardo", 23: "Rafa Castilho",
    28: "Vini Castilho", 29: "Dani R", 35: "Brisa", 43: "Allan", 44: "Felipinho", 71: "Tutão",
    80: "Gabriel Baby", 89: "Dody", 91: "Vitão", 98: "Askov", 99: "Isaías"
}

PRECO_JOGADOR = 150
PRECO_TORCEDOR = 115

# Mapeamento de (quantidade_jogador, quantidade_torcedor) para o link de pagamento
LINKS_PAGAMENTO = {
    # Apenas Jogador
    (1, 0): "https://pag.ae/7_WWHFHVr",
    (2, 0): "https://pag.ae/7_WWJgpjq",
    (3, 0): "https://pag.ae/7_WWJLahL",
    # Apenas Torcedor
    (0, 1): "https://pag.ae/7_WWKdMX5",
    (0, 2): "https://pag.ae/7_WWKGHTJ",
    (0, 3): "https://pag.ae/7_WWL9XYH",
    # Combinações
    (1, 1): "https://pag.ae/7_WWN5xun",
    (1, 2): "https://pag.ae/7_WWPyvX3",
    (1, 3): "https://pag.ae/7_WWQ2xX5",
    (2, 1): "https://pag.ae/7_WWQK8Qr",
    (2, 2): "https://pag.ae/7_WWNBv7L",
    (2, 3): "https://pag.ae/7_WWRrp9o",
    (3, 1): "https://pag.ae/7_WWR_3-q",
    (3, 2): "https://pag.ae/7_WWSBETJ",
    (3, 3): "https://pag.ae/7_WWP1c16",
}

# ==== Funções Auxiliares ====
def email_valido(email):
    """Verifica se o formato do e-mail é válido."""
    if email:
        return re.match(r"[^@]+@[^@]+\.[^@]+", email)
    return False

def enviar_email_confirmacao(remetente, senha, destinatarios, assunto, corpo, comprovante, caminho_csv=None):
    """Envia o e-mail de confirmação com anexos."""
    msg = MIMEMultipart()
    msg['Subject'] = assunto
    msg['From'] = remetente
    msg['To'] = ", ".join(destinatarios)
    msg.attach(MIMEText(corpo, 'plain'))

    # Anexa o comprovante de pagamento
    if comprovante is not None:
        part_comprovante = MIMEBase('application', "octet-stream")
        part_comprovante.set_payload(comprovante.getvalue())
        encoders.encode_base64(part_comprovante)
        part_comprovante.add_header('Content-Disposition', f'attachment; filename="{comprovante.name}"')
        msg.attach(part_comprovante)

    # Anexa o arquivo CSV com todos os pedidos
    if caminho_csv and os.path.exists(caminho_csv):
        with open(caminho_csv, "rb") as attachment:
            part_csv = MIMEBase('application', "octet-stream")
            part_csv.set_payload(attachment.read())
        encoders.encode_base64(part_csv)
        part_csv.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(caminho_csv)}"')
        msg.attach(part_csv)

    # Envio do e-mail
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(remetente, senha)
        server.sendmail(remetente, destinatarios, msg.as_string())


# ==== Interface do Streamlit ====

st.markdown("<h1 style='text-align: center;'>Chapiuski - Temporada 2025</h1>", unsafe_allow_html=True)

st.markdown("<h4 style='text-align: center; color: #333;'>1, 2, 4... Chapiuski!!! 🖤⚽💛</h4>", unsafe_allow_html=True)

# --- IMAGEM NO TOPO ---
# Coloque as imagens na mesma pasta que o script .py
try:
    st.image('Confra\camisas 2025.jpg', caption='Modelos oficiais para a temporada 2025')
except Exception:
    st.warning("⚠️ Imagem 'camisas 2025.jpg' não encontrada. Coloque-a na mesma pasta do script.")

st.divider()

# --- SEÇÃO DE SELEÇÃO DE QUANTIDADE ---
st.subheader("1. Escolha a quantidade de camisas")
col1, col2 = st.columns(2)
with col1:
    qtd_jogador = st.number_input(
        "Camisas **JOGADOR** (R$ 150,00)",
        min_value=0,
        max_value=3,
        step=1,
        key="qtd_jogador"
    )
with col2:
    qtd_torcedor = st.number_input(
        "Camisas **TORCEDOR** (R$ 115,00)",
        min_value=0,
        max_value=3,
        step=1,
        key="qtd_torcedor"
    )

# --- LÓGICA DE COMPRA E VALIDAÇÃO INICIAL ---
if qtd_jogador > 0 or qtd_torcedor > 0:
    # --- EXIBIÇÃO CONDICIONAL DAS IMAGENS DOS MODELOS ---
    st.markdown("---")
    cols_img = st.columns(2)
    try:
        if qtd_jogador > 0:
            with cols_img[0]:
                st.image('Confra\camisa atleta 2025.jpg', caption='Modelo Atleta (Jogador)')
        if qtd_torcedor > 0:
            # Se não houver camisa de jogador, a de torcedor ocupa o espaço todo
            col_idx = 1 if qtd_jogador > 0 else 0
            with cols_img[col_idx]:
                st.image('Confra\camisa torcedor 2025.jpg', caption='Modelo Torcedor')
    except Exception:
        st.warning("⚠️ Imagens 'camisa atleta 2025.jpg' ou 'camisa torcedor 2025.jpg' não encontradas.")
    st.markdown("---")

    # --- CÁLCULO E CRIAÇÃO DAS LISTAS ---
    preco_total = (qtd_jogador * PRECO_JOGADOR) + (qtd_torcedor * PRECO_TORCEDOR)
    tipos_camisas = ["Jogador"] * qtd_jogador + ["Torcedor"] * qtd_torcedor
    
    st.subheader(f"💰 Valor total do pedido: R$ {preco_total},00")
    st.subheader("2. Detalhes de cada camisa")

    nomes_camisa, numeros_camisa, tamanhos_camisa = [], [], []
    for i, tipo in enumerate(tipos_camisas):
        with st.container(border=True):
            st.markdown(f"**Camisa #{i+1} (Modelo: {tipo})**")
            col1, col2, col3 = st.columns(3)
            with col1:
                nome = st.text_input(f"Nome na camisa #{i+1}", key=f"nome_{i}")
            with col2:
                numero = st.number_input(f"Número (0-99)", min_value=0, max_value=99, key=f"num_{i}")
            with col3:
                # ===== LINHA ALTERADA =====
                tamanho = st.selectbox(
                    "Tamanho", 
                    ["P", "M", "G", "GG", "G1", "G2", "G3", "G4", "G5"], 
                    key=f"tamanho_{i}"
                )
            
            nomes_camisa.append(nome)
            numeros_camisa.append(numero)
            tamanhos_camisa.append(tamanho)
            
            if tipo == "Jogador" and numero in JOGADORES_FIXOS:
                st.warning(f"⚠️ Atenção: O número {numero} já pertence ao jogador {JOGADORES_FIXOS[numero]}.")

    # --- SEÇÃO DE SUBMISSÃO (DENTRO DO FORM) ---
    st.divider()
    with st.form("finalizar_compra_form"):
        st.subheader("✉️ 3. Seus dados e pagamento")
        
        nome_comprador = st.text_input("Seu nome completo")
        email_comprador = st.text_input("Seu melhor e-mail para contato")
        
        # Obtém o link de pagamento correto
        tupla_compra = (qtd_jogador, qtd_torcedor)
        link_pagamento = LINKS_PAGAMENTO.get(tupla_compra, '#')
        
        if link_pagamento != '#':
            st.info("Realize o pagamento no link abaixo e depois volte para esta guia para anexar o comprovante.")
            st.markdown(f"🔗 [**CLIQUE AQUI PARA PAGAR (R$ {preco_total},00)**]({link_pagamento})", unsafe_allow_html=True)
            comprovante = st.file_uploader("Anexe o comprovante de pagamento aqui", type=["png", "jpg", "jpeg", "pdf"])
        else:
            st.error("Combinação de camisas inválida. Contacte o administrador.")
            comprovante = None # Desabilita upload se o link for inválido
        
        st.divider()
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            finalizar_btn = st.form_submit_button("Finalizar Compra", use_container_width=True, disabled=(link_pagamento=='#'))
        with col_btn2:
            nova_compra_btn = st.form_submit_button("Finalizar e Nova Compra", use_container_width=True, disabled=(link_pagamento=='#'))


    # --- LÓGICA DE PROCESSAMENTO APÓS CLICAR EM QUALQUER UM DOS BOTÕES ---
    if finalizar_btn or nova_compra_btn:
        erro = False
        if not nome_comprador.strip():
            st.error("❌ Por favor, preencha seu nome completo.")
            erro = True
        if not email_valido(email_comprador):
            st.error("❌ O formato do e-mail é inválido.")
            erro = True
        if any(not nome.strip() for nome in nomes_camisa):
            st.error("❌ Preencha o nome para todas as camisas selecionadas.")
            erro = True
        if not comprovante:
            st.error("❌ O comprovante de pagamento é obrigatório.")
            erro = True

        if not erro:
            with st.spinner("Processando sua compra, por favor aguarde..."):
                try:
                    # --- Salva no Supabase ---
                    dados_para_supabase = {
                        "nome_compra": ", ".join([f"{nome} ({tipo})" for nome, tipo in zip(nomes_camisa, tipos_camisas)]),
                        "e_mail": email_comprador,
                        "tamanho": ", ".join(tamanhos_camisa),
                        "quantidade": len(tipos_camisas),
                        "valor_total": preco_total,
                        "status_pagam": "Aguardando Confirmação",
                        "tipo_camisa": ", ".join(tipos_camisas)
                    }
                    supabase.table("compra_camisas").insert(dados_para_supabase).execute()

                    # --- Gera CSV atualizado ---
                    response = supabase.table("compra_camisas").select("*").order("created_at", desc=True).execute()
                    caminho_csv = None
                    if response.data:
                        df = pd.DataFrame(response.data)
                        caminho_csv = "export_total_pedidos.csv"
                        df.to_csv(caminho_csv, index=False, encoding='utf-8-sig')
                    
                    # --- Prepara e envia o e-mail de notificação ---
                    destinatarios = [d.strip() for d in EMAIL_DESTINATARIO.split(",")]
                    assunto_email = f"Novo Pedido de Camisa 2025 - {nome_comprador}"
                    detalhes_camisas_email = "\n".join([f"  - Camisa {i+1} ({tipos_camisas[i]}): Nome '{nomes_camisa[i]}', Nº {numeros_camisa[i]}, Tam. {tamanhos_camisa[i]}" for i in range(len(tipos_camisas))])
                    
                    corpo_email = f"""
Novo pedido de camisas da temporada 2025 recebido!

DADOS DO COMPRADOR:
- Nome: {nome_comprador}
- E-mail: {email_comprador}
- Valor Total: R$ {preco_total},00
- Combinação: {qtd_jogador} Jogador / {qtd_torcedor} Torcedor

DETALHES DO PEDIDO:
{detalhes_camisas_email}

O comprovante de pagamento e o CSV atualizado de todos os pedidos estão em anexo.
Verifique o pagamento e atualize o status no painel do Supabase.
"""
                    enviar_email_confirmacao(EMAIL_REMETENTE, EMAIL_SENHA, destinatarios, assunto_email, corpo_email, comprovante, caminho_csv)
                    
                    # --- Mensagem de sucesso para o usuário ---
                    if finalizar_btn:
                        primeiro_nome = nome_comprador.split()[0]
                        st.success(f"✅ Compra finalizada com sucesso! Obrigado, {primeiro_nome}!")
                        st.info("Você receberá a confirmação e os próximos passos no e-mail informado.")
                        st.balloons()
                    
                    elif nova_compra_btn:
                        st.toast("✅ Compra registrada! A página será reiniciada para um novo pedido.", icon="🎉")
                        time.sleep(3)
                        st.rerun()

                except Exception as e:
                    st.error(f"❌ Ocorreu um erro inesperado ao processar seu pedido.")
                    st.error(f"Detalhe do erro: {e}")
                    st.warning("Por favor, tente novamente ou contate o suporte.")

else:
    st.info("Selecione a quantidade de camisas desejadas para iniciar seu pedido.")