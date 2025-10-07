from flask import Flask, request, jsonify
import mercadopago
import requests
import os

app = Flask(__name__)

# ===============================
# NOVA ROTA DE STATUS (RAIZ)
# ===============================
@app.route("/")
def index():
    return jsonify({
        "status": "online",
        "message": "API do Mercado Pago está operacional."
    })
# ===============================

# O resto do seu código permanece o mesmo...

MERCADO_PAGO_TOKEN = os.environ.get("MERCADO_PAGO_TOKEN")
ASPNET_API_URL = os.environ.get("ASPNET_API_URL")

if not MERCADO_PAGO_TOKEN:
    raise ValueError("A variável de ambiente MERCADO_PAGO_TOKEN não foi definida no Render.")
if not ASPNET_API_URL:
    raise ValueError("A variável de ambiente ASPNET_API_URL não foi definida no Render.")

sdk = mercadopago.SDK(MERCADO_PAGO_TOKEN)

@app.route("/criar_preferencia", methods=["POST"])
def criar_preferencia():
    # ... (todo o código desta função continua igual)
    dados = request.json
    if not dados:
        return jsonify({"error": "Corpo da requisição está vazio"}), 400

    pedido_id = dados.get("pedido_id")
    if not pedido_id:
        return jsonify({"error": "O campo 'pedido_id' é obrigatório"}), 400

    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not render_url:
        return jsonify({"error": "Não foi possível determinar a URL externa do serviço."}), 500

    preference_data = {
        "items": [
            {
                "title": dados.get("title", "Produto Padrão"),
                "quantity": int(dados.get("quantity", 1)),
                "currency_id": "BRL",
                "unit_price": float(dados.get("unit_price", 0))
            }
        ],
        "external_reference": str(pedido_id),
        "notification_url": f"{render_url}/webhook"
    }

    try:
        preference_response = sdk.preference().create(preference_data)
        return jsonify(preference_response["response"])
    except Exception as e:
        print(f"ERRO ao criar preferência: {e}")
        return jsonify({"error": "Falha ao se comunicar com a API do Mercado Pago"}), 500


@app.route("/webhook", methods=["POST"])
def webhook():
    # ... (todo o código desta função continua igual)
    data_payload = request.json
    payment_id = None

    if data_payload and data_payload.get("type") == "payment":
        payment_id = data_payload.get("data", {}).get("id")
    
    if payment_id:
        try:
            payment_info = sdk.payment().get(payment_id)
            payment_response = payment_info.get("response", {})
            status = payment_response.get("status")
            pedido_id = payment_response.get("external_reference")

            if pedido_id:
                requests.post(
                    ASPNET_API_URL,
                    json={"pedido_id": int(pedido_id), "status": status, "payment_id": int(payment_id)}
                )
        except Exception as e:
            print(f"ERRO ao processar webhook: {e}")

    return jsonify({"status": "ok"}), 200
