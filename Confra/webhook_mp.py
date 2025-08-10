# webhook_mp.py
from flask import Flask, request, jsonify
import os
import mercadopago
from supabase import create_client

app = Flask(__name__)
sdk = mercadopago.SDK(os.environ["MERCADO_PAGO_ACCESS_TOKEN"])
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

@app.route("/webhook/mp", methods=["POST"])
def webhook_mp():
    # Mercado Pago envia {"type":"payment", "data": {"id": <payment_id>}, ...}
    payload = request.get_json(silent=True) or {}
    payment_id = payload.get("data", {}).get("id")
    # opcional: validar assinatura/header aqui (veja docs)
    if payment_id:
        try:
            mp_resp = sdk.payment().get(payment_id)
            payment = mp_resp.get("response", {})
            external_ref = payment.get("external_reference")
            status = payment.get("status")  # ex: approved, pending, rejected
            if external_ref:
                supabase.table("venda_camisas").update({"status_pagamento": status}).eq("mercado_pago_id", external_ref).execute()
        except Exception as e:
            # logar erro
            print("Erro ao buscar pagamento/atualizar supabase:", e)
            return jsonify({"ok": False}), 500
    return jsonify({"ok": True}), 200

if __name__ == "__main__":
    app.run(port=5000)
