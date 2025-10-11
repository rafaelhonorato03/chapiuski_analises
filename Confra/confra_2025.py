import os
import re
import smtplib
import time
from datetime import datetime
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
    page_title="Ingressos Confra Chapiuski 2025",
    page_icon="🍻"
)

# Bloco para exibir a mensagem de sucesso que sobrevive ao rerun da página
if "mensagem_sucesso" in st.session_state:
    st.success(st.session_state.mensagem_sucesso, icon="🎉")
    # Limpa a mensagem da memória para não exibi-la novamente
    del st.session_state.mensagem_sucesso
    # Adiciona um pequeno atraso para melhor experiência
    time.sleep(0.5)

# ==== Configurações Iniciais e Variáveis de Ambiente ====
load_dotenv() 

# Conexão com o Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configurações de E-mail
EMAIL_REMETENTE = os.getenv("EMAIL_REMETENTE")
EMAIL_SENHA = os.getenv("EMAIL_SENHA")
EMAIL_DESTINATARIO = os.getenv("EMAIL_DESTINATARIO") # E-mails da organização (admin)

# Arquivo CSV para backup local
arquivo_csv = os.path.join(os.path.dirname(__file__), "compras_confra.csv")

# ==== Constantes e Mapeamentos do Aplicativo ====
PRECOS_PIX = {
    "Confra": 75.00,
    "Copo": 40.00,
    "Kit": 105.00 # Confra + Copo (desconto aplicado)
}

PRECOS_CREDITO = {
    "Confra": 78.50,
    "Copo": 42.00,
    "Kit": 110.50 # Confra + Copo (desconto aplicado)
}

# Mapeamento para Link de Pagamento no Crédito (Chave: (qtd_confra, qtd_copo))
LINKS_PAGAMENTO = {
    (1, 0): "https://pag.ae/8159KNAb3",
    (2, 0): "https://pag.ae/8159LcRNL",
    (3, 0): "https://pag.ae/8159LADX2",
    (0, 1): "https://pag.ae/8159LZ5um",
    (0, 2): "https://pag.ae/8159MhksL",
    (0, 3): "https://pag.ae/8159MA5-m",
    (1, 1): "https://pag.ae/8159N84-m",
    (2, 2): "https://pag.ae/8159Num4o",
    (3, 3): "https://pag.ae/8159NZ_S1",
    (1, 2): "https://pag.ae/8159PkFCJ",
    (1, 3): "https://pag.ae/8159PJpG5",
    (2, 1): "https://pag.ae/8159Q4KEo",
    (2, 3): "https://pag.ae/8159QtwQm",
    (3, 1): "https://pag.ae/8159QQnNG",
    (3, 2): "https://pag.ae/8159Ranw3"
}

# Estoque total (Exemplo - ajuste conforme a necessidade real)
ESTOQUE_MAX_CONFRA = 100
ESTOQUE_MAX_COPO = 100
LIMITE_POR_PEDIDO = 3 # Limite de ingressos/copos por tipo por pedido

# === Função para buscar total de ingressos vendidos (Simplificada, pois não há lotes) ===
@st.cache_data(ttl=600) # Armazena o resultado por 10 minutos
def buscar_total_vendido():
    """Busca o total de ingressos (Confra) e Copos vendidos no Supabase."""
    try:
        # Nota: A tabela no Supabase deve se chamar "compra_confra" conforme a refatoração anterior
        response = supabase.table("compra_confra").select("qtd_confra", "qtd_copo").execute()
        if response.data:
            total_confra = sum(item["qtd_confra"] for item in response.data)
            total_copo = sum(item["qtd_copo"] for item in response.data)
            return total_confra, total_copo
        return 0, 0
    except Exception as e:
        # st.error(f"Erro ao buscar estoque no banco de dados: {e}") # Comentar para não poluir o app
        return 0, 0

total_confra_vendidos, total_copo_vendidos = buscar_total_vendido()
estoque_disponivel_confra = max(0, ESTOQUE_MAX_CONFRA - total_confra_vendidos)
estoque_disponivel_copo = max(0, ESTOQUE_MAX_COPO - total_copo_vendidos)

