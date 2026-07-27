"""
utils/respostas.py — interpretação de "sim"/"não" do usuário (24/07/2026).

Motivo (pedido do Lucas: "faça de forma que a utilização do usuário seja
fluida"): antes, TODA confirmação do bot aceitava exatamente
("sim", "s", "confirma", "confirmar") e QUALQUER outra coisa cancelava em
silêncio. Na prática, num chat de WhatsApp a pessoa responde "ok", "pode",
"isso", "blz", "👍", "manda" — e perdia o registro sem entender por quê.
Pior: o cancelamento era indistinguível de um "não" de verdade, então o
usuário não tinha nem o sinal de que errou a palavra.

Três estados, não dois — essa é a decisão central deste módulo:
- afirmativo  -> executa
- negativo    -> cancela
- ambíguo     -> NÃO é cancelamento; quem chama pergunta de novo, mantendo a
                 sessão viva (o timeout de 5 min de `sessoes` continua sendo
                 a rede de segurança se a pessoa simplesmente sumir).

Reconhecimento por conjunto curado + prefixo, NÃO por similaridade fuzzy
(SequenceMatcher): "assim", "sem", "sinto" são próximos demais de "sim" e
um falso positivo aqui EXECUTA uma ação que a pessoa não pediu. Num
classificador de confirmação, errar pro lado de "não tenho certeza" (e
perguntar de novo) é sempre mais barato que errar pro lado de agir.
"""

import re
import unicodedata

_AFIRMATIVOS = {
    "sim", "s", "ss", "simm", "sim senhor", "isso", "isso ai", "isso mesmo",
    "ok", "okay", "oks", "blz", "beleza", "claro", "certo", "correto",
    "exato", "exatamente", "positivo", "perfeito", "show", "otimo", "boa",
    "pode", "pode sim", "pode ser", "pode registrar", "pode mandar",
    "manda", "manda ver", "bora", "vai", "vamos", "faz", "confirmo",
    "confirma", "confirmar", "confirmado", "aham", "uhum", "aha",
    "ta", "ta bom", "ta certo", "tudo certo", "yes", "y", "yep", "ya",
    "quero", "sim quero", "afirmativo", "com certeza", "sem duvida",
}

_NEGATIVOS = {
    "nao", "n", "no", "nops", "nem", "nada", "negativo", "errado",
    "nao quero", "nao e isso", "nao era isso", "nao foi isso",
    "cancela", "cancelar", "cancele", "esquece", "esquecer", "deixa",
    "deixa pra la", "deixa quieto", "para", "pare", "pode parar",
    "de jeito nenhum", "jamais", "nunca", "errou", "ta errado",
    "pular", "skip", "depois",
}

# Emojis tratados à parte: o strip de pontuação abaixo remove qualquer
# caractere não alfanumérico, então um "👍" sozinho viraria string vazia e
# cairia em ambíguo. Num chat de WhatsApp o polegar é uma confirmação
# corriqueira — ignorá-lo seria justamente o tipo de atrito que este módulo
# existe pra remover.
_EMOJI_AFIRMATIVO = {"👍", "👌", "✅", "☑️", "✔️", "🆗", "🙌", "💪", "😀", "😁"}
_EMOJI_NEGATIVO = {"👎", "❌", "🚫", "❎", "🙅", "😕", "😬"}


def _normalizar(texto: str) -> str:
    """minúsculas, sem acento, sem pontuação, espaços colapsados."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFD", texto.strip().lower())
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    sem_pontuacao = re.sub(r"[^\w\s]", " ", sem_acento)
    return re.sub(r"\s+", " ", sem_pontuacao).strip()


def _bate(texto: str, conjunto: set[str], emojis: set[str]) -> bool:
    bruto = (texto or "").strip()
    if bruto in emojis:
        return True
    # Emoji + texto ("👍 pode") — se algum emoji do conjunto aparece, já conta.
    if any(e in bruto for e in emojis):
        return True

    norm = _normalizar(texto)
    if not norm:
        return False
    if norm in conjunto:
        return True

    # Primeira palavra ("sim pode registrar" -> "sim"). Restrito à PRIMEIRA
    # palavra de propósito: "sim" no meio da frase costuma ser outra coisa
    # ("assim que der", "sim, mas não agora" já é ambíguo o bastante pra
    # merecer uma pergunta a mais em vez de uma ação errada).
    return norm.split()[0] in conjunto


def eh_afirmativo(texto: str) -> bool:
    return _bate(texto, _AFIRMATIVOS, _EMOJI_AFIRMATIVO)


def eh_negativo(texto: str) -> bool:
    return _bate(texto, _NEGATIVOS, _EMOJI_NEGATIVO)
