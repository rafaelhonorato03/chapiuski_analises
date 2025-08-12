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

LINKS_PAGAMENTO = {
    (1, 0): "https://pag.ae/7_WWHFHVr", (2, 0): "https://pag.ae/7_WWJgpjq", (3, 0): "https://pag.ae/7_WWJLahL",
    (0, 1): "https://pag.ae/7_WWKdMX5", (0, 2): "https://pag.ae/7_WWKGHTJ", (0, 3): "https://pag.ae/7_WWL9XYH",
    (1, 1): "https://pag.ae/7_WWN5xun", (1, 2): "https://pag.ae/7_WWPyvX3", (1, 3): "https://pag.ae/7_WWQ2xX5",
    (2, 1): "https://pag.ae/7_WWQK8Qr", (2, 2): "https://pag.ae/7_WWNBv7L", (2, 3): "https://pag.ae/7_WWRrp9o",
    (3, 1): "https://pag.ae/7_WWR_3-q", (3, 2): "https://pag.ae/7_WWSBETJ", (3, 3): "https://pag.ae/7_WWP1c16",
}

# ==== Funções Auxiliares ====
def email_valido(email):
    """Verifica se o formato do e-mail é válido."""
    if email:
        return re.match(r"[^@]+@[^@]+\.[^@]+", email)
    return False

# Função para enviar e-mail de notificação para o administrador
def enviar_email_notificacao(remetente, senha, destinatarios, assunto, corpo, comprovante, caminho_csv=None):
    """Envia o e-mail de notificação para o admin com todos os anexos."""
    msg = MIMEMultipart()
    msg['Subject'] = assunto
    msg['From'] = remetente
    msg['To'] = ", ".join(destinatarios)
    msg.attach(MIMEText(corpo, 'plain', 'utf-8'))

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

# <<< NOVO: Função para enviar e-mail de confirmação para o comprador >>>
def enviar_email_para_comprador(remetente, senha, destinatario, assunto, corpo):
    """Envia um e-mail simples de confirmação para o comprador, sem anexos."""
    msg = MIMEMultipart()
    msg['Subject'] = assunto
    msg['From'] = remetente
    msg['To'] = destinatario
    msg.attach(MIMEText(corpo, 'html', 'utf-8')) # Usando HTML para melhor formatação

    # Envio do e-mail
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(remetente, senha)
        server.sendmail(remetente, destinatario, msg.as_string())


# ==== Interface do Streamlit ====

st.markdown("<h1 style='text-align: center;'>Chapiuski - Temporada 2025</h1>", unsafe_allow_html=True)
st.markdown("<h4 style='text-align: center; color: #333;'>1, 2, 4... Chapiuski!!! 💛🖤⚽</h4>", unsafe_allow_html=True)

try:
    st.image('Confra/camisas 2025.jpg', caption='Modelos oficiais para a temporada 2025')
except Exception:
    st.warning("⚠️ Imagem 'camisas 2025.jpg' não encontrada.")
st.divider()

st.subheader("1. Escolha a quantidade de camisas")
col1, col2 = st.columns(2)
with col1:
    qtd_jogador = st.number_input("Camisas **JOGADOR** (**R$ 150,00**)", min_value=0, max_value=3, step=1, key="qtd_jogador")
with col2:
    qtd_torcedor = st.number_input("Camisas **TORCEDOR** (**R$ 115,00**)", min_value=0, max_value=3, step=1, key="qtd_torcedor")

