import streamlit as st
import pandas as pd
import mercadopago
import os
from supabase import create_client, Client
import uuid
from dotenv import load_dotenv

# ==============================================================================
# 1. CONFIGURAÇÕES GERAIS E INICIALIZAÇÃO
# ==============================================================================

st.set_page_config(
    page_title="Venda de Camisas 2025 - Chapiuski",
    page_icon="👕",
    layout="centered"
)

# Carrega as credenciais via Streamlit Secrets
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
MERCADO_PAGO_ACCESS_TOKEN = os.getenv("MERCADO_PAGO_ACCESS_TOKEN")

# Verificação para garantir que as variáveis foram carregadas
if not all([SUPABASE_URL, SUPABASE_KEY, MERCADO_PAGO_ACCESS_TOKEN]):
    st.error("Erro: Uma ou mais variáveis de ambiente (SUPABASE_URL, SUPABASE_KEY, MERCADO_PAGO_ACCESS_TOKEN) não foram encontradas. Verifique seu arquivo .env.")
    st.stop()

# Inicializa clientes
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
sdk = mercadopago.SDK(MERCADO_PAGO_ACCESS_TOKEN)

# ==============================================================================
# 2. DADOS E REGRAS DO NEGÓCIO
# ==============================================================================

# Preços das camisas
PRECOS = {
    "Jogador": 150.00,
    "Torcedor": 115.00
}

# [cite_start]Lista de jogadores com número fixo [cite: 2, 3, 4]
JOGADORES_FIXOS = {
    1: "Renan G", 2: "Renato", 3: "Arthur Garcia", 4: "Rafa Crispim", 6: "Kelvim",
    7: "Kenneth", 8: "Hassan", 9: "Marquezini", 10: "Biel", 11: "Dembele",
    12: "Tuaf", 13: "Kauan", 14: "Marrone", 17: "João Pedro", 19: "Léo Leite",
    20: "Arthur", 21: "Yago", 22: "Zanardo", 23: "Rafa Castilho", 28: "Vini Castilho",
    29: "Dani R", 35: "Brisa", 43: "Allan", 44: "Felipinho", 71: "Tutão",
    80: "Gabriel Baby", 89: "Dody", 91: "Vitão", 98: "Askov", 99: "Isaías"
}

# ==============================================================================
# 3. INTERFACE PRINCIPAL E REGRAS
# ==============================================================================

st.image("Confra/chapiuski.jpg") 
st.title("👕 Venda de Camisas 2025")
st.markdown("---")

st.subheader("Regras para Personalização")
# >>> ALTERAÇÃO AQUI: Texto da regra foi atualizado para refletir a nova lógica.
st.info(
    """
    - [cite_start]**Camisa Jogador (R$ 150,00):** Alguns números já são utilizados por jogadores do time (veja a lista abaixo). Você **pode** escolher um desses números, mas saiba que ele não será exclusivo. [cite: 5, 6, 7]
    - [cite_start]**Camisa Torcedor (R$ 115,00):** Você pode escolher qualquer nome e número, mesmo que já exista. [cite: 6]
    """
)

with st.expander("Ver lista de jogadores com número fixo"):
    df_jogadores = pd.DataFrame(JOGADORES_FIXOS.items(), columns=['Número', 'Jogador'])
    st.table(df_jogadores.set_index('Número'))

# ==============================================================================
# 4. LÓGICA DE PAGAMENTO E FORMULÁRIO
# ==============================================================================

def criar_preferencia_pagamento(itens_pedido, id_externo):
    base_url = st.get_option("server.baseUrl")
    preference_data = {
        "items": itens_pedido, "back_urls": {
            "success": f"{base_url}?mp_status=success&id={id_externo}",
            "failure": f"{base_url}?mp_status=failure&id={id_externo}",
            "pending": f"{base_url}?mp_status=pending&id={id_externo}"
        }, "auto_return": "approved", "external_reference": id_externo
    }
    try:
        response = sdk.preference().create(preference_data)
        return response["response"]["init_point"]
    except Exception as e:
        st.error(f"Erro ao comunicar com o Mercado Pago: {e}")
        return None

