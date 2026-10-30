"""
Ingressos - Festa de Fim de Ano Chapiuski 2026
Streamlit + Supabase. Somente ingressos (sem copos), até 3 por pedido, dois lotes por data.
"""
import logging
import os
import re
import smtplib
from datetime import datetime, timedelta, timezone
from email import encoders
from email.header import Header
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from urllib.parse import urlparse

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from supabase import Client, create_client

# ==== DEVE SER O PRIMEIRO COMANDO STREAMLIT ====
st.set_page_config(
    layout="centered",
    page_title="Ingressos Chapiuski 2026",
    page_icon="🍻",
)

log = logging.getLogger(__name__)

# Mensagem de sucesso que sobrevive ao rerun ("Finalizar e Nova Compra")
if "mensagem_sucesso" in st.session_state:
    _msg = st.session_state["mensagem_sucesso"]
    del st.session_state["mensagem_sucesso"]
    st.success(_msg, icon="🎉")

# ==================== CONFIGURAÇÃO ====================
load_dotenv()


def config(nome):
    """Lê do .env / variável de ambiente; se não houver, dos Secrets do Streamlit."""
    valor = os.getenv(nome)
    if valor:
        return valor.strip()
    try:
        return str(st.secrets[nome]).strip()
    except Exception:
        return None


def normalizar_url_supabase(url):
    """Devolve só https://<projeto>.supabase.co.
    Descarta barra no fim e caminhos colados por engano (ex.: /rest/v1/), que causam o erro
    PGRST125 'Invalid path specified in request URL'."""
    if not url:
        return url
    url = url.strip()
    if "://" not in url:
        url = "https://" + url
    partes = urlparse(url)
    return f"{partes.scheme}://{partes.netloc}"


SUPABASE_URL = normalizar_url_supabase(config("SUPABASE_URL"))
SUPABASE_KEY = config("SUPABASE_KEY")
EMAIL_REMETENTE = config("EMAIL_REMETENTE")
EMAIL_SENHA = config("EMAIL_SENHA")
EMAIL_DESTINATARIO = config("EMAIL_DESTINATARIO")  # e-mails da organização, separados por vírgula

# SÓ PARA TESTES: simula a data/hora (ex.: "2026-11-05 10:00"). Deixe VAZIO em produção.
DATA_SIMULADA = config("DATA_SIMULADA")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("⚠️ Sistema temporariamente indisponível (configuração incompleta). Avise a organização.")
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==================== DADOS DO EVENTO ====================
TABELA = "compra_confra"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGEM_EVENTO = os.path.join(BASE_DIR, "CHAP.jpg")  # opcional: se não existir, é ignorada

# Horário de Brasília (UTC-3). O Brasil não tem mais horário de verão; o servidor roda em UTC.
FUSO = timezone(timedelta(hours=-3), "BRT")

LIMITE_INGRESSOS_POR_PEDIDO = 3
LIMITE_CRIANCAS_POR_PEDIDO = 3
ESTOQUE_MAX = 100  # ⚠️ AJUSTE: capacidade total (pagantes + crianças)

# ⚠️ CONFIRA: mantidos do site anterior
PIX_FAVORECIDO = "Hassan Marques Nehme"
PIX_CHAVE = "11994991465"  # chave PIX (telefone)

ANEXAR_CSV_AO_ADMIN = True  # anexa a lista completa de pedidos no e-mail da organização