if qtd_jogador > 0 or qtd_torcedor > 0:
    st.markdown("---")
    cols_img = st.columns(2)
    try:
        if qtd_jogador > 0:
            with cols_img[0]:
                st.image('Confra/camisa atleta 2025.jpg', caption='Modelo Atleta (Jogador)')
        if qtd_torcedor > 0:
            col_idx = 1 if qtd_jogador > 0 else 0
            with cols_img[col_idx]:
                st.image('Confra/camisa torcedor 2025.jpg', caption='Modelo Torcedor')
    except Exception:
        st.warning("⚠️ Imagens dos modelos de camisa não encontradas.")
    st.markdown("---")

    preco_total = (qtd_jogador * PRECO_JOGADOR) + (qtd_torcedor * PRECO_TORCEDOR)
    tipos_camisas = ["Jogador"] * qtd_jogador + ["Torcedor"] * qtd_torcedor
    
    st.subheader(f"💰 Valor total do pedido: **R$ {preco_total},00**")
    st.subheader("2. Detalhes de cada camisa")

    nomes_camisa, numeros_camisa, tamanhos_camisa = [], [], []
    for i, tipo in enumerate(tipos_camisas):
        with st.container(border=True):
            st.markdown(f"**Camisa #{i+1} (Modelo: {tipo})**")
            c1, c2, c3 = st.columns(3)
            with c1:
                nome = st.text_input(f"Nome na camisa #{i+1}", key=f"nome_{i}")
            with c2:
                numero = st.number_input(f"Número (0-99)", min_value=0, max_value=99, key=f"num_{i}")
            with c3:
                tamanho = st.selectbox("Tamanho", ["P", "M", "G", "GG", "G1", "G2", "G3", "G4", "G5"], key=f"tamanho_{i}")
            
            nomes_camisa.append(nome)
            numeros_camisa.append(numero)
            tamanhos_camisa.append(tamanho)
            
            if tipo == "Jogador" and numero in JOGADORES_FIXOS:
                st.warning(f"⚠️ Atenção: O número {numero} já pertence ao jogador {JOGADORES_FIXOS[numero]}.")

    st.divider()
    with st.form("finalizar_compra_form"):
        st.subheader("✉️ 3. Seus dados e forma de pagamento")
        
        nome_comprador = st.text_input("Seu nome completo")
        email_comprador = st.text_input("Seu melhor e-mail para contato")
        
        st.divider()
        st.markdown("#### **Escolha a forma de pagamento:**")

        with st.expander("Opção 1: Pagar com PIX (Sem taxas)", expanded=True):
            st.markdown(f"### Valor total: **R$ {preco_total},00**")
            st.markdown("Favorecido: **Hassan Marques Nehme**")
            st.markdown("Chave PIX (Telefone):")
            st.code("1194991465")
            st.info("Após realizar o pagamento via PIX, anexe o comprovante logo abaixo.")

        tupla_compra = (qtd_jogador, qtd_torcedor)
        link_pagamento = LINKS_PAGAMENTO.get(tupla_compra, '#')

        if link_pagamento != '#':
            with st.expander("Opção 2: Pagar com Link (Cartão de Crédito com taxas)"):
                st.markdown(f"🔗 [**CLIQUE AQUI PARA ACESSAR O LINK DE PAGAMENTO**]({link_pagamento})", unsafe_allow_html=True)
                st.warning("""**ATENÇÃO:** O pagamento através do link tem a **taxa da operadora**. Caso opte por **parcelar**, haverá também a **taxa de parcelamento** cobrada no momento da transação.""")
                st.info("Após realizar o pagamento pelo link, anexe o comprovante logo abaixo.")
        else:
            st.error("Combinação de camisas inválida para gerar link de pagamento. Contacte o administrador.")

        st.divider()
        comprovante = st.file_uploader("Anexe o comprovante de pagamento aqui (seja do PIX ou do Link)", type=["png", "jpg", "jpeg", "pdf"])
        
        st.divider()
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            finalizar_btn = st.form_submit_button("✅ Finalizar Compra", use_container_width=True, disabled=(link_pagamento=='#'))
        with col_btn2:
            nova_compra_btn = st.form_submit_button("🔄 Finalizar e Nova Compra", use_container_width=True, disabled=(link_pagamento=='#'))

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
                        "nome_comprador": nome_comprador,
                        "detalhes_pedido": ", ".join([f"{nome} ({tipo})" for nome, tipo in zip(nomes_camisa, tipos_camisas)]),
                        "email_comprador": email_comprador,
                        "tamanho": ", ".join(tamanhos_camisa),
                        "quantidade": len(tipos_camisas),
                        "valor_total": preco_total,
                        "status_pagamento": "Aguardando Confirmação",
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
                    
                    detalhes_camisas_email = "\n".join([f"  - Camisa {i+1} ({tipos_camisas[i]}): Nome '{nomes_camisa[i]}', Nº {numeros_camisa[i]}, Tam. {tamanhos_camisa[i]}" for i in range(len(tipos_camisas))])

                    # --- 1. Prepara e envia e-mail para o ADMINISTRADOR ---
                    destinatarios_admin = [d.strip() for d in EMAIL_DESTINATARIO.split(",")]
                    assunto_admin = f"Novo Pedido de Camisa 2025 - {nome_comprador}"
                    corpo_admin = f"""
Novo pedido de camisas da temporada 2025 recebido!

DADOS DO COMPRADOR:
- Nome: {nome_comprador}
- E-mail: {email_comprador}
- Valor Base (PIX): R$ {preco_total},00
- Combinação: {qtd_jogador} Jogador / {qtd_torcedor} Torcedor

DETALHES DO PEDIDO:
{detalhes_camisas_email}

O comprovante de pagamento e o CSV atualizado de todos os pedidos estão em anexo.
Verifique o pagamento e atualize o status no painel do Supabase.
"""
                    enviar_email_notificacao(EMAIL_REMETENTE, EMAIL_SENHA, destinatarios_admin, assunto_admin, corpo_admin, comprovante, caminho_csv)
                    
                    # --- 2. <<< NOVO: Prepara e envia e-mail para o COMPRADOR >>> ---
                    primeiro_nome = nome_comprador.split()[0]
                    assunto_comprador = "✅ Pedido de Camisas Chapiuski 2025 Confirmado!"
                    detalhes_html = "".join([f"<li><b>Camisa {i+1} ({tipos_camisas[i]}):</b> Nome '{nomes_camisa[i]}', Número {numeros_camisa[i]}, Tamanho {tamanhos_camisa[i]}</li>" for i in range(len(tipos_camisas))])
                    
                    corpo_comprador = f"""
                    <html>
                    <body style="font-family: sans-serif;">
                        <h2>Olá, {primeiro_nome}!</h2>
                        <p>Seu pedido para as camisas da temporada 2025 do Chapiuski foi recebido com sucesso. 💛🖤</p>
                        <p>Estamos confirmando o seu pagamento. Você será notificado sobre os próximos passos.</p>
                        <hr>
                        <h3>Resumo do seu Pedido:</h3>
                        <ul>
                            {detalhes_html}
                        </ul>
                        <p><b>Valor Total (base), sem taxas:</b> R$ {preco_total},00</p>
                        <hr>
                        <p>Obrigado por fazer parte da nossa história!</p>
                        <p><b>1, 2, 4... Chapiuski!!!</b></p>
                    </body>
                    </html>
                    """
                    enviar_email_para_comprador(EMAIL_REMETENTE, EMAIL_SENHA, email_comprador, assunto_comprador, corpo_comprador)

                    # --- Mensagem de sucesso para o usuário ---
                    if finalizar_btn:
                        st.success(f"✅ Compra finalizada com sucesso! Obrigado, {primeiro_nome}!")
                        st.info("Seu pedido para as camisas da temporada 2025 do Chapiuski foi recebido com sucesso. 💛🖤. Estamos confirmando o seu pagamento. Você será notificado sobre os próximos passos.")
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