# ==== Funções Auxiliares (Reutilizadas e adaptadas) ====
def email_valido(email):
    """Verifica se o formato do e-mail é válido."""
    if email:
        return re.match(r"[^@]+@[^@]+\.[^@]+", email)
    return False

def whatsapp_valido(whatsapp):
    """Verifica se o WhatsApp tem um formato minimamente válido (10 ou 11 dígitos)."""
    if whatsapp:
        numeros = re.sub(r'\D', '', whatsapp)
        return len(numeros) >= 10
    return False

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

def sincronizar_csv_com_supabase(nome_tabela, caminho_csv):
    """Sincroniza os dados do Supabase para o CSV local."""
    try:
        response = supabase.table(nome_tabela).select("*").order("created_at", desc=True).execute()
        if response.data:
            df = pd.DataFrame(response.data)
            df.to_csv(caminho_csv, index=False, encoding="utf-8-sig")
            return caminho_csv
        else:
            # Colunas ajustadas para refletir a lista de nomes no copo
            colunas = ["nome_comprador", "email_comprador", "whatsapp_comprador", "qtd_confra", "qtd_copo", "nomes_copo", "valor_pix", "valor_credito", "link_pagamento", "nomes_participantes", "documentos_participantes", "created_at"]
            df = pd.DataFrame(columns=colunas)
            df.to_csv(caminho_csv, index=False, encoding="utf-8-sig")
            return caminho_csv
    except Exception as e:
        st.error(f"❌ Erro ao sincronizar CSV com Supabase: {e}")
        return None

# ==== Interface do Streamlit ====
st.markdown("<h1 style='text-align: center;'>🎉 Confra Chapiuski 2025 🎉</h1>", unsafe_allow_html=True)
st.markdown("<h4 style='text-align: center; color: #333;'>Ingressos e Copos Personalizados</h4>", unsafe_allow_html=True)

# ⭐️ IMAGEM GERAL DO EVENTO - TAMANHO MENOR
try:
    col_img_main1, col_img_main2, col_img_main3 = st.columns([1,2,1])
    with col_img_main2: # Centraliza a imagem principal
        st.image(r'Confra\CHAP.jpg', caption='Confra Chapiuski 2025', width=500) 
except Exception:
    st.warning("⚠️ Imagem 'CHAP.jpg' não encontrada. Verifique o caminho do arquivo.")

st.divider()

st.info(f"""
    **📅 Data:** 06/12/2025 | **⏰ Horário:** 16h às 22h | **📍 Local:** Penha Society
    **⚠️ Vendas:** De 15/10/2025 até 20/11/2025.
""")

st.markdown("""
### Informações do Evento
- **Futebol:** 14h às 16h
- **Open Food:** Churrasco à vontade.
- **Bebidas:** Bar do Fausto (Chopp, Vodka, Cachaça, Refrigerantes, Sucos e Água à vontade).
- **Atração:** Pagode ao vivo (19h às 22h).
- **Extra:** Premiação Anual.

---
### Valores e Itens
| Item | Preço PIX (Com Desconto) | Preço Crédito (Com Taxas) |
| :--- | :--- | :--- |
| **Ingresso (Confra)** | R$ 75,00 | R$ 78,50 |
| **Copo Personalizado** | R$ 40,00 | R$ 42,00 |
| **Kit (Ingresso + Copo)** | R$ 105,00 | R$ 110,50 |
""")

if estoque_disponivel_confra == 0 and estoque_disponivel_copo == 0:
    st.warning("🚫 Ingressos e Copos Esgotados!")
    st.stop()
elif estoque_disponivel_confra == 0:
    st.warning("🚫 Ingressos Esgotados!")

st.divider()

st.subheader("1. Selecione a quantidade")

# ⭐️ REPOSICIONAMENTO DA IMAGEM DO COPO
col_copo_img_prev1, col_copo_img_prev2, col_copo_img_prev3 = st.columns([1,2,1])
with col_copo_img_prev2:
    try:
        st.image(r'Confra\COPO.jpg', caption='Copo Personalizado da Confra', width=200) 
    except Exception:
        st.warning("⚠️ Imagem 'COPO.jpg' não encontrada.")