# Cada lote vale de "inicio" (inclusive) até "fim" (exclusivo).
# Lote 1 termina à meia-noite do fim do dia 28/11 (= 29/11 00h00).
LOTES = [
    {
        "nome": "Lote 1",
        "periodo": "01/11 a 28/11",
        "inicio": datetime(2026, 11, 1, 0, 0, tzinfo=FUSO),
        "fim": datetime(2026, 11, 29, 0, 0, tzinfo=FUSO),
        "pix_unit": 80.00,
        "credito_unit": 85.00,
        "links": {
            1: "https://pag.ae/82h2GJR13",
            2: "https://pag.ae/82h2JfDM3",
            3: "https://pag.ae/82h2JNcg4",
        },
    },
    {
        "nome": "Lote 2",
        "periodo": "29/11 a 05/12 (até 12h)",
        "inicio": datetime(2026, 11, 29, 0, 0, tzinfo=FUSO),
        "fim": datetime(2026, 12, 5, 12, 0, tzinfo=FUSO),
        "pix_unit": 95.00,
        "credito_unit": 100.00,
        "links": {
            1: "https://pag.ae/82hPqxKsJ",
            2: "https://pag.ae/82hPsAnm4",
            3: "https://pag.ae/82hPs-jEo",
        },
    },
]


# ==================== FUNÇÕES AUXILIARES ====================
def brl(valor):
    """Formata em reais: 1234.5 -> 'R$ 1.234,50'."""
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def agora_brasilia():
    if DATA_SIMULADA:
        try:
            return datetime.fromisoformat(DATA_SIMULADA).replace(tzinfo=FUSO)
        except ValueError:
            pass
    return datetime.now(FUSO)


def lote_vigente(agora):
    # Antes do início do Lote 1 as vendas já funcionam (o link só é divulgado na data certa):
    # vale o preço do Lote 1.
    if agora < LOTES[0]["inicio"]:
        return LOTES[0]
    for lote in LOTES:
        if lote["inicio"] <= agora < lote["fim"]:
            return lote
    return None


def email_valido(email):
    return bool(email) and re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()) is not None


def whatsapp_valido(whatsapp):
    if whatsapp:
        return len(re.sub(r"\D", "", whatsapp)) >= 10
    return False


def consultar_total_vendido():
    """Total de pessoas (pagantes + crianças) já registradas. Consulta direta, sem cache."""
    resp = supabase.table(TABELA).select("qtd_confra").execute()
    return sum((item.get("qtd_confra") or 0) for item in (resp.data or []))


@st.cache_data(ttl=60)
def total_vendido_cache():
    """Versão com cache curto, só para exibição. A checagem final no envio NÃO usa cache."""
    return consultar_total_vendido()


def gerar_csv_pedidos():
    resp = supabase.table(TABELA).select("*").order("created_at", desc=True).execute()
    if not resp.data:
        return None
    return pd.DataFrame(resp.data).to_csv(index=False).encode("utf-8-sig")


def enviar_email(destinatarios, assunto, corpo, tipo="plain", anexos=None):
    msg = MIMEMultipart()
    msg["Subject"] = Header(assunto, "utf-8")
    msg["From"] = EMAIL_REMETENTE
    msg["To"] = ", ".join(destinatarios)
    msg.attach(MIMEText(corpo, tipo, "utf-8"))
    for nome_arquivo, conteudo in anexos or []:
        parte = MIMEBase("application", "octet-stream")
        parte.set_payload(conteudo)
        encoders.encode_base64(parte)
        parte.add_header("Content-Disposition", "attachment", filename=nome_arquivo)
        msg.attach(parte)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_REMETENTE, EMAIL_SENHA)
        server.sendmail(EMAIL_REMETENTE, destinatarios, msg.as_string())


# ==================== PÁGINA: INFORMAÇÕES DO EVENTO ====================
st.markdown(
    "<h1 style='text-align: center;'>Festa de Fim de Ano - Chapiuski 2026</h1>",
    unsafe_allow_html=True,
)
st.markdown("<h4 style='text-align: center;'>Ingressos</h4>", unsafe_allow_html=True)

if os.path.exists(IMAGEM_EVENTO):
    _c1, _c2, _c3 = st.columns([1, 2, 1])
    with _c2:
        st.image(IMAGEM_EVENTO, width=300)

st.divider()

st.info(
    "**📅 Data:** Sábado, 05/12/2026 | **⏰ Festa:** 16h às 22h\n\n"
    "**📍 Local:** Penha Society - Penha, SP"
)

