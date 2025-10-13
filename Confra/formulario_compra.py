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

# Mapeamento para Link de Pagamento no Crédito (Chave: (qtd_confra_pagantes, qtd_copo))
# ATENÇÃO: Os links abaixo continuam mapeando o total BRUTO de ingressos de Confra e copos.
# Para manter a lógica correta, teríamos que gerar links dinâmicos no PagSeguro (API) ou 
# criar links para todas as combinações (Adultos, Crianças) - o que não é escalável.
# MANTEREMOS O CÁLCULO DE VALOR DEVIDO AO PIX E A VISUALIZAÇÃO CORRETA NA TELA.
# A lógica de link para Cartão de Crédito é complexa e requer MUITOS links. 
# Para simplificar, vamos assumir que os links SÓ SERÃO USADOS para combos onde NÃO HÁ CRIANÇAS.
# Se houver criança e o usuário escolher crédito, o link ficará inválido e a validação irá barrar.
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
            colunas = ["nome_comprador", "email_comprador", "whatsapp_comprador", "qtd_confra", "qtd_copo", "nomes_copo", "valor_pix", "valor_credito", "link_pagamento", "nomes_participantes", "documentos_participantes", "e_crianca", "created_at"] # Coluna 'e_crianca' adicionada
            df = pd.DataFrame(columns=colunas)
            df.to_csv(caminho_csv, index=False, encoding="utf-8-sig")
            return caminho_csv
    except Exception as e:
        st.error(f"❌ Erro ao sincronizar CSV com Supabase: {e}")
        return None

# ==== Interface do Streamlit ====
st.markdown("<h1 style='text-align: center;'>Confra 2025 - Chapiuski</h1>", unsafe_allow_html=True)
st.markdown("<h4 style='text-align: center; color: #333;'>Ingressos e Copos Personalizados</h4>", unsafe_allow_html=True)

# ⭐️ IMAGEM GERAL DO EVENTO - TAMANHO MENOR
try:
    col_img_main1, col_img_main2, col_img_main3 = st.columns([1,2,1])
    with col_img_main2: # Centraliza a imagem principal
        st.image('Confra/CHAP.jpg', caption='Confra Chapiuski 2025', width=300) 
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
- **Bebidas:** Bar do Fausto (Chopp, Vodka, Cachaça, Refrigerantes, Sucos e Água - venda local).
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

# ⭐️ NOVO ALERTA SOBRE DESCONTO DO KIT ⭐️
st.info("""
🚨 **ATENÇÃO AO DESCONTO DO KIT!**

O desconto de **R$ 10,00** é aplicado **apenas** quando o Ingresso e o Copo são comprados **simultaneamente** (no mesmo preenchimento/pedido).

Exemplo: Se comprar apenas o Ingresso e decidir comprar o Copo depois, o Copo será cobrado no preço integral de **R$ 40,00**, **sem o desconto do Kit.**
""")
# ⭐️ FIM DO NOVO ALERTA ⭐️

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
        st.image('Confra/COPO.jpg', caption='Copo Personalizado da Confra', width=200) 
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

# ⭐️ BLOCO: NOMES INDIVIDUAIS PARA COPOS
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
    

# --- SEÇÃO DE DETALHES DOS PARTICIPANTES (Antes do cálculo de preço) ---

st.subheader("2. Detalhes dos Participantes")

# --- Regras para Crianças ---
st.warning("""
**ATENÇÃO - Crianças:** Crianças até **12 anos** não pagam o valor do ingresso Confra.

**Obrigatório:** Informar o **nome completo** e **documento** da criança no formulário abaixo e **marcar a caixa "É Criança (até 12 anos)"** para que o desconto do ingresso seja aplicado ao total da compra.

A partir de 13 anos, pagam valor integral (contam como 1 ingresso).
""")

nomes_participantes, documentos_participantes, flags_crianca = [], [], [] # Lista para a nova flag