# Campos de input de quantidade
col_confra, col_copo = st.columns(2)

with col_confra:
    qtd_confra = st.number_input(
        f"Ingressos (Confra) - Disponível: {estoque_disponivel_confra}",
        min_value=0,
        max_value=min(LIMITE_POR_PEDIDO, estoque_disponivel_confra),
        value=0,
        step=1,
        key="qtd_confra"
    )

with col_copo:
    qtd_copo = st.number_input(
        f"Copos Personalizados - Disponível: {estoque_disponivel_copo}",
        min_value=0,
        max_value=min(LIMITE_POR_PEDIDO, estoque_disponivel_copo),
        value=0,
        step=1,
        key="qtd_copo"
    )

# ⭐️ NOVO BLOCO: NOMES INDIVIDUAIS PARA COPOS
nomes_copo = []
if qtd_copo > 0:
    st.markdown("---")
    st.markdown("#### Detalhes da Personalização dos Copos")
    st.info("Insira o nome desejado para cada copo. O limite é de **10 caracteres** por nome, e eles serão impressos em **letras maiúsculas**.")
    
    for i in range(qtd_copo):
        nome = st.text_input(
            f"Nome para Copo #{i+1} (Máx. 10 caracteres)",
            max_chars=10,
            placeholder=f"Ex: NOME{i+1}",
            key=f"nome_copo_{i}"
        )
        nomes_copo.append(nome)
    
    st.markdown("---")

if qtd_confra == 0 and qtd_copo == 0:
    st.info("Selecione a quantidade de Ingressos e/ou Copos desejados para continuar.")
    st.stop()
    
# --- Cálculos de Preço (mantidos) ---
total_itens = qtd_confra + qtd_copo

if qtd_confra == qtd_copo and qtd_confra > 0: # Caso seja Kit (mesma quantidade)
    preco_pix = qtd_confra * PRECOS_PIX["Kit"]
    preco_credito = qtd_confra * PRECOS_CREDITO["Kit"]
    tipo_compra = "Kit Ingresso + Copo"
    valor_unitario_pix = PRECOS_PIX["Kit"]
    valor_unitario_credito = PRECOS_CREDITO["Kit"]
else: # Caso seja compra mista ou apenas um item
    preco_pix = (qtd_confra * PRECOS_PIX["Confra"]) + (qtd_copo * PRECOS_PIX["Copo"])
    preco_credito = (qtd_confra * PRECOS_CREDITO["Confra"]) + (qtd_copo * PRECOS_CREDITO["Copo"])
    tipo_compra = f"{qtd_confra} Confra / {qtd_copo} Copo"
    valor_unitario_pix = (qtd_confra * PRECOS_PIX["Confra"] + qtd_copo * PRECOS_PIX["Copo"]) / total_itens if total_itens > 0 else 0
    valor_unitario_credito = (qtd_confra * PRECOS_CREDITO["Confra"] + qtd_copo * PRECOS_CREDITO["Copo"]) / total_itens if total_itens > 0 else 0


st.subheader("2. Detalhes dos Participantes")

# --- Regras para Crianças ---
st.markdown("""
<div style="border: 1px solid #ffcc00; padding: 10px; border-radius: 5px; background-color: #fffacd;">
    ⚠️ **ATENÇÃO - Crianças:** Crianças até **12 anos** não pagam. No entanto, é **obrigatório** informar o **nome completo** e **documento** da criança no formulário abaixo para liberação da entrada. A partir de 13 anos, pagam valor integral (contam como 1 ingresso).
</div>
""", unsafe_allow_html=True)

nomes_participantes, documentos_participantes = [], []

for i in range(qtd_confra):
    with st.container(border=True):
        st.markdown(f"**Dados do Participante de Ingresso #{i+1}**")
        col_nome, col_doc = st.columns(2)
        with col_nome:
            nome = st.text_input(f"Nome completo (Adulto ou Criança até 12 anos)", key=f"nome_confra_{i}")
        with col_doc:
            documento = st.text_input(f"RG ou outro Doc. com foto (Adulto) / Doc. (Criança)", key=f"doc_confra_{i}")
        
        nomes_participantes.append(nome)
        documentos_participantes.append(documento)

