import os
import smtplib
import pandas as pd
import io
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

# Links PagSeguro
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
    (1, 2, 1): ("R$ 289,45", "https://pag.ae/81xQ5uSev"),
    (1, 2, 2): ("R$ 373,65", "https://pag.ae/81xQ64KTL"),
    (2, 2, 2): ("R$ 410,49", "https://pag.ae/81xQ6rE65"),
    (2, 1, 1): ("R$ 257,87", "https://pag.ae/81xQ6KEjv"),
    (2, 1, 2): ("R$ 342,07", "https://pag.ae/81xQ7gX7R"),
    (2, 2, 1): ("R$ 342,07", "https://pag.ae/81xQ7gX7R"),
}

def enviar_emails(dados_atuais, arquivo_comprovante):
    try:
        # Busca apenas a partir do ID 54
        resposta = supabase.table("compra_confra").select("*").gte("id", 54).execute()
        historico = resposta.data
        
        if historico:
            df_historico = pd.DataFrame(historico)
            
            # Seleciona apenas as colunas pertinentes (ignorando metadados internos se existirem)
            colunas_finais = [
                'id', 'created_at', 'nome_comprador', 'whatsapp_comprador', 'email_comprador',
                'qtd_bone_avulso', 'qtd_confort', 'qtd_over', 'valor_total',
                'confort_1_arte', 'confort_1_tam', 'confort_2_arte', 'confort_2_tam',
                'over_1_arte', 'over_1_tam', 'over_2_arte', 'over_2_tam'
            ]
            # Garante que só tentará filtrar colunas que realmente existem no DataFrame
            df_filtrado = df_historico[[c for c in colunas_finais if c in df_historico.columns]]
            
            csv_buffer = io.StringIO()
            df_filtrado.to_csv(csv_buffer, index=False, sep=';', encoding='utf-8-sig')
            
            resumo = f"""
            ✅ NOVO PEDIDO REGISTRADO - CHAPIUSKI 2026
            ------------------------------------------
            Comprador Atual: {dados_atuais['nome_comprador']}
            Valor: R$ {dados_atuais['valor_total']:.2f}
            
            📎 O arquivo 'historico_vendas.csv' em anexo contém 
            os pedidos realizados a partir do ID 54.
            ------------------------------------------
            """
            
            msg = MIMEMultipart()
            msg['Subject'] = f"📈 NOVO PEDIDO + HISTÓRICO: {dados_atuais['nome_comprador']}"
            msg['From'] = EMAIL_REMETENTE
            msg['To'] = EMAIL_DESTINATARIO
            msg.attach(MIMEText(resumo, 'plain'))

            part_csv = MIMEBase('application', "octet-stream")
            part_csv.set_payload(csv_buffer.getvalue().encode('utf-8-sig'))
            encoders.encode_base64(part_csv)
            part_csv.add_header('Content-Disposition', 'attachment; filename="historico_vendas.csv"')
            msg.attach(part_csv)

            if arquivo_comprovante:
                part_img = MIMEBase('application', "octet-stream")
                part_img.set_payload(arquivo_comprovante.getvalue())
                encoders.encode_base64(part_img)
                part_img.add_header('Content-Disposition', 'attachment; filename="comprovante.png"')
                msg.attach(part_img)

            destinatarios = [d.strip() for d in EMAIL_DESTINATARIO.split(",")]
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(EMAIL_REMETENTE, EMAIL_SENHA)
                server.sendmail(EMAIL_REMETENTE, destinatarios, msg.as_string())
                server.sendmail(EMAIL_REMETENTE, [dados_atuais['email_comprador']], msg.as_string())
            
    except Exception as e:
        st.error(f"Erro ao gerar histórico/enviar e-mail: {e}")

# ==== Interface ====
exibir_imagem_segura("Central.jpeg")
st.title("👕🧢 Linha Casual 2026")

# 1. Quantidades
st.subheader("1. Escolha as quantidades")
col_q1, col_q2, col_q3 = st.columns(3)
with col_q1: q_bone = st.number_input("Boné (R$ 50)", 0, 2, 0)
with col_q2: q_comfort = st.number_input("Comfort (R$ 80)", 0, 2, 0)
with col_q3: q_over = st.number_input("Oversized (R$ 80)", 0, 2, 0)

dados_venda = {}

if q_bone > 0:
    st.divider()
    exibir_imagem_segura("BONE.jpeg")