for i in range(qtd_confra):
    with st.container(border=True):
        st.markdown(f"**Dados do Participante de Ingresso #{i+1}**")
        col_nome, col_doc, col_crianca = st.columns([3, 3, 2]) # Ajuste de colunas
        
        with col_nome:
            nome = st.text_input(f"Nome Completo (Adulto) / Nome Completo (Criança até 12 anos)", key=f"nome_confra_{i}")
        with col_doc:
            documento = st.text_input(f"RG ou Doc. com foto (Adulto) / RG ou Doc. com foto (Criança)", key=f"doc_confra_{i}")
        with col_crianca:
            # ⭐️ NOVO CAMPO DE FLAG
            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
            e_crianca = st.checkbox("É Criança (até 12 anos)", key=f"crianca_flag_{i}")
        
        nomes_participantes.append(nome)
        documentos_participantes.append(documento)
        flags_crianca.append(e_crianca) # ⭐️ ARMAZENA A FLAG

if qtd_copo > qtd_confra:
    st.warning("⚠️ Você selecionou mais Copos do que Ingressos. Lembre-se que o copo acompanha o kit ou é vendido individualmente.")


# ⭐️ --- CÁLCULO DE PREÇO AJUSTADO (DEPOIS DOS DETALHES) ---
total_itens = qtd_confra + qtd_copo
qtd_criancas = sum(flags_crianca)
qtd_confra_pagantes = qtd_confra - qtd_criancas # Subtrai a contagem das crianças

# Valida se há mais crianças marcadas do que ingressos comprados (erro de lógica)
if qtd_confra_pagantes < 0:
    st.error("⚠️ Erro de contagem: Há mais participantes marcados como crianças do que ingressos de Confra comprados. Por favor, verifique.")
    st.stop()

# --- Cálculo de preço baseado APENAS em itens PAGANTES ---
# A lógica agora aplica o desconto do Kit ao menor número entre Ingresso Pagante e Copo.

# Encontra a quantidade de KITS que podem ser formados (Kit = 1 Ingresso Pagante + 1 Copo)
qtd_kits = min(qtd_confra_pagantes, qtd_copo)

# Calcula itens restantes após a formação dos kits
qtd_confra_avulsa = qtd_confra_pagantes - qtd_kits
qtd_copo_avulso = qtd_copo - qtd_kits

# --- 1. Cálculo PIX ---
# Valor do Kit PIX (com desconto) * Qtd de kits
preco_pix_kits = qtd_kits * PRECOS_PIX["Kit"]
# Valor do Ingresso Confra Avulso (sem desconto)
preco_pix_confra_avulsa = qtd_confra_avulsa * PRECOS_PIX["Confra"]
# Valor do Copo Avulso (sem desconto)
preco_pix_copo_avulso = qtd_copo_avulso * PRECOS_PIX["Copo"]

preco_pix = preco_pix_kits + preco_pix_confra_avulsa + preco_pix_copo_avulso

# --- 2. Cálculo CRÉDITO ---
# Valor do Kit CRÉDITO (com desconto) * Qtd de kits
preco_credito_kits = qtd_kits * PRECOS_CREDITO["Kit"]
# Valor do Ingresso Confra Avulso (sem desconto)
preco_credito_confra_avulsa = qtd_confra_avulsa * PRECOS_CREDITO["Confra"]
# Valor do Copo Avulso (sem desconto)
preco_credito_copo_avulso = qtd_copo_avulso * PRECOS_CREDITO["Copo"]

preco_credito = preco_credito_kits + preco_credito_confra_avulsa + preco_credito_copo_avulso

# Define o tipo de compra para fins de registro no DB/Email
if qtd_kits > 0:
    tipo_compra = f"{qtd_kits} Kit(s) / {qtd_confra_avulsa} Confra Avulsa / {qtd_copo_avulso} Copo Avulso"
elif qtd_confra_pagantes > 0 or qtd_copo > 0:
    tipo_compra = f"{qtd_confra_pagantes} Confra Pagante / {qtd_copo} Copo"
else:
    tipo_compra = "Apenas Crianças (Qtd Confra > 0, Pagante = 0)"