st.markdown("""
### O que esperar
- **Futebol:** 14h às 16h
- **Premiação:** após o futebol
- **Festa:** 16h às 22h
- **Open Food:** equipe Alô Garçom
- **Bebidas:** vendas no bar do Fausto
- **Pagode ao vivo:** A partir das 19h
""")

agora = agora_brasilia()
lote = lote_vigente(agora)

# Mostra só o valor do lote vigente: os valores dos outros lotes são informação interna.
if lote is not None:
    st.markdown("### Formas de pagamento")
    st.markdown(
        "| Ingresso | PIX | Créd c/ taxa |\n"
        "| :--- | :--- | :--- |\n"
        f"| **{lote['nome']}** ({lote['periodo']}) | {brl(lote['pix_unit'])} | {brl(lote['credito_unit'])} |"
    )
    st.caption("Valores por ingresso.")
    if lote is LOTES[0]:
        # Aviso público dos flyers (sem citar valores)
        st.caption("Após o término das vendas deste lote haverá reajuste no preço (conforme disponibilidade).")

st.warning(
    "**Crianças de até 12 anos não pagam**, mas é obrigatório preencher o nome completo e o "
    "documento de cada uma. O ingresso é validado conforme o pagamento e o preenchimento deste formulário."
)

# ==================== VENDAS ABERTAS? ====================
if lote is None:
    st.warning("🚫 As vendas foram encerradas. Em caso de dúvidas, fale com a organização.")
    st.stop()

try:
    total_vendido = total_vendido_cache()
except Exception:
    log.exception("Falha ao consultar o estoque")
    st.error("Não foi possível consultar a disponibilidade agora. Tente novamente em instantes.")
    st.stop()

estoque_disponivel = max(0, ESTOQUE_MAX - total_vendido)
if estoque_disponivel == 0:
    st.warning("🚫 Ingressos esgotados!")
    st.stop()

st.divider()

# ==================== 1. QUANTIDADE ====================
st.subheader("1. Quantidade de ingressos")
st.caption(f"Máximo de {LIMITE_INGRESSOS_POR_PEDIDO} ingressos pagos por compra.")

qtd_ingressos = st.number_input(
    "Ingressos (pagantes)",
    min_value=0,
    max_value=min(LIMITE_INGRESSOS_POR_PEDIDO, estoque_disponivel),
    step=1,
    key="qtd_ingressos",
)

if qtd_ingressos == 0:
    st.info("Selecione a quantidade de ingressos para continuar.")
    st.stop()

# ==================== 2. PARTICIPANTES ====================
st.subheader("2. Detalhes dos participantes")

nomes_pagantes, documentos_pagantes = [], []
for i in range(qtd_ingressos):
    with st.container(border=True):
        st.markdown(f"**Participante pagante #{i + 1}**")
        col_nome, col_doc = st.columns(2)
        with col_nome:
            nomes_pagantes.append(st.text_input(f"Nome completo ({i + 1})", key=f"nome_adulto_{i}"))
        with col_doc:
            documentos_pagantes.append(
                st.text_input(f"RG ou doc. com foto ({i + 1})", key=f"doc_adulto_{i}")
            )

st.markdown("#### Crianças de até 12 anos (grátis)")

max_criancas = max(0, min(LIMITE_CRIANCAS_POR_PEDIDO, estoque_disponivel - qtd_ingressos))
if st.session_state.get("qtd_criancas", 0) > max_criancas:
    st.session_state["qtd_criancas"] = max_criancas

if max_criancas > 0:
    qtd_criancas = st.number_input(
        "Quantas crianças de até 12 anos acompanham?",
        min_value=0,
        max_value=max_criancas,
        step=1,
        key="qtd_criancas",
    )
else:
    qtd_criancas = 0
    st.caption("Não há vagas restantes para crianças neste pedido.")