if qtd_copo > qtd_confra:
    st.warning("⚠️ Você selecionou mais Copos do que Ingressos. Lembre-se que o copo acompanha o kit ou é vendido individualmente. Não é necessário informar o nome dos participantes para os copos extras, apenas se comprar ingressos avulsos para eles.")


st.divider()

with st.form("finalizar_compra_form"):
    st.subheader("✉️ 3. Seus dados e forma de pagamento")
    
    nome_comprador = st.text_input("Seu nome completo (Responsável pela Compra)")
    email_comprador = st.text_input("Seu melhor e-mail para contato")
    whatsapp_comprador = st.text_input("Seu WhatsApp (com DDD)", placeholder="Ex: 11987654321")
    
    st.divider()
    st.markdown("#### **Escolha a forma de pagamento:**")

    # --- Opção 1: PIX ---
    with st.expander("Opção 1: Pagar com PIX (Melhor Preço)", expanded=True):
        st.markdown(f"### Valor total (PIX): **R$ {preco_pix:,.2f}**")
        st.markdown("Favorecido: **Hassan Marques Nehme**")
        st.markdown("Chave PIX (Telefone):")
        st.code("11994991465")
        st.info("Após realizar o pagamento via PIX, anexe o comprovante logo abaixo.")

    # --- Opção 2: Cartão de Crédito ---
    tupla_compra = (qtd_confra, qtd_copo)
    link_pagamento = LINKS_PAGAMENTO.get(tupla_compra, '#')

    if link_pagamento != '#':
        with st.expander("Opção 2: Pagar com Link (Cartão de Crédito com taxas)"):
            st.markdown(f"### Valor total (Crédito): **R$ {preco_credito:,.2f}**")
            st.markdown(f"🔗 [**CLIQUE AQUI PARA ACESSAR O LINK DE PAGAMENTO**]({link_pagamento})", unsafe_allow_html=True)
            st.warning("""**ATENÇÃO:** O pagamento através do link tem a **taxa da operadora**. Caso opte por **parcelar**, haverá também a **taxa de parcelamento** cobrada no momento da transação.""")
            st.info("Após realizar o pagamento pelo link, anexe o comprovante logo abaixo.")
    else:
        st.error("Combinação de itens inválida para gerar link de pagamento. Contate o administrador.")
        
    st.divider()
    comprovante = st.file_uploader("Anexe o comprovante de pagamento aqui (seja do PIX ou do Link)", type=["png", "jpg", "jpeg", "pdf"])
    
    st.divider()
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        # Desabilita se não houver itens ou se o link for inválido
        finalizar_btn = st.form_submit_button("✅ Finalizar Compra", use_container_width=True, disabled=(total_itens == 0))
    with col_btn2:
        # Desabilita se não houver itens ou se o link for inválido
        nova_compra_btn = st.form_submit_button("🔄 Finalizar e Nova Compra", use_container_width=True, disabled=(total_itens == 0))

