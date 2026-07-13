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

# Fallback usado só se a chamada não informar a lista de categorias do grupo
# (ex.: erro ao buscar categorias antes de chamar a Vision).
_CATEGORIAS_PADRAO = [
    "Mercado", "Combustível", "Restaurante", "Farmácia",
    "Lazer", "Educação", "Saúde", "Transporte", "Outros",
]


def _montar_prompt_comprovante(categorias: list[str] | None) -> str:
    """
    Monta o prompt do Vision com a lista de categorias do grupo (Fase 3.1).
    Antes a lista era fixa no prompt; agora reflete categorias customizadas
    por grupo (services/categorias.py), com fallback pro catálogo padrão.
    """
    nomes = categorias if categorias else _CATEGORIAS_PADRAO
    lista = ", ".join(nomes)
    return (
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
        f"- categoria_sugerida: uma de [{lista}]\n"
        "- forma_pagamento: uma de [Cartão, Pix/Dinheiro, Ticket] ou null\n"
        "- numero_cupom: identificador único do cupom (string) ou null\n\n"
        "Responda apenas o JSON, sem explicações."
    )


def analisar_comprovante(
    imagem_bytes: bytes,
    mimetype: str = "image/jpeg",
    categorias: list[str] | None = None,
) -> dict:
    """
    Envia imagem para GPT-4o mini Vision.
    `categorias`: nomes das categorias do grupo do usuário (globais + customizadas,
    ver services/categorias.py). Se None/vazia, usa o catálogo padrão como fallback.
    Retorna dict com: valor, descricao, categoria_sugerida, forma_pagamento.
    """
    b64 = base64.b64encode(imagem_bytes).decode()
    mime = mimetype.split(";")[0].strip()  # remove "; codecs=..." se houver
    prompt = _montar_prompt_comprovante(categorias)

    resp = _client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
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
# Extração de lançamentos de fatura em PDF (Fase 5.3)
# ---------------------------------------------------------------------------

def _montar_prompt_fatura(categorias: list[str] | None) -> str:
    nomes = categorias if categorias else _CATEGORIAS_PADRAO
    lista = ", ".join(nomes)
    return (
        "Você recebe abaixo o texto extraído de uma fatura de cartão de crédito "
        "brasileira. Extraia TODOS os lançamentos individuais (compras) e "
        "responda SOMENTE em JSON válido.\n\n"
        'Formato: {"lancamentos": [{"data": "YYYY-MM-DD", "descricao": "...", '
        '"valor": 123.45, "categoria_sugerida": "..."}]}\n\n'
        "REGRAS OBRIGATÓRIAS:\n"
        "1. 'data': converta pro formato ISO (YYYY-MM-DD). Se a fatura só mostrar "
        "dia/mês, use o ano mais coerente com o restante do documento.\n"
        "2. 'valor': sempre positivo, número decimal com ponto. Formato brasileiro "
        "na fatura: vírgula é decimal, ponto é milhar (ex: '1.234,56' -> 1234.56).\n"
        "3. NÃO inclua o total da fatura, saldo anterior, pagamento recebido, "
        "nem juros/encargos genéricos que não sejam uma compra específica.\n"
        f"4. 'categoria_sugerida': uma de [{lista}].\n\n"
        "Responda apenas o JSON, sem explicações."
    )


def extrair_lancamentos_fatura(texto_pdf: str, categorias: list[str] | None = None) -> list[dict]:
    """
    Fase 5.3 — extrai lançamentos de uma fatura de cartão em PDF (o texto já
    vem extraído via pypdf, ver services/importacao.py:extrair_linhas_pdf).

    AVISO: diferente de analisar_comprovante (Fase 3.1, já validado em uso
    real via bot), esta função não foi testada contra uma fatura real — este
    ambiente de desenvolvimento não tem chave de API da OpenAI nem um
    arquivo de exemplo pra rodar o prompt na prática. Segue o mesmo padrão
    estrutural (JSON response_format, mesma família de prompt), mas o
    principal risco não coberto é o prompt não generalizar bem entre os
    layouts de fatura muito diferentes de cada banco. Testar com faturas
    reais antes de liberar essa tela pro Lucas usar de verdade.
    """
    prompt = _montar_prompt_fatura(categorias)
    # Corta num limite generoso — fatura legítima raramente passa disso;
    # se passar, é sinal de texto extraído com ruído (ex: PDF mal formatado),
    # não de fatura genuinamente maior.
    texto_truncado = texto_pdf[:15000]

    resp = _client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"{prompt}\n\nTexto da fatura:\n{texto_truncado}"}],
        max_tokens=4000,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content
    try:
        dados = json.loads(content)
        return dados.get("lancamentos", []) or []
    except json.JSONDecodeError:
  