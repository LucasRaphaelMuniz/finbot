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
        return []


# ---------------------------------------------------------------------------
# Fallback de IA — classificação de mensagem não reconhecida (Fase 3.6,
# estendida em 24/07/2026 com 'pergunta' e 'comando' — pedido do Lucas: "IA
# precisa entender qual ação tomar" pra comando em linguagem natural, e
# responder perguntas tipo "como registro o pagamento?")
# ---------------------------------------------------------------------------

def _montar_prompt_fallback(texto: str) -> str:
    # Import local (não no topo do módulo) pra evitar ciclo de import:
    # comandos.py não importa nada deste módulo hoje, mas manter a
    # dependência só dentro da função que realmente precisa deixa isso
    # explícito e barato de revisar se um dia comandos.py crescer.
    from comandos import cmd_ajuda

    referencia = cmd_ajuda()
    return (
        "Você é o classificador de intenção do Finbot, um bot financeiro em "
        "português. A mensagem abaixo do usuário NÃO tem um valor numérico "
        "claro nem bate na sintaxe EXATA de nenhum comando conhecido. Decida "
        "a intenção mais provável usando a REFERÊNCIA DE COMANDOS abaixo — "
        "ela é a ÚNICA fonte de verdade sobre o que o bot sabe fazer; nunca "
        "invente uma funcionalidade que não está nela.\n\n"
        "REFERÊNCIA DE COMANDOS DO FINBOT:\n"
        f"{referencia}\n\n"
        "Responda SOMENTE em JSON com as chaves:\n"
        "- intencao: uma de ['gasto', 'ajuda', 'pergunta', 'comando', "
        "'consulta_dados', 'consulta_contas', 'marcar_conta_paga', "
        "'indefinido']\n"
        "  'gasto' só se você conseguir extrair um valor em reais razoavelmente "
        "confiável (ex: número por extenso, valor com erro de digitação). "
        "Caso contrário, use 'indefinido' — não invente valor.\n"
        "  'pergunta' quando o usuário está perguntando COMO fazer algo no bot "
        "(ex: 'como registro o pagamento?', 'como eu adiciono uma categoria?') "
        "— dúvida sobre o FUNCIONAMENTO do bot, não sobre os dados dele.\n"
        "  'comando' quando o usuário quer EXECUTAR uma ação que existe na "
        "referência, mas escreveu em linguagem natural em vez da sintaxe exata "
        "(ex: 'adiciona a Yasmin com o numero 44912345678 no grupo' -> comando "
        "'grupo add 44912345678').\n"
        "  'consulta_dados' quando o usuário pergunta sobre o PRÓPRIO histórico "
        "de gastos numa categoria (ex: 'qual foi o último dia que abasteci o "
        "carro?', 'quando foi minha última ida ao mercado?') — pergunta sobre "
        "OS DADOS dele, não sobre como usar o bot. Hoje só cobre 'quando foi a "
        "última vez que registrei um gasto em <categoria>' — se a pergunta for "
        "outra coisa sobre os dados (soma, período, comparação), use "
        "'indefinido' em vez de forçar 'consulta_dados'.\n"
        "  'consulta_contas' quando o usuário pergunta sobre as CONTAS DO MÊS "
        "— o que falta pagar e o que já foi pago (ex: 'quais são as contas do "
        "mês?', 'o que ainda falta pagar?', 'me mostra o que já foi pago'). "
        "Diferente de 'consulta_dados' (que é sobre gastos por categoria).\n"
        "  'marcar_conta_paga' quando o usuário está AVISANDO que pagou algo "
        "que está em aberto nas contas do mês (ex: 'paguei a fatura do "
        "cartão', 'já paguei o consórcio', 'quitei a conta de luz') — NUNCA "
        "use pra registrar um gasto novo (isso é 'gasto'); use só quando fica "
        "claro que é uma conta JÁ EXISTENTE sendo dada como paga.\n"
        "- valor: número decimal (ex: 50.0) se intencao='gasto', senão null\n"
        "- categoria_sugerida: nome curto da categoria — do gasto (se "
        "intencao='gasto') ou da consulta (se intencao='consulta_dados', ex: "
        "'Combustível' pra pergunta sobre abastecer o carro); senão null\n"
        "- forma_sugerida: 'Cartão', 'Pix' ou 'Ticket' (ou null)\n"
        "- descricao: texto curto descrevendo o gasto, ou null\n"
        "- resposta: SÓ quando intencao='pergunta' — resposta objetiva em "
        "português, baseada SOMENTE na referência acima. Se a referência não "
        "cobrir a dúvida, diga honestamente que essa funcionalidade ainda não "
        "existe no bot, em vez de inventar um jeito de fazer.\n"
        "- comando_sugerido: SÓ quando intencao='comando' — o comando na "
        "sintaxe EXATA da referência, já preenchido com os dados extraídos da "
        "mensagem (ex: 'grupo add 44912345678'). Se faltar um dado "
        "obrigatório que a mensagem não informou (ex: pediu pra adicionar "
        "alguém mas só deu o nome, sem telefone), use intencao='pergunta' e "
        "explique em 'resposta' o que falta informar — NUNCA invente um dado "
        "que não está na mensagem.\n"
        "- descricao_acao: SÓ quando intencao='comando' — frase curta "
        "explicando o que o comando vai fazer, pra mostrar numa confirmação "
        "antes de executar (ex: 'Adicionar +55 44 91234-5678 ao seu grupo').\n\n"
        f"Mensagem do usuário: {texto}\n\n"
        "Responda apenas o JSON, sem explicações."
    )