if q_comfort > 0 or q_over > 0:
    st.divider()
    st.subheader("🖼️ Opções de Arte")
    if q_comfort > 0:
        st.write("**Artes para modelo Comfort:**")
        col_c1, col_c2 = st.columns(2)
        with col_c1: exibir_imagem_segura("comfort+degrade.jpeg")
        with col_c2: exibir_imagem_segura("comfort+logo.jpeg")
    if q_over > 0:
        st.write("**Artes para modelo Oversized:**")
        col_o1, col_o2 = st.columns(2)
        with col_o1: exibir_imagem_segura("over+degrade.jpeg")
        with col_o2: exibir_imagem_segura("over+logo.jpeg")
    
    st.divider()
    st.subheader("2. Tamanhos e Personalização")
    col_t1, col_t2 = st.columns(2)
    with col_t1: exibir_imagem_segura("tam_comfort.jpeg")
    with col_t2: exibir_imagem_segura("tam_over.jpeg")

    if q_comfort > 0:
        for i in range(q_comfort):
            with st.expander(f"Configurar Comfort #{i+1}", expanded=True):
                c1, c2 = st.columns(2)
                dados_venda[f"confort_{i+1}_arte"] = c1.radio(f"Arte (C#{i+1})", ["Comfort Arte Degradê", "Comfort Arte Logo"], key=f"ac{i}")
                dados_venda[f"confort_{i+1}_tam"] = c2.selectbox(f"Tam (C#{i+1})", ["P", "M", "G", "GG", "XGG"], key=f"tc{i}")

    if q_over > 0:
        for i in range(q_over):
            with st.expander(f"Configurar Oversized #{i+1}", expanded=True):
                c1, c2 = st.columns(2)
                dados_venda[f"over_{i+1}_arte"] = c1.radio(f"Arte (O#{i+1})", ["Oversized Degradê", "Oversized Logo"], key=f"ao{i}")
                dados_venda[f"over_{i+1}_tam"] = c2.selectbox(f"Tam (O#{i+1})", ["P", "M", "G", "GG", "XGG"], key=f"to{i}")

# ==== Lógica de Preço Inteligente ====
total_tupla = (q_bone, q_comfort, q_over)

# ==== Lógica de Preço Inteligente: 1 Boné + 2 Camisetas ====
total_tupla = (q_bone, q_comfort, q_over)

if any(total_tupla):
    st.divider()
    
    total_camisetas = q_comfort + q_over
    
    # O Kit promocional de R$ 195 é 1 Boné + 2 Camisetas.
    # Calculamos quantos desses trios conseguimos formar:
    num_kits = min(q_bone, total_camisetas // 2)
    
    # O que sobra do Boné após formar os kits
    sobra_bone = q_bone - num_kits
    
    # O que sobra de camisetas após formar os kits
    sobra_camisetas = total_camisetas - (num_kits * 2)
    
    # Cálculo:
    # (Kits * 195) + (Bonés que sobraram * 50) + (Camisetas que sobraram * 80)
    valor_final = (num_kits * 195.0) + (sobra_bone * 50.0) + (sobra_camisetas * 80.0)
    
    # Exibição
    if num_kits > 0:
        st.success(f"### 🎯 Total no Pix: R$ {valor_final:.2f} ({num_kits} Kit(s) aplicado!)")
    else:
        st.success(f"### 🎯 Total no Pix: R$ {valor_final:.2f}")

    # Link do Cartão (Busca na sua tabela LINKS_CARTAO)
    info_pg = LINKS_CARTAO.get(total_tupla)
    if info_pg:
        st.write(f"💳 Cartão/Boleto: {info_pg[0]}")
        st.link_button("🔗 Pagar no Cartão", info_pg[1], use_container_width=True)
    
    st.markdown("**Chave Pix:** `11994991465` (Hassan Marques)")

    st.warning("""
    ⚠️ **Informação Importante:** Uma vez que o link for finalizado, acabou aquela compra. Não podendo comprar em parcelas. 
    *Exemplo: Comprou 1 Camiseta e 1 Boné e finalizou o link, se quiser comprar mais uma camiseta não terá aplicação de desconto.*
    """)

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
                        "qtd_bone_avulso": q_bone, "qtd_confort": q_comfort, "qtd_over": q_over,
                        "valor_total": float(valor_final), "created_at": datetime.now().isoformat(),
                        **dados_venda
                    }
                    supabase.table("compra_confra").insert(p).execute()
                    enviar_emails(p, comp)
                    st.success("Pedido registrado e histórico enviado!")
                    st.balloons()
                except Exception as ex: st.error(f"Erro: {ex}")
            else: st.warning("Preencha tudo!")