with st.form("form_compra"):
    st.subheader("Monte seu Pedido")
    col_comprador1, col_comprador2 = st.columns(2);
    with col_comprador1: nome_comprador = st.text_input("Seu nome completo")
    with col_comprador2: email_comprador = st.text_input("Seu e-mail de contato")
    st.markdown("---")
    col_tipo, col_qtd = st.columns([2, 1]);
    with col_tipo: tipo_camisa = st.radio("Escolha o modelo da camisa", options=["Jogador", "Torcedor"], horizontal=True)
    with col_qtd: quantidade = st.number_input("Quantidade", min_value=1, max_value=10, value=1)
    preco_unitario = PRECOS[tipo_camisa]
    st.markdown(f"**Valor total do pedido: R$ {preco_unitario * quantidade:.2f}**")
    st.markdown("---"); st.subheader("Personalização das Camisas")
    camisas_personalizadas = []
    for i in range(quantidade):
        st.markdown(f"**Camisa {i+1}**"); col_nome, col_num = st.columns(2)
        with col_nome: nome_na_camisa = st.text_input(f"Nome na Camisa #{i+1}", key=f"nome_{i}")
        with col_num: numero_na_camisa = st.number_input(f"Número na Camisa #{i+1}", min_value=0, max_value=99, step=1, key=f"num_{i}")
        camisas_personalizadas.append({"nome": nome_na_camisa, "numero": numero_na_camisa})
    enviado = st.form_submit_button("Finalizar e Ir para Pagamento")

if enviado:
    erros = []
    avisos = [] # >>> ALTERAÇÃO AQUI: Lista para os avisos de duplicidade.

    if not nome_comprador or not email_comprador:
        erros.append("Por favor, preencha seu nome e e-mail.")
    
    # >>> ALTERAÇÃO AQUI: Lógica de validação foi modificada.
    # Agora, em vez de bloquear, ela apenas gera um aviso.
    for camisa in camisas_personalizadas:
        if not camisa["nome"]:
            erros.append(f"O nome da camisa para o número {camisa['numero']} não foi preenchido.")
        # Se for camisa de JOGADOR e o número estiver na lista fixa, cria um AVISO.
        if tipo_camisa == "Jogador" and camisa["numero"] in JOGADORES_FIXOS:
            nome_jogador_existente = JOGADORES_FIXOS[camisa["numero"]]
            avisos.append(f"Atenção: O número **{camisa['numero']}** que você escolheu já é usado pelo jogador **{nome_jogador_existente}**.")

    if erros:
        for erro in erros: st.error(erro)
    else:
        # Mostra os avisos (se houver algum), mas não impede a compra.
        if avisos:
            st.warning("Avisos sobre sua escolha:")
            for aviso in avisos: st.info(aviso)
        
        # O resto do processo continua normalmente
        valor_total = quantidade * preco_unitario
        id_externo = str(uuid.uuid4())
        itens_para_mp = []
        detalhes_pedido_str = []
        for i, camisa in enumerate(camisas_personalizadas):
            itens_para_mp.append({"title": f"Camisa {tipo_camisa} - {camisa['nome']} N°{camisa['numero']}", "quantity": 1, "unit_price": preco_unitario, "currency_id": "BRL"})
            detalhes_pedido_str.append(f"{i+1}. Nome: {camisa['nome']}, N°: {camisa['numero']}")
        try:
            dados_pedido = {"nome_comprador": nome_comprador, "email_comprador": email_comprador, "tipo_camisa": tipo_camisa, "quantidade": quantidade, "valor_total": valor_total, "mercado_pago_id": id_externo, "detalhes_pedido": "; ".join(detalhes_pedido_str)}
            supabase.table("venda_camisas").insert(dados_pedido).execute()
            link_pagamento = criar_preferencia_pagamento(itens_para_mp, id_externo)
            if link_pagamento:
                st.success("Pedido registrado! Redirecionando para o pagamento...")
                st.markdown(f'### [Clique aqui para pagar R$ {valor_total:.2f}]({link_pagamento})', unsafe_allow_html=True)
                st.html(f'<meta http-equiv="refresh" content="0; url={link_pagamento}">')
                st.stop()
        except Exception as e:
            st.error(f"Ocorreu um erro ao salvar seu pedido. Tente novamente. Detalhe: {e}")

# ==============================================================================
# 5. LÓGICA DE RETORNO DO PAGAMENTO
# ==============================================================================
query_params = st.query_params
if "mp_status" in query_params:
    status = query_params["mp_status"]; pedido_id = query_params.get("id")
    if status == "success":
        st.success("✅ Pagamento aprovado com sucesso! Obrigado pela sua compra."); st.balloons()
        try: supabase.table("venda_camisas").update({"status_pagamento": "aprovado"}).eq("mercado_pago_id", pedido_id).execute()
        except Exception as e: st.error(f"Erro ao confirmar seu pedido no sistema: {e}")
    elif status == "failure": st.error("❌ Seu pagamento falhou. Por favor, tente refazer o pedido.")
    st.query_params.clear()