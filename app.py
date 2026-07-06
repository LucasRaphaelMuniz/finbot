"""
app.py — Webhook Flask para Evolution API v2.

Tipos de mensagem tratados:
  - conversation / extendedTextMessage → texto puro → handler.py
  - imageMessage                       → comprovante → ai.py (Vision) → handler.py
  - audioMessage (PTT)                 → voz        → ai.py (Whisper) → handler.py
"""

import os
import re
import httpx
from datetime import datetime, timedelta, timezone
from flask import Flask, request
from dotenv import load_dotenv

load_dotenv()

from handler import processar_mensagem
from ai import analisar_comprovante, transcrever_audio, baixar_midia

app = Flask(__name__)

EVOLUTION_URL      = os.getenv("EVOLUTION_API_URL", "").rstrip("/")

# Cache em memória para detecção de duplicatas (cupom → timestamp)
_cupons_recentes: dict[str, datetime] = {}
_JANELA_DUPLICATA = timedelta(minutes=10)
EVOLUTION_KEY      = os.getenv("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "")


# ---------------------------------------------------------------------------
# Detecção de duplicata de comprovante
# ---------------------------------------------------------------------------

def _e_duplicata(telefone: str, valor: float, numero_cupom: str | None) -> bool:
    """Retorna True se este comprovante já foi registrado nos últimos 10 minutos."""
    agora = datetime.now(timezone.utc)
    # Limpa entradas expiradas
    expirados = [k for k, t in _cupons_recentes.items() if agora - t > _JANELA_DUPLICATA]
    for k in expirados:
        del _cupons_recentes[k]

    # Chave: cupom fiscal (se disponível) ou telefone+valor
    chave = f"{telefone}:{numero_cupom}" if numero_cupom else f"{telefone}:{valor}"

    if chave in _cupons_recentes:
        return True

    _cupons_recentes[chave] = agora
    return False


# ---------------------------------------------------------------------------
# Envio de resposta via Evolution API
# ---------------------------------------------------------------------------

def enviar_mensagem(jid: str, texto: str):
    try:
        httpx.post(
            f"{EVOLUTION_URL}/message/sendText/{EVOLUTION_INSTANCE}",
            json={"number": jid, "text": texto},
            headers={"apikey": EVOLUTION_KEY},
            timeout=45,
        )
    except Exception as e:
        print(f"[Finbot SEND ERROR] {e}")


# ---------------------------------------------------------------------------
# Extração de metadados do payload Evolution
# ---------------------------------------------------------------------------

def _normalizar_jid(jid: str) -> str | None:
    """
    Converte qualquer formato de JID para o formato canônico: DIGITS@s.whatsapp.net
    Retorna None para JIDs inválidos, de grupo (@g.us) ou de dispositivo (@lid).
    """
    if not jid:
        return None
    if "@g.us" in jid:   # JID de grupo — não é um usuário
        return None
    if "@lid" in jid:    # Linked Device ID — identificador instável, ignorar
        return None
    # Remove prefixo legado "whatsapp:+" ou "whatsapp:"
    jid = re.sub(r"^whatsapp:\+?", "", jid)
    jid = jid.lstrip("+")
    if "@s.whatsapp.net" in jid:
        return jid
    digits = re.sub(r"\D", "", jid)
    return (digits + "@s.whatsapp.net") if digits else None


def obter_telefone_e_jid(data: dict) -> tuple[str | None, str]:
    """
    Retorna (telefone_normalizado, jid_para_resposta).
    - telefone: DIGITS@s.whatsapp.net ou None se inválido
    - jid: para onde enviar a resposta (pode ser grupo @g.us)

    Evolution API v2 com multi-device usa @lid como participant,
    mas disponibiliza participantAlt e sender com o número real.
    """
    key    = data.get("key", {})
    remote = key.get("remoteJid", "")

    if remote.endswith("@g.us"):
        # Mensagem de grupo
        participant = key.get("participant", "")
        if "@lid" in participant:
            # Multi-device: usa participantAlt (número real)
            participant = data.get("participantAlt", "") or participant
        return _normalizar_jid(participant), remote
    else:
        # Mensagem direta
        telefone = _normalizar_jid(remote)
        if not telefone:
            # remoteJid é @lid: tenta o campo sender
            sender = data.get("sender", "")
            telefone = _normalizar_jid(sender)
        return telefone, remote


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
    if not telefone:
        # @lid (linked device) ou formato desconhecido — ignora silenciosamente
        return "", 200
    resposta = None

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

            valor        = dados.get("valor")
            numero_cupom = dados.get("numero_cupom")

            if not valor:
                resposta = (
                    "🔍 Não consegui identificar o valor total no comprovante.\n"
                    "Digite o valor manualmente (ex: *50 mercado cartão*)."
                )
            elif _e_duplicata(telefone, valor, numero_cupom):
                resposta = (
                    f"⚠️ Este comprovante de *R$ {str(valor).replace('.', ',')}* "
                    "parece já ter sido registrado.\n"
                    "Se for um gasto diferente, digite manualmente (ex: *50 mercado cartão*)."
                )
            else:
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