nomes_criancas, documentos_criancas = [], []
if qtd_criancas > 0:
    st.info("Preencha os dados de cada criança. O registro é obrigatório para a entrada.")
    for i in range(qtd_criancas):
        with st.container(border=True):
            st.markdown(f"**Criança #{i + 1} (grátis)**")
            col_nome, col_doc = st.columns(2)
            with col_nome:
                nomes_criancas.append(st.text_input(f"Nome completo (criança {i + 1})", key=f"nome_crianca_{i}"))
            with col_doc:
                documentos_criancas.append(
                    st.text_input(f"RG ou doc. com foto (criança {i + 1})", key=f"doc_crianca_{i}")
                )

nomes_participantes = nomes_pagantes + nomes_criancas
documentos_participantes = documentos_pagantes + documentos_criancas
flags_crianca_str = ["Não"] * len(nomes_pagantes) + ["Sim"] * len(nomes_criancas)
qtd_total_pessoas = qtd_ingressos + qtd_criancas

# ==================== VALORES ====================
preco_pix = qtd_ingressos * lote["pix_unit"]
preco_credito = qtd_ingressos * lote["credito_unit"]
link_pagamento = lote["links"][qtd_ingressos]

tipo_compra = f"{lote['nome']} - {qtd_ingressos} ingresso(s) pago(s)"
if qtd_criancas > 0:
    tipo_compra += f" + {qtd_criancas} criança(s) gratuita(s)"

st.divider()

# ==================== 3. DADOS E PAGAMENTO ====================
FORMA_PIX = "PIX"
FORMA_CREDITO = "Cartão de crédito (link)"

with st.form("finalizar_compra_form"):
    st.subheader("3. Seus dados e forma de pagamento")

    nome_comprador = st.text_input("Seu nome completo (responsável pela compra)")
    email_comprador = st.text_input("Seu melhor e-mail para contato")
    whatsapp_comprador = st.text_input("Seu WhatsApp (com DDD)", placeholder="Ex: 11987654321")

    st.divider()
    st.markdown(f"#### Pagamento - {lote['nome']}")

    with st.expander("Opção 1: PIX (melhor preço)", expanded=True):
        st.markdown(f"### Valor (PIX): **{brl(preco_pix)}**")
        st.markdown(f"Favorecido: **{PIX_FAVORECIDO}**")
        st.markdown("Chave PIX (telefone):")
        st.code(PIX_CHAVE)

    with st.expander("Opção 2: Cartão de crédito em até 10x (link, com taxa)"):
        st.markdown(f"### Valor (crédito): **{brl(preco_credito)}**")
        st.markdown(f"🔗 [**CLIQUE AQUI PARA ACESSAR O LINK DE PAGAMENTO**]({link_pagamento})")
        st.info("Este link vale para a sua quantidade de ingressos neste lote.")

    forma_pagamento = st.radio(
        "Como você pagou?", [FORMA_PIX, FORMA_CREDITO], horizontal=True
    )
    comprovante = st.file_uploader(
        "Anexe o comprovante de pagamento (PIX ou link)", type=["png", "jpg", "jpeg", "pdf"]
    )

    st.divider()
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        finalizar_btn = st.form_submit_button("✅ Finalizar compra", use_container_width=True)
    with col_btn2:
        nova_compra_btn = st.form_submit_button("🔄 Finalizar e nova compra", use_container_width=True)

