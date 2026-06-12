import os
from contextvars import ContextVar
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

_client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
_from_env = os.getenv("TWILIO_WHATSAPP_NUMBER")

# Número do bot na conversa atual (campo "To" do webhook). Notificar pelo
# mesmo canal que recebeu a mensagem evita erro 63007 quando a variável de
# ambiente aponta para um número sem WhatsApp habilitado.
numero_bot: ContextVar = ContextVar("numero_bot", default=None)


def enviar_notificacao(para_telefone: str, mensagem: str):
    telefone = para_telefone if para_telefone.startswith("whatsapp:") else f"whatsapp:{para_telefone}"
    de = numero_bot.get() or _from_env
    try:
        _client.messages.create(from_=de, to=telefone, body=mensagem)
    except Exception as exc:
        print(f"[Finbot NOTIFY ERROR] {exc}")
