"""
ai.py — Integração com OpenAI para análise de comprovantes (Vision)
         e transcrição de áudios (Whisper).
"""

import os
import io
import json
import base64
import httpx
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

EVOLUTION_URL      = os.getenv("EVOLUTION_API_URL", "").rstrip("/")
EVOLUTION_KEY      = os.getenv("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "")

# ---------------------------------------------------------------------------
# Download de mídia via Evolution API
# ---------------------------------------------------------------------------

def baixar_midia(message: dict) -> bytes:
    """
    Baixa mídia de uma mensagem via endpoint da Evolution API.
    `message` é o dict completo da mensagem recebida no webhook.
    Retorna os bytes do arquivo.
    """
    url = f"{EVOLUTION_URL}/chat/getBase64FromMediaMessage/{EVOLUTION_INSTANCE}"
    resp = httpx.post(
        url,
        json={"message": message, "convertToMp4": False},
        headers={"apikey": EVOLUTION_KEY},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    b64 = data.get("base64") or data.get("data", {}).get("base64", "")
    return base64.b64decode(b64)


# ---------------------------------------------------------------------------
# Vision — análise de comprovante
# ---------------------------------------------------------------------------

_PROMPT_COMPROVANTE = (
    "Analise este comprovante, nota fiscal ou recibo brasileiro.\n"
    "Responda SOMENTE em JSON válido com as chaves abaixo.\n\n"
    "REGRAS OBRIGATÓRIAS:\n"
    "1. 'valor' deve ser o VALOR TOTAL FINAL pago — procure os campos 'Valor Total', "
    "'Total a Pagar', 'Valor a Pagar', 'Valor Pago' ou 'Total'. NUNCA use subtotais, "
    "valores de itens individuais ou 'Valor Total de Itens'.\n"
    "2. Formato brasileiro: vírgula é decimal, ponto é milhar. "
    "Ex: '73,43' → 73.43 | '1.234,56' → 1234.56\n"
    "3. 'numero_cupom': número do cupom/COO/NFCe para detectar duplicatas (string ou null).\n\n"
    "Chaves do JSON:\n"
    "- valor: número decimal (ex: 73.43) ou null\n"
    "- descricao: nome do estabelecimento (string curta)\n"
    "- categoria_sugerida: uma de [Mercado, Combustível, Restaurante, Farmácia, "
    "Lazer, Educação, Saúde, Transporte, Outros]\n"
    "- forma_pagamento: uma de [Cartão, Pix/Dinheiro, Ticket] ou null\n"
    "- numero_cupom: identificador único do cupom (string) ou null\n\n"
    "Responda apenas o JSON, sem explicações."
)


def analisar_comprovante(imagem_bytes: bytes, mimetype: str = "image/jpeg") -> dict:
    """
    Envia imagem para GPT-4o mini Vision.
    Retorna dict com: valor, descricao, categoria_sugerida, forma_pagamento.
    """
    b64 = base64.b64encode(imagem_bytes).decode()
    mime = mimetype.split(";")[0].strip()  # remove "; codecs=..." se houver

    resp = _client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _PROMPT_COMPROVANTE},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"},
                    },
                ],
            }
        ],
        max_tokens=300,
        response_format={"type": "json_object"},
    )

    content = resp.choices[0].message.content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {}


# ---------------------------------------------------------------------------
# Whisper — transcrição de áudio
# ---------------------------------------------------------------------------

def transcrever_audio(audio_bytes: bytes, mimetype: str = "audio/ogg; codecs=opus") -> str:
    """
    Transcreve áudio (PTT/voz) via Whisper-1 em português.
    Retorna o texto transcrito.
    """
    # Determina extensão pelo mimetype
    mime_base = mimetype.split(";")[0].strip().lower()
    ext_map = {
        "audio/ogg":  "ogg",
        "audio/mpeg": "mp3",
        "audio/mp4":  "mp4",
        "audio/wav":  "wav",
        "audio/webm": "webm",
        "audio/m4a":  "m4a",
    }
    ext = ext_map.get(mime_base, "ogg")

    buf = io.BytesIO(audio_bytes)
    buf.name = f"audio.{ext}"

    transcript = _client.audio.transcriptions.create(
        model="whisper-1",
        file=buf,
        language="pt",
    )
    return transcript.text.strip()
