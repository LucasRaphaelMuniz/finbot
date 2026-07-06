"""
app.py — Webhook Flask para Evolution API v2.

Tipos de mensagem tratados:
  - conversation / extendedTextMessage → texto puro → handler.py
  - imageMessage                       → comprovante → ai.py (Vision) → handler.py
  - audioMessage (PTT)                 → voz        → ai.py (Whisper) → handler.py
"""

import os
import httpx
from flask import Flask, request
from dotenv import load_dotenv

load_dotenv()

from handler import processar_mensagem
from ai import analisar_comprovante, transcrever_audio, baixar_midia

app = Flask(__name__)

EVOLUTION_URL      = os.getenv("EVOLUTION_API_URL", "").rstrip("/")
EVOLUTION_KEY      = os.getenv("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "")


# ---------------------------------------------------------------------------
# Envio de resposta via Evolution API
# ---------------------------------------------------------------------------

def enviar_mensagem(jid: str, texto: str):
    try:
        httpx.post(
            f"{EVOLUTION_URL}/message/sendText/{EVOLUTION_INSTANCE}",
            json={"number": jid, "text": texto},
            headers={"apikey": EVOLUTION_KEY},
            timeout=15,
        )
    except Exception as e:
        print(f"[Finbot SEND ERROR] {e}")


# ---------------------------------------------------------------------------
# Extração de metadados do payload Evolution
# ---------------------------------------------------------------------------

def obter_telefone_e_jid(data: dict) -> tuple[str, str]:
    """
    Retorna (telefone_do_remetente, jid_para_resposta).
    Em grupos, telefone = participante; jid = grupo.
    """
    key = data.get("key", {})
    jid = key.get("remoteJid", "")

    if jid.endswith("@g.us"):
        telefone = key.get("participant", jid)
    else:
        telefone = jid

    return telefone, jid


def obter_texto(msg: dict) -> str | None:
    if "conversation" in msg:
        return msg["conversation"]
    if "extendedTextMessage" in msg:
        return msg["extendedTextMessage"].get("text", "")
    return None


# ---------------------------------------------------------------------------
# Webhook principal
# ---------------------------------------------------------------------------

@app.route("/webhook", methods=["POST"])
@app.route("/webhook/<path:event_path>", methods=["POST"])
def webhook(event_path=None):
    payload = request.get_json(silent=True)
    if not payload:
        return "", 200

    # Evolution v2 envelopa em "data" para events messages.upsert
    event = payload.get("event", "")
    if event != "messages.upsert":
        return "", 200

    data = payload.get("data", {})
    key  = data.get("key", {})

    # Ignora mensagens próprias e de status
    if key.get("fromMe", False):
        return "", 200
    if key.get("remoteJid") == "status@broadcast":
        return "", 200

    msg = data.get("message", {})
    if not msg:
        return "", 200

    telefone, jid = obter_telefone_e_jid(data)
    resposta       = None

    # ── Texto puro ──────────────────────────────────────────────────────────
    texto = obter_texto(msg)
    if texto:
        resposta = processar_mensagem(telefone, texto.strip())

    # ── Imagem (comprovante) ────────────────────────────────────────────────
    elif "imageMessage" in msg:
        caption  = msg["imageMessage"].get("caption", "")
        mimetype = msg["imageMessage"].get("mimetype", "image/jpeg")
        try:
            imagem_bytes = baixar_midia(data)
            dados = analisar_comprovante(imagem_bytes, mimetype)

            valor = dados.get("valor")
            if not valor:
                resposta = (
                    "🔍 Não consegui identificar o valor no comprovante.\n"
                    "Digite o valor manualmente (ex: *50 mercado cartão*)."
                )
            else:
                # Monta texto sintético com os dados extraídos + legenda do usuário
                partes = [
                    str(valor),
                    dados.get("descricao", ""),
                    dados.get("categoria_sugerida", ""),
                    dados.get("forma_pagamento") or "",
                    caption,
                ]
                texto_sintetico = " ".join(p for p in partes if p).strip()
                resultado = processar_mensagem(telefone, texto_sintetico)
                resposta  = f"📄 _Comprovante lido pela IA_\n\n{resultado}"

        except Exception as e:
            print(f"[AI Vision ERROR] {e}")
            resposta = "😕 Erro ao ler o comprovante. Tente digitar o gasto manualmente."

    # ── Áudio PTT (voz) ─────────────────────────────────────────────────────
    elif "audioMessage" in msg:
        mimetype = msg["audioMessage"].get("mimetype", "audio/ogg; codecs=opus")
        try:
            audio_bytes  = baixar_midia(data)
            transcricao  = transcrever_audio(audio_bytes, mimetype)
            resultado    = processar_mensagem(telefone, transcricao)
            resposta     = f"🎤 _Ouvi: \"{transcricao}\"_\n\n{resultado}"

        except Exception as e:
            print(f"[AI Audio ERROR] {e}")
            resposta = "😕 Não consegui entender o áudio. Tente digitar o gasto."

    # ── Tipo não suportado ───────────────────────────────────────────────────
    else:
        # Documentos, stickers, etc. — ignora silenciosamente
        return "", 200

    if resposta:
        enviar_mensagem(jid, resposta)

    return "", 200


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
