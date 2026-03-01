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
PASTA_ATUAL = os.path.dirname(os.path.abspath(__file__))
def get_p(file): return os.path.join(PASTA_ATUAL, file)

def exibir_imagem_segura(nome_arquivo, cap="", w=None):
    caminho = get_p(nome_arquivo)
    if os.path.exists(caminho):
        st.image(caminho, caption=cap, width=w, use_container_width=(w is None))
    else:
        st.error(f"⚠️ Arquivo não encontrado: {nome_arquivo}")

# ==== Configurações ====
st.set_page_config(layout="centered", page_title="Chapiuski 2026", page_icon="👕")
load_dotenv()
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

EMAIL_REMETENTE = os.getenv("EMAIL_REMETENTE")
EMAIL_SENHA = os.getenv("EMAIL_SENHA")
EMAIL_DESTINATARIO = os.getenv("EMAIL_DESTINATARIO")

# Links PagSeguro (Mantenha seu dicionário atual aqui)
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
    (2, 1, 1): ("R$ 257,87", "https://pag.ae/81xQ6KEjv"),
    (2, 1, 2): ("R$ 342,07", "https://pag.ae/81xQ7gX7R"),
    (2, 2, 1): ("R$ 342,07", "https://pag.ae/81xQ7gX7R"),
}

def enviar_emails(dados, arquivo):
    resumo = f"""
    📦 DETALHES DO PEDIDO - CHAPIUSKI 2026
    --------------------------------------
    Comprador: {dados['nome_comprador']}
    WhatsApp: {dados['whatsapp_comprador']}
    E-mail: {dados['email_comprador']}
    Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}
    
    VALOR TOTAL: R$ {dados['valor_total']:.2f}
    
    ITENS:
    - Bonés: {dados['qtd_bone_avulso']}
    - Camisetas Comfort: {dados.get('qtd_comf', 0)}
    - Camisetas Oversized: {dados.get('qtd_over', 0)}
    --------------------------------------
    """
    msg_admin = MIMEMultipart()
    msg_admin['Subject'] = f"✅ NOVO PEDIDO: {dados['nome_comprador']}"
    msg_admin['From'] = EMAIL_REMETENTE
    msg_admin['To'] = EMAIL_DESTINATARIO
    msg_admin.attach(MIMEText(resumo, 'plain'))

    if arquivo:
        part = MIMEBase('application', "octet-stream")
        part.set_payload(arquivo.getvalue())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="comprovante.png"')
        msg_admin.attach(part)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(EMAIL_REMETENTE, EMAIL_SENHA)
        server.sendmail(EMAIL_REMETENTE, EMAIL_DESTINATARIO.split(","), msg_admin.as_string())
        server.sendmail(EMAIL_REMETENTE, [dados['email_comprador']], msg_admin.as_string())

# ==== Interface ====
exibir_imagem_segura("Central.jpeg")
st.title("👕 Chapiuski 2026")

st.subheader("1. Escolha as quantidades")
col_q1, col_q2, col_q3 = st.columns(3)
with col_q1: q_bone = st.number_input("Bonés (R$ 50)", 0, 2, 0)
with col_q2: q_comf = st.number_input("Comfort (R$ 80)", 0, 2, 0)
with col_q3: q_over = st.number_input("Oversized (R$ 80)", 0, 2, 0)

dados_venda = {}

if q_bone > 0:
    st.divider()
    exibir_imagem_segura("BONE.jpeg", cap="Modelo Boné", w=200)

if q_comf > 0 or q_over > 0:
    st.divider()
    exibir_imagem_segura("Tam Confort.jpeg", cap="Tabela Comfort")
    exibir_imagem_segura("Tam Oversized.jpeg", cap="Tabela Oversized")

    if q_comf > 0:
        for i in range(q_comf):
            with st.expander(f"Comfort #{i+1}", expanded=True):
                c1, c2 = st.columns(2)
                dados_venda[f"comf_{i+1}_arte"] = c1.radio(f"Arte", ["Arte 1", "Arte 2"], key=f"ac{i}")
                dados_venda[f"comf_{i+1}_tam"] = c2.selectbox(f"Tam", ["P", "M", "G", "GG", "XGG"], key=f"tc{i}")

    if q_over > 0:
        for i in range(q_over):
            with st.expander(f"Oversized #{i+1}", expanded=True):
                c1, c2 = st.columns(2)
                dados_venda[f"over_{i+1}_arte"] = c1.radio(f"Arte", ["Arte 1", "Arte 2"], key=f"ao{i}")
                dados_venda[f"over_{i+1}_tam"] = c2.selectbox(f"Tam", ["P", "M", "G", "GG", "XGG"], key=f"to{i}")

# ==== Lógica de Preço Inteligente ====
total_tupla = (q_bone, q_comf, q_over)

if any(total_tupla):
    st.divider()
    
    # Descobre quantos Kits completos de 195 existem na seleção
    num_kits = min(q_bone, q_comf, q_over)
    
    # Sobras (o que não entrou no kit)
    sobra_bone = q_bone - num_kits
    sobra_comf = q_comf - num_kits
    sobra_over = q_over - num_kits
    
    # Cálculo Final
    valor_final = (num_kits * 195.0) + (sobra_bone * 50.0) + (sobra_comf * 80.0) + (sobra_over * 80.0)
    
    if num_kits > 0:
        st.success(f"### 🎯 Total no Pix: R$ {valor_final:.2f} ({num_kits} Kit(s) aplicado!)")
    else:
        st.success(f"### 🎯 Total no Pix: R$ {valor_final:.2f}")

    info_pg = LINKS_CARTAO.get(total_tupla)
    if info_pg:
        st.write(f"💳 Cartão/Boleto: {info_pg[0]}")
        st.link_button("🔗 Pagar no Cartão", info_pg[1], use_container_width=True)
    
    st.markdown("**Chave Pix:** `11994991465` (Hassan Marques)")

    with st.form("checkout"):
        n = st.text_input("Nome Completo")
        e = st.text_input("E-mail")
        w = st.text_input("WhatsApp")
        comp = st.file_uploader("Upload do Comprovante", type=["png", "jpg", "pdf"])
        
        if st.form_submit_button("Finalizar Pedido"):
            if n and e and w and comp:
                try:
                    p = {
                        "nome_comprador": n, "email_comprador": e, "whatsapp_comprador": w,
                        "qtd_bone_avulso": q_bone, "qtd_camiseta_avulsa": q_comf + q_over,
                        "valor_total": valor_final, "created_at": datetime.now().isoformat(),
                        "qtd_comf": q_comf, "qtd_over": q_over, **dados_venda
                    }
                    supabase.table("compra_confra").insert(p).execute()
                    enviar_emails(p, comp)
                    st.success("Pedido registrado!")
                    st.balloons()
                except Exception as ex: st.error(f"Erro: {ex}")
            else: st.warning("Preencha tudo!")