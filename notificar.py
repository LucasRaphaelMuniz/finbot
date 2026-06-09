import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

_client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
_from = os.getenv("TWILIO_WHATSAPP_NUMBER")


def enviar_notificacao(para_telefone: str, mensagem: str):
    telefone = para_telefone if para_telefone.startswith("whatsapp:") else f"whatsapp:{para_telefone}"
    try:
        _client.messages.create(from_=_from, to=telefone, body=mensagem)
    except Exception as exc:
        print(f"[Finbot NOTIFY ERROR] {exc}")
