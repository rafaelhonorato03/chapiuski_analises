# app.py
import os
import re
import uuid
from datetime import datetime

import streamlit as st
import pandas as pd
import mercadopago
from supabase import create_client, Client
from dotenv import load_dotenv

# ---------- CONFIG ----------
load_dotenv()  # local dev: use .env; em produção prefira secrets

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
MERCADO_PAGO_ACCESS_TOKEN = os.getenv("MERCADO_PAGO_ACCESS_TOKEN")
# BASE_URL must be the public HTTPS URL where your app (and ideally webhook) is reachable
BASE_URL = os.getenv("BASE_URL")  # ex: "https://meu-app.streamlit.app" or your webhook host

# validações básicas de ambiente
if not all([SUPABASE_URL, SUPABASE_KEY, MERCADO_PAGO_ACCESS_TOKEN]):
    st.error("Faltam variáveis de ambiente: SUPABASE_URL, SUPABASE_KEY ou MERCADO_PAGO_ACCESS_TOKEN.")
    st.stop()

if not BASE_URL:
    st.warning("BASE_URL não configurada. Para pagamentos em produção você precisa informar a URL pública do app/webhook (BASE_URL).")

# clientes
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
sdk = mercadopago.SDK(MERCADO_PAGO_ACCESS_TOKEN)

# ---------- NEGÓCIO ----------
PRECOS = {"Jogador": 150.00, "Torcedor": 115.00}
JOGADORES_FIXOS = {1: "Renan G", 2: "Renato", 3: "Arthur Garcia", 4: "Rafa Crispim", 6: "Kelvim", 7: "Kenneth",
                   8: "Hassan", 9: "Marquezini", 10: "Biel", 11: "Dembele", 12: "Tuaf", 13: "Kauan", 14: "Marrone",
                   17: "João Pedro", 19: "Léo Leite", 20: "Arthur", 21: "Yago", 22: "Zanardo", 23: "Rafa Castilho",
                   28: "Vini Castilho", 29: "Dani R", 35: "Brisa", 43: "Allan", 44: "Felipinho", 71: "Tutão",
                   80: "Gabriel Baby", 89: "Dody", 91: "Vitão", 98: "Askov", 99: "Isaías"}

# ---------- UI ----------
st.set_page_config(page_title="Venda de Camisas 2025 - Chapiuski", page_icon="👕", layout="centered")
st.image("Confra/chapiuski.jpg")
st.title("👕 Venda de Camisas 2025")
st.markdown("---")

st.subheader("Regras para Personalização")
st.info(
    """
    - **Camisa Jogador (R$ 150,00):** Alguns números já são usados por jogadores (veja a lista). Você pode escolher, mas não será exclusivo.
    - **Camisa Torcedor (R$ 115,00):** Pode escolher qualquer nome e número.
    """
)

with st.expander("Ver lista de jogadores com número fixo"):
    df_jogadores = pd.DataFrame(JOGADORES_FIXOS.items(), columns=['Número', 'Jogador'])
    st.table(df_jogadores.set_index('Número'))

# ---------- helpers ----------
def validar_email(email: str) -> bool:
    if not email:
        return False
    return re.match(r"[^@]+@[^@]+\.[^@]+", email) is not None

def criar_preferencia_pagamento(itens_pedido: list, id_externo: str):
    """
    Cria preferência no Mercado Pago e retorna init_point (URL do checkout).
    É recomendado também configurar notification_url (webhook) no painel ou aqui.
    """
    if not BASE_URL:
        st.warning("BASE_URL não definida. O fluxo de retorno e webhook podem não funcionar corretamente.")
    preference_data = {
        "items": itens_pedido,
        "back_urls": {
            "success": f"{BASE_URL}?mp_status=success&id={id_externo}",
            "failure": f"{BASE_URL}?mp_status=failure&id={id_externo}",
            "pending": f"{BASE_URL}?mp_status=pending&id={id_externo}"
        },
        "auto_return": "approved",
        # pede ao Mercado Pago para notificar seu webhook (substitua /webhook/mp pelo endpoint público que você usar)
        "notification_url": f"{BASE_URL}/webhook/mp" if BASE_URL else None,
        "external_reference": id_externo
    }
    try:
        response = sdk.preference().create(preference_data)
        # a estrutura retornada costuma ser {"status":200, "response": {...}}
        init_point = response.get("response", {}).get("init_point")
        return init_point
    except Exception as e:
        st.error(f"Erro ao criar preferência Mercado Pago: {e}")
        return None

