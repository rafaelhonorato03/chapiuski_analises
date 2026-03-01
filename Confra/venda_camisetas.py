import os
import smtplib
import pandas as pd
from datetime import datetime
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders

import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv

# ==== Tratamento de Caminhos ====
PASTA_ATUAL = os.path.dirname(__file__)
def get_p(file): return os.path.join(PASTA_ATUAL, file)

# ==== Configurações ====
st.set_page_config(layout="centered", page_title="Chapiuski 2026", page_icon="👕")
load_dotenv()
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

EMAIL_REMETENTE = os.getenv("EMAIL_REMETENTE")
EMAIL_SENHA = os.getenv("EMAIL_SENHA")
EMAIL_DESTINATARIO = os.getenv("EMAIL_DESTINATARIO") # E-mail do administrador (você)

# Links PagSeguro (Com Taxas)
LINKS_CARTAO = {
    (1, 0, 0): ("R$ 52,63", "https://pag.ae/81xQ1jT7L"),
    (0, 1, 0): ("R$ 84,21", "https://pag.ae/81xQ1Z5Vr"),
    (0, 0, 1): ("R$ 84,21", "https://pag.ae/81xQ1Z5Vr"),
    (1, 1, 0): ("R$ 136,83", "https://pag.ae/81xQ2yHm5"),
    (1, 0, 1): ("R$ 136,83", "https://pag.ae/81xQ2yHm5"),
    (0, 1, 1): ("R$ 168,41", "https://pag.ae/81xQ2ZREs"),
    (2, 0, 0): ("R$ 105,26", "https://pag.ae/81xQ3H_-u"),
    (0, 2, 0): ("R$ 168,41", "https://pag.ae/81xQ2ZREs"),
    (0, 0, 2): ("R$ 168,41", "https://pag.ae/81xQ2ZREs"),
    (2, 2, 0): ("R$ 273,66", "https://pag.ae/81xQ47U-u"),
    (2, 0, 2): ("R$ 273,66", "https://pag.ae/81xQ47U-u"),
    (0, 2, 2): ("R$ 336,81", "https://pag.ae/81xQ4QRsR"),
    (1, 1, 1): ("R$ 205,25", "https://pag.ae/81xQ576S5"),
    (1, 1, 2): ("R$ 289,45", "https://pag.ae/81xQ5uSev"),
    (1, 2, 1): ("R$ 275,00", "https://pag.ae/81xQ5uSev"),
    (1, 2, 2): ("R$ 373,65", "https://pag.ae/81xQ64KTL"),
    (2, 2, 2): ("R$ 410,49", "https://pag.ae/81xQ6rE65"),
}

def montar_resumo_pedido(dados):
    resumo = f"""
    📦 DETALHES DO PEDIDO - CHAPIUSKI 2026
    --------------------------------------
    Comprador: {dados['nome_comprador']}
    WhatsApp: {dados['whatsapp_comprador']}
    E-mail: {dados['email_comprador']}
    Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}
    
    ITENS:
    - Bonés: {dados['qtd_bone_avulso']}
    - Camisetas Totais: {dados['qtd_camiseta_avulsa']}
    
    VALOR TOTAL: R$ {dados['valor_total']:.2f}
    --------------------------------------
    """
    # Adiciona detalhes de artes/tamanhos se houver
    for k, v in dados.items():
        if 'arte' in k or 'tam' in k:
            resumo += f"{k.replace('_', ' ').title()}: {v}\n"
    
    return resumo

def enviar_emails(dados, arquivo):
    resumo = montar_resumo_pedido(dados)
    
    # 1. E-mail para o Administrador (com anexo e planilha)
    msg_admin = MIMEMultipart()
    msg_admin['Subject'] = f"✅ NOVO PEDIDO: {dados['nome_comprador']}"
    msg_admin['From'] = EMAIL_REMETENTE
    msg_admin['To'] = EMAIL_DESTINATARIO
    msg_admin.attach(MIMEText(resumo, 'plain'))
    
    # 2. E-mail para o Comprador (simples)
    msg_cliente = MIMEMultipart()
    msg_cliente['Subject'] = "Confirmação de Pedido - Chapiuski 2026"
    msg_cliente['From'] = EMAIL_REMETENTE
    msg_cliente['To'] = dados['email_comprador']
    texto_cliente = f"Olá {dados['nome_comprador']},\n\nRecebemos seu pedido!\n\n{resumo}\n\nObrigado por fazer parte do Chapiuski!"
    msg_cliente.attach(MIMEText(texto_cliente, 'plain'))

    # Anexo do comprovante para o Admin
    if arquivo:
        part = MIMEBase('application', "octet-stream")
        part.set_payload(arquivo.getvalue())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="comprovante.png"')
        msg_admin.attach(part)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(EMAIL_REMETENTE, EMAIL_SENHA)
        # Envia para você
        server.sendmail(EMAIL_REMETENTE, EMAIL_DESTINATARIO.split(","), msg_admin.as_string())
        # Envia para o cliente
        server.sendmail(EMAIL_REMETENTE, [dados['email_comprador']], msg_cliente.as_string())

