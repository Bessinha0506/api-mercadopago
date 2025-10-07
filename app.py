# app.py - Versão Final com Logging Profissional

from flask import Flask, request, jsonify
import mercadopago
import requests
import os
import logging
import sys # Importar sys para direcionar o log

app = Flask(__name__)

# --- CONFIGURAÇÃO DO LOGGING ---
# Configura o logger para ser mais robusto que o print()
# Isso garante que as mensagens aparecerão nos logs do Render.
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]',
    stream=sys.stdout # Direciona a saída para o console, onde o Render a captura
)


# ===============================
# ROTA DE STATUS (RAIZ)
# ===============================
@app.route("/")
def index():
    app.logger.info("Rota de status foi acessada.")
    return jsonify({
        "status": "online",
        "message": "API Versão 2 - AGORA VAI!"
    })


# --- CONFIGURAÇÃO DAS VARIÁVEIS DE AMBIENTE ---
MERCADO_PAGO_TOKEN = os.environ.get("MERCADO_PAGO_TOKEN")
ASPNET_API_URL = os.environ.get("ASPNET_API_URL")

if not MERCADO_PAGO_TOKEN:
    app.logger.error("A variável de ambiente MERCADO_PAGO_TOKEN não foi definida.")
    raise ValueError("A variável de ambiente MERCADO_PAGO_TOKEN não foi definida.")
if not ASPNET_API_URL:
    app.logger.error("A variável de ambiente ASPNET_API_URL não foi definida.")
    raise ValueError("A variável de ambiente ASPNET_API_URL não foi definida.")

sdk = mercadopago.SDK(MERCADO_PAGO_TOKEN)


# ===============================
# ROTA PARA CRIAR PREFERÊNCIA DE PAGAMENTO
# ===============================
@app.route("/criar_preferencia", methods=["POST"])
def criar_preferencia():
    dados = request.json
    app.logger.info(f"Dados recebidos para criar preferência: {dados}")

    if not dados:
        app.logger.warning("Corpo da requisição está vazio ou não é JSON.")
        return jsonify({"error": "Corpo da requisição está vazio ou não é JSON"}), 400

    pedido_id = dados.get("pedido_id")
    if not pedido_id:
        app.logger.warning("O campo 'pedido_id' é obrigatório, mas não foi encontrado.")
        return jsonify({"error": "O campo 'pedido_id' é obrigatório"}), 400

    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not render_url:
        app.logger.error("Não foi possível determinar a URL externa do serviço (RENDER_EXTERNAL_URL).")
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
    
    app.logger.info(f"Enviando para o Mercado Pago: {preference_data}")

    try:
        preference_response = sdk.preference().create(preference_data)
        return jsonify(preference_response["response"])
    except Exception as e:
        app.logger.error(f"Erro ao criar preferência no Mercado Pago: {e}")
        return jsonify({"error": "Falha ao se comunicar com a API do Mercado Pago"}), 500


# ===============================
# ROTA DE WEBHOOK
# ===============================
@app.route("/webhook", methods=["POST"])
def webhook():
    app.logger.info("===================================")
    app.logger.info("Webhook recebido!")
    
    query_params = request.args
    data_payload = request.json
    app.logger.info(f"Query Params: {query_params}")
    app.logger.info(f"JSON Payload: {data_payload}")

    payment_id = None
    if data_payload and data_payload.get("type") == "payment":
        payment_id = data_payload.get("data", {}).get("id")
    if not payment_id:
        payment_id = query_params.get("data.id")
        app.logger.info(f"Payment ID obtido dos query_params: {payment_id}")

    if payment_id:
        try:
            payment_info = sdk.payment().get(payment_id)
            payment_response = payment_info.get("response", {})
            status = payment_response.get("status")
            pedido_id = payment_response.get("external_reference")

            app.logger.info(f"Status do pagamento {payment_id} (pedido {pedido_id}) atualizado para: {status}")

            if pedido_id:
                app.logger.info(f"Enviando notificação para a API .NET em {ASPNET_API_URL}...")
                response_dotnet = requests.post(
                    ASPNET_API_URL,
                    json={"pedido_id": int(pedido_id), "status": status, "payment_id": int(payment_id)}
                )
                app.logger.info(f"Resposta da API .NET: Status {response_dotnet.status_code}, Corpo: {response_dotnet.text}")
            else:
                app.logger.warning("external_reference (pedido_id) não encontrada no pagamento.")
        
        except Exception as e:
            app.logger.error(f"ERRO CRÍTICO ao processar webhook ou chamar a API .NET: {e}")

    return jsonify({"status": "ok"}), 200