# ---------- FORM ----------
with st.form("form_compra"):
    st.subheader("Monte seu Pedido")
    nome_comprador = st.text_input("Seu nome completo")
    email_comprador = st.text_input("Seu e-mail de contato")
    st.markdown("---")
    tipo_camisa = st.radio("Escolha o modelo da camisa", options=["Jogador", "Torcedor"], horizontal=True)
    quantidade = st.number_input("Quantidade", min_value=1, max_value=10, value=1)
    preco_unitario = PRECOS[tipo_camisa]
    st.markdown(f"**Valor total do pedido: R$ {preco_unitario * quantidade:.2f}**")
    st.markdown("---")
    st.subheader("Personalização das Camisas")
    camisas_personalizadas = []
    for i in range(quantidade):
        st.markdown(f"**Camisa {i+1}**")
        nome_na_camisa = st.text_input(f"Nome na Camisa #{i+1}", key=f"nome_{i}")
        numero_na_camisa = st.number_input(f"Número na Camisa #{i+1}", min_value=0, max_value=99, step=1, key=f"num_{i}")
        camisas_personalizadas.append({"nome": nome_na_camisa.strip(), "numero": int(numero_na_camisa)})
    enviado = st.form_submit_button("Finalizar e Ir para Pagamento")

# ---------- PROCESSAMENTO DO FORM ----------
if enviado:
    erros = []
    avisos = []
    if not nome_comprador.strip():
        erros.append("Por favor, preencha seu nome.")
    if not validar_email(email_comprador.strip()):
        erros.append("Por favor, informe um e-mail válido.")
    for camisa in camisas_personalizadas:
        if not camisa["nome"]:
            erros.append(f"Nome da camisa para o número {camisa['numero']} não preenchido.")
        if tipo_camisa == "Jogador" and camisa["numero"] in JOGADORES_FIXOS:
            avisos.append(f"Atenção: O número {camisa['numero']} já é usado pelo jogador {JOGADORES_FIXOS[camisa['numero']]} (não exclusivo).")

    if erros:
        for erro in erros:
            st.error(erro)
    else:
        if avisos:
            st.warning("Avisos sobre sua escolha:")
            for aviso in avisos:
                st.info(aviso)

        # cria pedido no Supabase com status inicial 'pending'
        valor_total = quantidade * preco_unitario
        id_externo = str(uuid.uuid4())
        itens_para_mp = []
        detalhes_pedido = []
        for i, camisa in enumerate(camisas_personalizadas):
            itens_para_mp.append({
                "title": f"Camisa {tipo_camisa} - {camisa['nome']} N°{camisa['numero']}",
                "quantity": 1,
                "unit_price": float(preco_unitario),
                "currency_id": "BRL"
            })
            detalhes_pedido.append(f"{i+1}. {camisa['nome']} N°{camisa['numero']}")

        dados_pedido = {
            "nome_comprador": nome_comprador.strip(),
            "email_comprador": email_comprador.strip().lower(),
            "tipo_camisa": tipo_camisa,
            "quantidade": quantidade,
            "valor_total": float(valor_total),
            "mercado_pago_id": id_externo,
            "status_pagamento": "pending",
            "detalhes_pedido": "; ".join(detalhes_pedido),
            "created_at": datetime.utcnow().isoformat()
        }
        try:
            supabase.table("venda_camisas").insert(dados_pedido).execute()
        except Exception as e:
            st.error(f"Erro ao salvar pedido no Supabase: {e}")
            st.stop()

        link_pagamento = criar_preferencia_pagamento(itens_para_mp, id_externo)
        if link_pagamento:
            st.success("Pedido registrado! Clique no link abaixo para pagar:")
            st.markdown(f"[Pagar R$ {valor_total:.2f}]({link_pagamento})", unsafe_allow_html=True)
            # não fazer redirect automático em produção sem feedback ao usuário
        else:
            st.error("Não foi possível gerar o link de pagamento. Tente novamente mais tarde.")

# ---------- RETORNO via query_params (back_urls) ----------
query_params = st.experimental_get_query_params()
if "mp_status" in query_params:
    status = query_params.get("mp_status", [""])[0]
    pedido_id = query_params.get("id", [""])[0]
    if status == "success":
        st.success("✅ Pagamento aprovado com sucesso! Obrigado pela sua compra.")
        try:
            supabase.table("venda_camisas").update({"status_pagamento": "approved"}).eq("mercado_pago_id", pedido_id).execute()
        except Exception as e:
            st.error(f"Erro ao atualizar pedido: {e}")
    elif status == "failure":
        st.error("❌ Pagamento falhou. Tente novamente.")
    elif status == "pending":
        st.info("Pagamento pendente.")
    # limpa query params visivelmente (não remove histórico do navegador)
    st.experimental_set_query_params()
