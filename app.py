import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv

load_dotenv()

from handler import processar_mensagem

app = Flask(__name__)


@app.route("/webhook", methods=["POST"])
def webhook():
    telefone = request.form.get("From", "").strip()
    mensagem = request.form.get("Body", "").strip()

    if not telefone or not mensagem:
        return str(MessagingResponse())

    resposta = processar_mensagem(telefone, mensagem)

    resp = MessagingResponse()
    resp.message(resposta)
    return str(resp)


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
