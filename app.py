# app.py - VERSÃO FINAL DE PRODUÇÃO

from flask import Flask, request, jsonify
import mercadopago
import requests
import os
import logging
import sys
import threading

app = Flask(__name__)

# --- Configuração do Logging Profissional ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]',
    stream=sys.stdout
)

# --- Função que faz o trabalho pesado em segundo plano ---
def process_payment(payment_id, app_context):
    with app_context:
        app.logger.info(f"[THREAD] Iniciando processamento para o pagamento {payment_id}...")
        try:
            payment_info = sdk.payment().get(payment_id)
            payment_response = payment_info.get("response", {})
            status = payment_response.get("status")
            pedido_id = payment_response.get("external_reference")

            app.logger.info(f"[THREAD] Status do pagamento {payment_id} (pedido {pedido_id}) atualizado para: {status}")

            if pedido_id:
                app.logger.info(f"[THREAD] Enviando notificação para a API .NET em {ASPNET_API_URL}...")
                response_dotnet = requests.post(
                    ASPNET_API_URL,
                    json={"pedido_id": int(pedido_id), "status": status, "payment_id": int(payment_id)},
                    timeout=10
                )
                app.logger.info(f"[THREAD] Resposta da API .NET: Status {response_dotnet.status_code}, Corpo: {response_dotnet.text}")
            else:
                app.logger.warning("[THREAD] external_reference (pedido_id) não encontrada no pagamento.")
        
        except Exception as e:
            app.logger.error(f"[THREAD] ERRO CRÍTICO ao processar webhook: {e}")

# --- Rota de Status (/) ---
@app.route("/")
def index():
    return jsonify({"status": "online", "message": "API de Pagamentos está operacional."})

# --- Configuração das Variáveis de Ambiente ---
MERCADO_PAGO_TOKEN = os.environ.get("MERCADO_PAGO_TOKEN")
ASPNET_API_URL = os.environ.get("ASPNET_API_URL")
sdk = mercadopago.SDK(MERCADO_PAGO_TOKEN)

# --- Rota para Criar Preferência de Pagamento ---
@app.route("/criar_preferencia", methods=["POST"])
def criar_preferencia():
    dados = request.json
    app.logger.info(f"Dados recebidos para criar preferência: {dados}")
    pedido_id = dados.get("pedido_id")
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    
    preference_data = {
        "items": [{"title": dados.get("title", "Produto"), "quantity": 1, "currency_id": "BRL", "unit_price": float(dados.get("unit_price", 0))}],
        "external_reference": str(pedido_id),
        "notification_url": f"{render_url}/webhook"
    }
    
    app.logger.info(f"Enviando para o Mercado Pago: {preference_data}")
    preference_response = sdk.preference().create(preference_data)
    return jsonify(preference_response["response"])

# --- Rota de Webhook (Rápida e Assíncrona) ---
@app.route("/webhook", methods=["POST"])
def webhook():
    app.logger.info("Webhook recebido! Respondendo OK e iniciando processo em background.")
    
    query_params = request.args
    payment_id = query_params.get("data.id")
    
    if payment_id:
        thread = threading.Thread(target=process_payment, args=(payment_id, app.app_context()))
        thread.start()
    else:
        app.logger.warning("Webhook recebido sem data.id nos parâmetros da query.")

    return jsonify({"status": "notification received"}), 200