# === Processamento da Compra ===
if finalizar_btn or nova_compra_btn:
    erro = False
    
    # ⭐️ VALIDAÇÃO DOS NOMES NO COPO (Múltiplos Nomes)
    nomes_copo_formatados = []
    if qtd_copo > 0:
        for nome in nomes_copo:
            nome_limpo = nome.strip()
            if not nome_limpo:
                st.error(f"❌ Por favor, preencha o nome para todos os **{qtd_copo} copos**.")
                erro = True
                break
            elif len(nome_limpo) > 10:
                st.error(f"❌ O nome '{nome_limpo}' no copo deve ter no máximo 10 caracteres.")
                erro = True
                break
            nomes_copo_formatados.append(nome_limpo.upper())
    
    # Validações existentes
    if not nome_comprador.strip():
        st.error("❌ Por favor, preencha seu nome completo.")
        erro = True
    if not email_valido(email_comprador):
        st.error("❌ O formato do e-mail é inválido.")
        erro = True
    if not whatsapp_valido(whatsapp_comprador):
        st.error("❌ O número de WhatsApp é inválido. Por favor, insira o DDD + número.")
        erro = True
    if qtd_confra > 0:
        if any(not nome.strip() for nome in nomes_participantes):
            st.error("❌ Preencha o nome de todos os participantes dos ingressos (incluindo crianças).")
            erro = True
        if any(not doc.strip() for doc in documentos_participantes):
            st.error("❌ Preencha o documento de todos os participantes dos ingressos (incluindo crianças).")
            erro = True
    
    if not comprovante:
        st.error("❌ O comprovante de pagamento é obrigatório.")
        erro = True
    if qtd_confra == 0 and qtd_copo == 0:
        st.error("❌ A quantidade de itens deve ser maior que zero.")
        erro = True

    if not erro:
        # ⭐️ PREPARA NOME DO COPO FINAL PARA O BANCO DE DADOS
        nomes_copo_final = ", ".join(nomes_copo_formatados) if qtd_copo > 0 else "N/A"
        
        with st.spinner("Processando sua compra, por favor aguarde..."):
            try:
                datahora = datetime.now().isoformat()
                
                # --- Salva no Supabase ---
                dados_para_supabase = {
                    "nome_comprador": nome_comprador,
                    "email_comprador": email_comprador,
                    "whatsapp_comprador": whatsapp_comprador,
                    "qtd_confra": qtd_confra,
                    "qtd_copo": qtd_copo,
                    "nomes_copo": nomes_copo_final, # ⭐️ CAMPO ATUALIZADO
                    "valor_pix": preco_pix,
                    "valor_credito": preco_credito,
                    "tipo_compra": tipo_compra,
                    "link_pagamento": link_pagamento if link_pagamento != '#' else "PIX",
                    "nomes_participantes": ", ".join(nomes_participantes),
                    "documentos_participantes": ", ".join(documentos_participantes),
                    "created_at": datahora
                }
                supabase.table("compra_confra").insert(dados_para_supabase).execute()

                # --- Gera CSV atualizado ---
                caminho_csv = sincronizar_csv_com_supabase("compra_confra", arquivo_csv)
                
                detalhes_participantes_email = "\n".join([f"  - Participante {i+1}: Nome '{nomes_participantes[i]}', Doc. {documentos_participantes[i]}" for i in range(qtd_confra)])
                
                detalhes_copo_email = "\n".join([f"  - Copo {i+1}: Nome '{nome}'" for i, nome in enumerate(nomes_copo_formatados)])
                
                # --- 1. Prepara e envia e-mail para o ADMINISTRADOR ---
                destinatarios_admin = [d.strip() for d in EMAIL_DESTINATARIO.split(",")]
                assunto_admin = f"Novo Pedido Confra Chapiuski 2025 - {nome_comprador}"
                corpo_admin = f"""
Novo pedido de Confra/Copo recebido!

DADOS DO COMPRADOR:
- Nome: {nome_comprador}
- E-mail: {email_comprador}
- WhatsApp: {whatsapp_comprador}
- Data/Hora: {datahora}

DETALHES DO PEDIDO:
- Qtd. Ingressos (Confra): {qtd_confra}
- Qtd. Copos Personalizados: {qtd_copo}
- Tipo de Compra: {tipo_compra}
- Valor PIX: R$ {preco_pix:,.2f}
- Valor Crédito (se aplicável): R$ {preco_credito:,.2f}

NOMES NOS COPOS:
{detalhes_copo_email if qtd_copo > 0 else 'Nenhum copo comprado.'}

PARTICIPANTES (Ingressos):
{detalhes_participantes_email if qtd_confra > 0 else 'Nenhum ingresso de adulto comprado.'}

O comprovante de pagamento e o CSV atualizado de todos os pedidos estão em anexo.
Verifique o pagamento para confirmar o pedido.
"""
                enviar_email_notificacao(EMAIL_REMETENTE, EMAIL_SENHA, destinatarios_admin, assunto_admin, corpo_admin, comprovante, caminho_csv)
                
                # --- 2. Prepara e envia e-mail para o COMPRADOR ---
                primeiro_nome = nome_comprador.split()[0]
                assunto_comprador = "✅ Pedido Confra Chapiuski 2025 Confirmado!"
                
                detalhes_itens = ""
                if qtd_confra > 0:
                    detalhes_itens += f"<li><b>Ingressos Confra:</b> {qtd_confra} unidade(s)</li>"
                if qtd_copo > 0:
                    nomes_copo_html = "".join([f"<br> - Copo {i+1}: **{nome}**" for i, nome in enumerate(nomes_copo_formatados)])
                    detalhes_itens += f"<li><b>Copos Personalizados:</b> {qtd_copo} unidade(s){nomes_copo_html}</li>"

                detalhes_participantes_html = "".join([f"<li>Participante {i+1}: <b>{nomes_participantes[i]}</b> (Doc: {documentos_participantes[i]})</li>" for i in range(qtd_confra)])

                corpo_comprador = f"""
                <html>
                <body style="font-family: sans-serif;">
                    <h2>Olá, {primeiro_nome}!</h2>
                    <p>Seu pedido para a Confra Chapiuski 2025 foi recebido com sucesso. 🍻</p>
                    <p>Agora, a organização irá **conferir seu comprovante** para validar a compra. Você receberá uma confirmação final.</p>
                    <hr>
                    <h3>Resumo do seu Pedido:</h3>
                    <ul>
                        {detalhes_itens}
                        <li><b>Valor Total (PIX):</b> R$ {preco_pix:,.2f}</li>
                        <li><b>Valor Total (Crédito):</b> R$ {preco_credito:,.2f} (base, sem taxas de parcelamento)</li>
                        <li><b>E-mail de Contato:</b> {email_comprador}</li>
                        <li><b>WhatsApp:</b> {whatsapp_comprador}</li>
                    </ul>

                    <h3>Participantes Registrados (Obrigatório Documento com Foto na Entrada):</h3>
                    <ul style="list-style-type: none; padding-left: 0;">
                        {detalhes_participantes_html if qtd_confra > 0 else '<li>Nenhum ingresso adulto/pagante registrado.</li>'}
                    </ul>

                    <p>⚠️ **LEMBRETE IMPORTANTE:** Crianças até 12 anos não pagam, mas devem ter os dados informados acima.</p>
                    <hr>
                    <p>Obrigado por fazer parte da Confra!</p>
                    <p><b>#ConfraChapiuski2025</b></p>
                </body>
                </html>
                """
                enviar_email_para_comprador(EMAIL_REMETENTE, EMAIL_SENHA, email_comprador, assunto_comprador, corpo_comprador)

                # --- Mensagem de sucesso para o usuário ---
                if finalizar_btn:
                    st.success(f"✅ Compra finalizada com sucesso! Obrigado, {primeiro_nome}!")
                    st.info("Seu pedido foi registrado. Verifique seu e-mail para o resumo da compra. A validação final será feita após a conferência do comprovante pela organização.")
                    st.balloons()
                
                elif nova_compra_btn:
                    # 1. Guarda a mensagem de sucesso na sessão
                    st.session_state.mensagem_sucesso = f"Pedido confirmado, {primeiro_nome}! Sua compra foi registrada com sucesso e está aguardando conferência do comprovante."

                    # 2. Limpa todos os campos do formulário para o reset
                    chaves_para_limpar = [key for key in st.session_state.keys() if key != 'mensagem_sucesso']
                    for key in chaves_para_limpar:
                        del st.session_state[key]
        
                    # 3. Força o recarregamento da página. A mensagem será exibida no topo.
                    st.rerun()

            except Exception as e:
                st.error(f"❌ Ocorreu um erro inesperado ao processar seu pedido.")
                st.error(f"Detalhe do erro: {e}")
                st.warning("Por favor, tente novamente ou contate o suporte.")


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