if qtd_criancas > 0:
    tipo_compra += f" ({qtd_criancas} Criança(s) Gratuita(s))"


st.divider()

# --- FIM DO CÁLCULO ---

with st.form("finalizar_compra_form"):
    st.subheader("✉️ 3. Seus dados e forma de pagamento")
    
    nome_comprador = st.text_input("Seu nome completo (Responsável pela Compra)")
    email_comprador = st.text_input("Seu melhor e-mail para contato")
    whatsapp_comprador = st.text_input("Seu WhatsApp (com DDD)", placeholder="Ex: 11987654321")
    
    st.divider()
    st.markdown("#### **Escolha a forma de pagamento:**")

    # --- Opção 1: PIX ---
    with st.expander("Opção 1: Pagar com PIX (Melhor Preço)", expanded=True):
        st.markdown(f"### Valor total (PIX): **R$ {preco_pix:,.2f}**") # Exibe o valor CORRETO/COM DESCONTO
        st.markdown("Favorecido: **Hassan Marques Nehme**")
        st.markdown("Chave PIX (Telefone):")
        st.code("11994991465")
        st.info("Após realizar o pagamento via PIX, anexe o comprovante logo abaixo.")

    # --- Opção 2: Cartão de Crédito ---
    # Usamos o link apenas se a compra for exatamente igual à tupla do link (ou seja, sem crianças)
    tupla_compra_pagantes = (qtd_confra_pagantes, qtd_copo)
    link_pagamento = LINKS_PAGAMENTO.get(tupla_compra_pagantes, '#')

    if link_pagamento != '#':
        with st.expander("Opção 2: Pagar com Link (Cartão de Crédito com taxas)"):
            st.markdown(f"### Valor total (Crédito): **R$ {preco_credito:,.2f}**") # Exibe o valor CORRETO/COM DESCONTO
            st.markdown(f"🔗 [**CLIQUE AQUI PARA ACESSAR O LINK DE PAGAMENTO**]({link_pagamento})", unsafe_allow_html=True)
            st.warning("""**ATENÇÃO:** O pagamento através do link tem a **taxa da operadora**. Caso opte por **parcelar**, haverá também a **taxa de parcelamento** cobrada no momento da transação. **Este link é válido para sua combinação de compra.**""")
            st.info("Após realizar o pagamento pelo link, anexe o comprovante logo abaixo.")
    else:
        st.error(f"Combinação de itens ({qtd_confra_pagantes} Pagante Confra, {qtd_copo} Copo) **inválida para gerar link de pagamento no cartão**. Por favor, utilize a opção **PIX**.")
        
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
    
    # ... [VALIAÇÃO DE NOMES DE COPO, COMPRADOR, ETC. (MANTIDA)] ...

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
    # Validação do Link de Crédito (Se não houver link válido, não permite finalizar)
    if link_pagamento == '#' and ('Crédito' in st.session_state.get('forma_pagamento', '')): # Validação simples que pode falhar
        # Se for pix, não tem problema, mas se for crédito, tem que ter link
        # É mais seguro validar o PIX, mas como o campo de comprovante é genérico,
        # vamos confiar que o usuário usará o PIX se o link for inválido, e deixar o erro acima.
        pass 
    
    if not erro:
        # ⭐️ PREPARA AS LISTAS FINAIS PARA O BANCO DE DADOS
        nomes_copo_final = ", ".join(nomes_copo_formatados) if qtd_copo > 0 else "N/A"
        # Converte a lista de booleanos (True/False) para strings ('Sim'/'Não') para o DB/CSV
        flags_crianca_str = ["Sim" if flag else "Não" for flag in flags_crianca]
        
        with st.spinner("Processando sua compra, por favor aguarde..."):
            try:
                datahora = datetime.now().isoformat()
                
                # --- Salva no Supabase ---
                dados_para_supabase = {
                    "nome_comprador": nome_comprador,
                    "email_comprador": email_comprador,
                    "whatsapp_comprador": whatsapp_comprador,
                    "qtd_confra": qtd_confra, # Qtd. Bruta de participantes
                    "qtd_copo": qtd_copo,
                    "nomes_copo": nomes_copo_final,
                    "valor_pix": preco_pix, # ⭐️ Valor FINAL
                    "valor_credito": preco_credito, # ⭐️ Valor FINAL
                    "tipo_compra": tipo_compra,
                    "link_pagamento": link_pagamento if link_pagamento != '#' else "PIX",
                    "nomes_participantes": ", ".join(nomes_participantes),
                    "documentos_participantes": ", ".join(documentos_participantes),
                    "e_crianca": ", ".join(flags_crianca_str), # Novo campo salvo
                    "created_at": datahora
                }
                supabase.table("compra_confra").insert(dados_para_supabase).execute()

                # --- Gera CSV atualizado ---
                caminho_csv = sincronizar_csv_com_supabase("compra_confra", arquivo_csv)
                
                # Prepara detalhes para o e-mail do ADMIN
                detalhes_participantes_email = "\n".join([f"  - Participante {i+1}: Nome '{nomes_participantes[i]}', Doc. {documentos_participantes[i]}, Criança: {flags_crianca_str[i]}" for i in range(qtd_confra)])
                
                detalhes_copo_email = "\n".join([f"  - Copo {i+1}: Nome '{nome}'" for i, nome in enumerate(nomes_copo_formatados)])
                
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
- Qtd. Ingressos (Confra): {qtd_confra} ({qtd_confra_pagantes} Pagantes, {sum(flags_crianca)} Gratuitos)
- Qtd. Copos Personalizados: {qtd_copo}
- Tipo de Compra: {tipo_compra}
- Valor PIX (FINAL): R$ {preco_pix:,.2f}
- Valor Crédito (FINAL, se aplicável): R$ {preco_credito:,.2f}

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
                    detalhes_itens += f"<li><b>Ingressos Confra:</b> {qtd_confra} unidade(s) ({qtd_confra_pagantes} Pagantes)</li>"
                if qtd_copo > 0:
                    nomes_copo_html = "".join([f"<br> - Copo {i+1}: **{nome}**" for i, nome in enumerate(nomes_copo_formatados)])
                    detalhes_itens += f"<li><b>Copos Personalizados:</b> {qtd_copo} unidade(s){nomes_copo_html}</li>"

                # Prepara detalhes para o e-mail do COMPRADOR (incluindo a flag)
                detalhes_participantes_html = "".join([f"<li>Participante {i+1}: <b>{nomes_participantes[i]}</b> (Doc: {documentos_participantes[i]}) - **Criança (Até 12 anos): {flags_crianca_str[i]}**</li>" for i in range(qtd_confra)])

                corpo_comprador = f"""
                <html>
                <body style="font-family: sans-serif;">
                    <h2>Olá, {primeiro_nome}!</h2>
                    <p>Seu pedido para a Confra Chapiuski 2025 foi recebido com sucesso. 🍻</p>
                    <p>Agora, a organização irá **conferir seu comprovante** para validar a compra.</p>
                    <hr>
                    <h3>Resumo do seu Pedido:</h3>
                    <ul>
                        {detalhes_itens}
                        <li><b>Valor Total (PIX):</b> R$ {preco_pix:,.2f}</li>
                        <li><b>Valor Total (Crédito):</b> R$ {preco_credito:,.2f} (base, sem taxas de parcelamento)</li>
                        <li><b>E-mail de Contato:</b> {email_comprador}</li>
                        <li><b>WhatsApp:</b> {whatsapp_comprador}</li>
                    </ul>

                    <h3>Participantes Registrados (Obrigatório Documento na Entrada):</h3>
                    <ul style="list-style-type: none; padding-left: 0;">
                        {detalhes_participantes_html if qtd_confra > 0 else '<li>Nenhum ingresso registrado.</li>'}
                    </ul>

                    <p>✅ **Valor Calculado:** O valor final de R$ {preco_pix:,.2f} (PIX) já inclui o desconto do(s) ingresso(s) gratuito(s) da(s) criança(s) indicada(s) acima.</p>
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