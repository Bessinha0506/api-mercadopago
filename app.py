# app.py - VERSÃO FINAL DE PRODUÇÃO (COM REDIRECIONAMENTO)

from flask import Flask, request, jsonify, render_template_string
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
    
    # URL de destino final para o redirecionamento
    redirect_url_final = "https://www.photofind.com.br/Conta/Pedidos"

    preference_data = {
        "items": [{"title": dados.get("title", "Produto" ), "quantity": 1, "currency_id": "BRL", "unit_price": float(dados.get("unit_price", 0))}],
        "external_reference": str(pedido_id),
        "notification_url": f"{render_url}/webhook",
        # --- NOVO: Adiciona as URLs de retorno ---
        "back_urls": {
            "success": f"{render_url}/pagamento_sucesso?pedido_id={pedido_id}",
            "failure": f"{render_url}/pagamento_falha?pedido_id={pedido_id}",
            "pending": f"{render_url}/pagamento_pendente?pedido_id={pedido_id}"
        },
        "auto_return": "approved" # Retorna automaticamente para a URL de sucesso se o pagamento for aprovado
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

# --- NOVA ROTA: Página de sucesso com redirecionamento ---
@app.route("/pagamento_sucesso")
def pagamento_sucesso():
    # URL de destino final para o redirecionamento
    redirect_url_final = "http://localhost:52415/Conta/Pedidos"
    
    # Template HTML com JavaScript para a contagem regressiva
    html_template = """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Pagamento Aprovado!</title>
        <style>
            body { font-family: Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; text-align: center; background-color: #f0f2f5; }
            .container { padding: 20px; background-color: white; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1 ); }
            h1 { color: #28a745; }
            p { font-size: 1.2em; }
            #countdown { font-weight: bold; color: #007bff; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Pagamento realizado com sucesso!</h1>
            <p>Obrigado pela sua compra.</p>
            <p>Você será redirecionado para a sua lista de pedidos em <span id="countdown">5</span> segundos...</p>
        </div>
        <script>
            (function() {
                let countdown = 5;
                const countdownElement = document.getElementById('countdown');
                const redirectUrl = "{{ redirect_url_final }}";
                
                const interval = setInterval(() => {
                    countdown--;
                    countdownElement.textContent = countdown;
                    if (countdown <= 0) {
                        clearInterval(interval);
                        window.location.href = redirectUrl;
                    }
                }, 1000);
            })();
        </script>
    </body>
    </html>
    """
    # Renderiza o HTML passando a URL de destino para o template
    return render_template_string(html_template, redirect_url_final=redirect_url_final)

# --- (Opcional) Rotas para falha e pendente ---
@app.route("/pagamento_falha")
def pagamento_falha():
    return "<h1>Ocorreu uma falha no pagamento.</h1><p>Por favor, tente novamente.</p>"

@app.route("/pagamento_pendente")
def pagamento_pendente():
    return "<h1>Seu pagamento está pendente.</h1><p>Aguarde a confirmação ou verifique seu e-mail.</p>"