def classificar_mensagem(texto: str) -> dict:
    """
    Fase 3.6 — fallback de IA para mensagens que não batem em nenhum comando
    nem têm valor extraído pelo parser regex. `services/ai_fallback.py` já
    filtra os casos baratos ("ajuda"/"cancelar") antes de chegar aqui, então
    esta função só é chamada quando vale a pena gastar 1 requisição de LLM.

    A EXECUÇÃO de 'comando' e a validação de que 'comando_sugerido' é mesmo
    um comando real do bot (não uma alucinação da IA) acontecem em
    services/ai_fallback.py + handler.py, não aqui — esta função só
    classifica e devolve o JSON cru.
    """
    prompt = _montar_prompt_fallback(texto)
    resp = _client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"intencao": "indefinido"}


# ---------------------------------------------------------------------------
# Alocação de gasto por entendimento da mensagem (24/07/2026) — completa
# categoria/forma quando o casamento por palavra-chave (parser.py) não achou
# nada, mas o VALOR já foi extraído com certeza (ex: "50 remédio" -> valor
# certo, mas "remédio" não está em nenhum alias de categoria). Só chamada
# nesse caso pontual (ver services/ai_fallback.py::completar_categoria_forma)
# — não em toda mensagem de gasto, pra não custar 1 chamada de LLM em 100%
# dos registros.
# ---------------------------------------------------------------------------

def _montar_prompt_categoria_forma(texto: str, categorias: list[str], formas: list[str]) -> str:
    return (
        "Classifique o gasto abaixo (mensagem em português, moeda brasileira) "
        "usando APENAS as listas fornecidas — não sugira nada fora delas.\n\n"
        f"Categorias disponíveis: [{', '.join(categorias)}]\n"
        f"Formas de pagamento disponíveis: [{', '.join(formas)}]\n\n"
        "Responda SOMENTE em JSON com as chaves:\n"
        "- categoria_sugerida: uma categoria da lista acima, ou null se não "
        "tiver certeza razoável\n"
        "- forma_sugerida: uma forma da lista acima, ou null se a mensagem não "
        "der nenhuma pista de como foi pago\n\n"
        f"Mensagem: {texto}\n\n"
        "Responda apenas o JSON, sem explicações."
    )


def sugerir_categoria_forma(texto: str, categorias: list[str], formas: list[str]) -> dict:
    """Retorna {'categoria_sugerida': str|None, 'forma_sugerida': str|None}."""
    prompt = _montar_prompt_categoria_forma(texto, categorias, formas)
    resp = _client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {}


# ---------------------------------------------------------------------------
# Correção de um comando pendente (24/07/2026)
#
# "falei errado, o nome correto é teste123" não significa nada sozinho — só
# faz sentido colado no comando que está esperando confirmação. Por isso
# esta função recebe os DOIS e devolve a versão corrigida, em vez de tentar
# classificar a frase isolada (que é o que classificar_mensagem faria).
# ---------------------------------------------------------------------------

def corrigir_comando(comando_pendente: str, mensagem: str) -> dict:
    """
    Retorna {'comando_sugerido': str|None, 'descricao_acao': str|None}.
    comando_sugerido = None quando a mensagem não é uma correção aplicável
    (quem chama decide o que fazer — ver services/ai_fallback.py).
    """
    from comandos import cmd_ajuda

    prompt = (
        "O usuário do Finbot (bot financeiro em português) pediu uma ação e "
        "o bot montou o comando abaixo, aguardando confirmação. Em vez de "
        "confirmar, o usuário mandou uma mensagem CORRIGINDO o pedido.\n\n"
        f"COMANDO PENDENTE: {comando_pendente}\n"
        f"MENSAGEM DE CORREÇÃO DO USUÁRIO: {mensagem}\n\n"
        "REFERÊNCIA DE COMANDOS DO FINBOT (única fonte de verdade sobre a "
        "sintaxe — nunca invente comando fora dela):\n"
        f"{cmd_ajuda()}\n\n"
        "Aplique a correção sobre o comando pendente, preservando tudo que o "
        "usuário NÃO pediu pra mudar. Responda SOMENTE em JSON:\n"
        "- comando_sugerido: o comando corrigido, na sintaxe EXATA da "
        "referência. Se a mensagem não for uma correção aplicável a este "
        "comando (ex: assunto totalmente diferente), use null.\n"
        "- descricao_acao: frase curta explicando o que o comando corrigido "
        "vai fazer, pra mostrar numa nova confirmação.\n\n"
        "Exemplo: pendente 'forma add teste 2999' + correção 'falei errado, "
        "o nome correto é teste123' -> comando_sugerido "
        "'forma add teste123 2999' (o limite 2999 é preservado, só o nome "
        "muda).\n\n"
        "Responda apenas o JSON, sem explicações."
    )

    resp = _client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
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