# Bloco para exibir a mensagem de sucesso que sobrevive ao rerun da página
if "mensagem_sucesso" in st.session_state:
    st.success(st.session_state.mensagem_sucesso, icon="🎉")
    # Limpa a mensagem da memória para não exibi-la novamente
    del st.session_state.mensagem_sucesso

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

# Validação do Whatsapp
def whatsapp_valido(whatsapp):
    """Verifica se o WhatsApp tem um formato minimamente válido (10 ou 11 dígitos)."""
    if whatsapp:
        # Remove todos os caracteres que não são dígitos
        numeros = re.sub(r'\D', '', whatsapp)
        # Verifica se tem 10 ou 11 dígitos (comum para fixo+DDD ou celular+DDD)
        return len(numeros) >= 10
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

st.markdown("<h1 style='text-align: center;'>Manto aurinegro - Temporada 25/26</h1>", unsafe_allow_html=True)
st.markdown("<h4 style='text-align: center; color: #333;'>1, 2, 4... Chapiuski!!! 💛🖤⚽</h4>", unsafe_allow_html=True)

try:
    st.image('Confra/camisas 2025.jpg', caption='Modelos oficiais para a temporada 25/26')
except Exception:
    st.warning("⚠️ Imagem 'camisas 2025.jpg' não encontrada.")