# ==== Interface Streamlit ====
st.image(get_p("Central.jpeg"), use_container_width=True)
st.title("👕 Chapiuski 2026")

st.subheader("1. Escolha as quantidades")
col_q1, col_q2, col_q3 = st.columns(3)
with col_q1: q_bone = st.number_input("Bonés (R$ 50)", 0, 2, 0)
with col_q2: q_comf = st.number_input("Comfort (R$ 80)", 0, 2, 0)
with col_q3: q_over = st.number_input("Oversized (R$ 80)", 0, 2, 0)

dados_venda = {}

if q_bone > 0:
    st.divider()
    st.image(get_p("bone.jpeg"), width=200, caption="Modelo Boné")

if q_comf > 0 or q_over > 0:
    st.divider()
    st.info("📏 Confira as medidas nas imagens abaixo antes de selecionar:")
    col_t1, col_t2 = st.columns(2)
    with col_t1: st.image(get_p("Tam Confort.jpeg"), caption="Tabela Comfort")
    with col_t2: st.image(get_p("Tam Oversized.jpeg"), caption="Tabela Oversized")

    if q_comf > 0:
        for i in range(q_comf):
            with st.expander(f"Configurar Comfort #{i+1}", expanded=True):
                c1, c2 = st.columns(2)
                dados_venda[f"comf_{i+1}_arte"] = c1.radio(f"Arte", ["Arte 1", "Arte 2"], key=f"ac{i}")
                dados_venda[f"comf_{i+1}_tam"] = c2.selectbox(f"Tamanho", ["P", "M", "G", "GG", "XGG"], key=f"tc{i}")

    if q_over > 0:
        for i in range(q_over):
            with st.expander(f"Configurar Oversized #{i+1}", expanded=True):
                c1, c2 = st.columns(2)
                dados_venda[f"over_{i+1}_arte"] = c1.radio(f"Arte", ["Arte 1", "Arte 2"], key=f"ao{i}")
                dados_venda[f"over_{i+1}_tam"] = c2.selectbox(f"Tamanho", ["P", "M", "G", "GG", "XGG"], key=f"to{i}")

# Checkout
total_tupla = (q_bone, q_comf, q_over)
if any(total_tupla):
    st.divider()
    if total_tupla == (1, 1, 1): valor_final = 195.0
    elif total_tupla == (2, 2, 2): valor_final = 390.0
    else: valor_final = (q_bone * 50.0) + (q_comf * 80.0) + (q_over * 80.0)

    st.success(f"### 🎯 Total no Pix: R$ {valor_final:.2f}")
    
    info_pg = LINKS_CARTAO.get(total_tupla)
    if info_pg:
        st.write(f"💳 Cartão/Boleto: {info_pg[0]}")
        st.link_button("🔗 Pagar no Cartão", info_pg[1], use_container_width=True)
    
    st.markdown("**Chave Pix:** `11994991465` (Hassan Marques)")

    with st.form("checkout"):
        n = st.text_input("Nome Completo")
        email_cliente = st.text_input("E-mail para confirmação")
        w = st.text_input("WhatsApp (DDD + Número)")
        comp = st.file_uploader("Upload do Comprovante (Pix ou Cartão)", type=["png", "jpg", "pdf"])
        
        if st.form_submit_button("Finalizar Pedido"):
            if n and email_cliente and w and comp:
                try:
                    p = {
                        "nome_comprador": n, "email_comprador": email_cliente,
                        "whatsapp_comprador": w, "qtd_bone_avulso": q_bone,
                        "qtd_camiseta_avulsa": q_comf + q_over, "valor_total": valor_final,
                        "created_at": datetime.now().isoformat(), **dados_venda
                    }
                    supabase.table("compra_confra").insert(p).execute()
                    enviar_emails(p, comp)
                    st.success("Tudo pronto! Você e a gente recebemos a confirmação por e-mail.")
                    st.balloons()
                except Exception as e: st.error(f"Erro: {e}")
            else: st.warning("Por favor, preencha todos os campos e anexe o comprovante.")