# ==================== PROCESSAMENTO ====================
if finalizar_btn or nova_compra_btn:
    erros = []

    if not nome_comprador.strip():
        erros.append("Preencha seu nome completo.")
    if not email_valido(email_comprador):
        erros.append("O formato do e-mail é inválido.")
    if not whatsapp_valido(whatsapp_comprador):
        erros.append("O número de WhatsApp é inválido. Informe DDD + número.")
    if any(not n.strip() for n in nomes_pagantes) or any(not d.strip() for d in documentos_pagantes):
        erros.append("Preencha nome e documento de todos os participantes pagantes.")
    if any(not n.strip() for n in nomes_criancas) or any(not d.strip() for d in documentos_criancas):
        erros.append("Preencha nome e documento de todas as crianças.")
    if not comprovante:
        erros.append("O comprovante de pagamento é obrigatório.")

    # Confere de novo, na hora do envio, o lote e o estoque (sem cache)
    lote_no_envio = lote_vigente(agora_brasilia())
    if lote_no_envio is None:
        erros.append("As vendas foram encerradas.")
    elif lote_no_envio["nome"] != lote["nome"]:
        erros.append(
            f"O {lote['nome']} acabou de encerrar. Atualize a página (F5): o valor agora é do "
            f"{lote_no_envio['nome']}. Se você já pagou pelo valor anterior, fale com a organização."
        )
    try:
        restante = ESTOQUE_MAX - consultar_total_vendido()
        if qtd_total_pessoas > restante:
            erros.append(
                f"Restam apenas {max(0, restante)} vaga(s) e seu pedido tem {qtd_total_pessoas} pessoa(s). "
                "Atualize a página e ajuste as quantidades."
            )
    except Exception:
        log.exception("Falha ao conferir estoque no envio")
        erros.append("Não foi possível confirmar a disponibilidade agora. Tente novamente em instantes.")

    for e in erros:
        st.error(f"❌ {e}")

    if not erros:
        datahora = agora_brasilia().strftime("%d/%m/%Y %H:%M")
        pagou_credito = forma_pagamento == FORMA_CREDITO
        valor_a_conferir = preco_credito if pagou_credito else preco_pix
        primeiro_nome = nome_comprador.strip().split()[0]
        pedido_registrado = False
        falhas = []

        with st.spinner("Processando sua compra, por favor aguarde..."):
            try:
                supabase.table(TABELA).insert({
                    "nome_comprador": nome_comprador.strip(),
                    "email_comprador": email_comprador.strip(),
                    "whatsapp_comprador": whatsapp_comprador.strip(),
                    "qtd_confra": qtd_total_pessoas,  # pagantes + crianças
                    "qtd_copo": 0,
                    "valor_pix": preco_pix,
                    "valor_credito": preco_credito,
                    "tipo_compra": f"{tipo_compra} - pago via {forma_pagamento}",
                    "link_pagamento": link_pagamento if pagou_credito else "PIX",
                    "nomes_participantes": ", ".join(n.strip() for n in nomes_participantes),
                    "documentos_participantes": ", ".join(d.strip() for d in documentos_participantes),
                    "e_crianca": ", ".join(flags_crianca_str),
                }).execute()
                pedido_registrado = True
            except Exception:
                log.exception("Falha ao gravar o pedido")
                st.error(
                    "❌ Não foi possível registrar seu pedido agora. Guarde seu comprovante, "
                    "tente novamente em instantes e, se persistir, fale com a organização."
                )

            if pedido_registrado:
                linhas_participantes = "\n".join(
                    f"  - {nomes_participantes[i].strip()} | Doc: {documentos_participantes[i].strip()} | "
                    f"Criança: {flags_crianca_str[i]}"
                    for i in range(qtd_total_pessoas)
                )

                # 1) E-mail para a organização (com comprovante e CSV)
                try:
                    destinatarios_admin = [d.strip() for d in (EMAIL_DESTINATARIO or "").split(",") if d.strip()]
                    anexos = [(comprovante.name, comprovante.getvalue())]
                    if ANEXAR_CSV_AO_ADMIN:
                        try:
                            csv_bytes = gerar_csv_pedidos()
                            if csv_bytes:
                                anexos.append(("pedidos_chapiuski_2026.csv", csv_bytes))
                        except Exception:
                            log.exception("Falha ao gerar o CSV de pedidos")
                    corpo_admin = f"""Novo pedido recebido!

COMPRADOR
- Nome: {nome_comprador.strip()}
- E-mail: {email_comprador.strip()}
- WhatsApp: {whatsapp_comprador.strip()}
- Data/hora: {datahora}

PEDIDO
- {tipo_compra}
- Forma de pagamento informada: {forma_pagamento}
- VALOR A CONFERIR NO COMPROVANTE: {brl(valor_a_conferir)}
  (PIX {brl(preco_pix)} | Crédito {brl(preco_credito)})

PARTICIPANTES
{linhas_participantes}

O comprovante está em anexo. Confira o pagamento para validar o pedido.
"""
                    enviar_email(
                        destinatarios_admin,
                        f"Novo pedido - Festa Chapiuski 2026 - {nome_comprador.strip()}",
                        corpo_admin,
                        anexos=anexos,
                    )
                except Exception:
                    log.exception("Falha ao enviar e-mail para a organização")
                    falhas.append(
                        "o aviso à organização não foi enviado. Envie seu comprovante diretamente "
                        "à organização para validar o pedido"
                    )

                # 2) E-mail de resumo para o comprador
                try:
                    itens_html = "".join(
                        f"<li>{escape(nomes_participantes[i].strip())} "
                        f"(Doc: {escape(documentos_participantes[i].strip())})"
                        f"{' - <b>criança, não paga</b>' if flags_crianca_str[i] == 'Sim' else ''}</li>"
                        for i in range(qtd_total_pessoas)
                    )
                    corpo_comprador = f"""
<html>
<body style="font-family: sans-serif;">
  <h2>Olá, {escape(primeiro_nome)}!</h2>
  <p>Recebemos seu pedido para a <b>Festa de Fim de Ano - Chapiuski 2026</b>. 🍻</p>
  <p>A organização vai conferir seu comprovante para validar a compra.</p>
  <hr>
  <h3>Resumo do pedido</h3>
  <ul>
    <li><b>{escape(lote['nome'])}:</b> {qtd_ingressos} ingresso(s) pago(s) e {qtd_criancas} criança(s) gratuita(s)</li>
    <li><b>Forma de pagamento:</b> {escape(forma_pagamento)}</li>
    <li><b>Valor:</b> {brl(valor_a_conferir)}</li>
  </ul>
  <h3>Participantes (levar documento com foto)</h3>
  <ul>{itens_html}</ul>
  <p><b>Sábado, 05/12/2026 - Penha Society (Penha, SP)</b><br>
     Futebol 14h às 16h | Festa 16h às 22h | Pagode ao vivo a partir das 19h</p>
  <hr>
  <p>Obrigado! <b>#ConfraChapiuski2026</b></p>
</body>
</html>
"""
                    enviar_email(
                        [email_comprador.strip()],
                        "✅ Pedido recebido - Festa Chapiuski 2026",
                        corpo_comprador,
                        tipo="html",
                    )
                except Exception:
                    log.exception("Falha ao enviar e-mail para o comprador")
                    falhas.append("o e-mail de resumo não pôde ser enviado; guarde os dados desta tela")

        if pedido_registrado:
            if nova_compra_btn:
                mensagem = (
                    f"Pedido registrado, {primeiro_nome}! Ele será validado após a conferência do comprovante."
                )
                if falhas:
                    mensagem += " Atenção: " + "; ".join(falhas) + "."
                # Limpa o formulário e recarrega, mantendo só a mensagem
                for chave in list(st.session_state.keys()):
                    del st.session_state[chave]
                st.session_state["mensagem_sucesso"] = mensagem
                st.rerun()
            else:
                st.success(f"✅ Compra registrada com sucesso! Obrigado, {primeiro_nome}!")
                st.info(
                    "Seu pedido foi registrado e será validado após a conferência do comprovante "
                    "pela organização. Verifique seu e-mail para o resumo."
                )
                for f in falhas:
                    st.warning(f"⚠️ Atenção: {f}.")
                st.balloons()