st.divider()

st.warning(
    "**Atenção:** Permitimos no máximo 6 peças por pedido, sendo até 3 do modelo Jogador e até 3 do modelo Torcedor."
)

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
    
    st.subheader("2. Detalhes de cada camisa")

    #Expander com detalhes de medidas das camisas
    try:
        with st.expander("📏 Dúvida com o tamanho? **Clique aqui para ver as tabelas de medidas**"):
            col_medida1, col_medida2 = st.columns(2)
            with col_medida1:
                # Altere o nome do arquivo se necessário (ex: .jpg, .jpeg)
                st.image('Confra/tabela_medidas_jogador.jpg', caption='Medidas Modelo JOGADOR')
            with col_medida2:
                # Altere o nome do arquivo se necessário (ex: .jpg, .jpeg)
                st.image('Confra/tabela_medidas_torcedor.jpg', caption='Medidas Modelo TORCEDOR')
    except FileNotFoundError:
        st.warning("⚠️ Imagens das tabelas de medida não encontradas. Verifique os nomes e caminhos dos arquivos.")
    except Exception as e:
        st.error(f"Ocorreu um erro ao carregar as tabelas de medida: {e}")

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
        whatsapp_comprador = st.text_input("Seu WhatsApp (com DDD)", placeholder="Ex: 11987654321")
        
        st.divider()
        st.markdown("#### **Escolha a forma de pagamento:**")

        with st.expander("Opção 1: Pagar com PIX (Sem taxas)", expanded=True):
            st.markdown(f"### Valor total: **R$ {preco_total},00**")
            st.markdown("Favorecido: **Hassan Marques Nehme**")
            st.markdown("Chave PIX (Telefone):")
            st.code("11994991465")
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
        if not whatsapp_valido(whatsapp_comprador):
            st.error("❌ O número de WhatsApp é inválido. Por favor, insira o DDD + número.")
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
                        "whatsapp_comprador": whatsapp_comprador,
                        "tamanho": ", ".join(tamanhos_camisa),
                        "numero_camisa": ",".join(map(str, numeros_camisa)),
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
- WhatsApp: {whatsapp_comprador}
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
                        <p>Estamos confirmando o seu pagamento.</p>
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
                        st.info("Seu pedido para as camisas da temporada 2025 do Chapiuski foi recebido com sucesso. 💛🖤. Estamos confirmando o seu pagamento.")
                        st.balloons()
                    
                    elif nova_compra_btn:
                        # 1. Guarda a mensagem de sucesso na sessão para ser exibida após o recarregamento
                        primeiro_nome = nome_comprador.split()[0]
                        st.session_state.mensagem_sucesso = f"Pedido confirmado, {primeiro_nome}! Sua compra foi registrada com sucesso."

                        # 2. Limpa todos os campos do formulário para o reset
                        # Vamos ter o cuidado de não apagar a própria chave da mensagem que acabamos de criar
                        chaves_para_limpar = [key for key in st.session_state.keys() if key != 'mensagem_sucesso']
                        for key in chaves_para_limpar:
                            del st.session_state[key]
    
                        # 3. Força o recarregamento da página. A mensagem será exibida no topo.
                        st.rerun()

                except Exception as e:
                    st.error(f"❌ Ocorreu um erro inesperado ao processar seu pedido.")
                    st.error(f"Detalhe do erro: {e}")
                    st.warning("Por favor, tente novamente ou contate o suporte.")

else:
    st.info("Selecione a quantidade de camisas desejadas para iniciar seu pedido.")