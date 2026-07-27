"""
tests/test_respostas.py — utils/respostas.py (24/07/2026).

Pedido do Lucas: "faça de forma que a utilização do usuário seja fluida".
Antes, confirmação só aceitava ("sim","s","confirma","confirmar") e
qualquer outra coisa CANCELAVA em silêncio — "ok"/"pode"/"👍" perdiam o
registro.

O teste mais importante deste arquivo é o último bloco: garantir que
palavras PARECIDAS com "sim"/"não" (mas que não são confirmação) caiam em
ambíguo, não em falso positivo. Um falso positivo aqui executa uma ação que
a pessoa não pediu — é o erro caro; ambíguo só custa uma pergunta a mais.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from utils.respostas import eh_afirmativo, eh_negativo


# ---------------------------------------------------------------------------
# Afirmativos
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("texto", [
    "sim", "Sim", "SIM", "sim!", "  sim  ", "s", "ss", "simm",
    "ok", "OK", "ok!", "okay", "blz", "beleza", "claro",
    "isso", "isso mesmo", "isso aí", "exato", "exatamente",
    "pode", "pode sim", "pode registrar", "pode ser",
    "manda", "manda ver", "bora", "vai", "confirma", "confirmar",
    "aham", "uhum", "tá", "ta bom", "certo", "correto", "perfeito",
    "yes", "y", "quero", "com certeza",
    "sim, pode registrar", "sim pode mandar",
])
def test_afirmativos_reconhecidos(texto):
    assert eh_afirmativo(texto) is True, texto


@pytest.mark.parametrize("texto", ["👍", "👌", "✅", "👍 pode", "ok 👍"])
def test_emoji_afirmativo(texto):
    assert eh_afirmativo(texto) is True, texto


# ---------------------------------------------------------------------------
# Negativos
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("texto", [
    "não", "nao", "NÃO", "não!", "n", "no", "nops", "nem", "nada",
    "não quero", "nao quero", "não é isso", "nao era isso",
    "cancela", "cancelar", "esquece", "deixa", "deixa pra lá",
    "para", "pare", "negativo", "errado", "errou", "de jeito nenhum",
    "pular", "skip", "depois",
    "não, cancela isso",
])
def test_negativos_reconhecidos(texto):
    assert eh_negativo(texto) is True, texto


@pytest.mark.parametrize("texto", ["👎", "❌", "🚫"])
def test_emoji_negativo(texto):
    assert eh_negativo(texto) is True, texto


# ---------------------------------------------------------------------------
# Ambíguos — NEM afirmativo NEM negativo. Este é o bloco que protege contra
# o erro caro (executar uma ação que a pessoa não confirmou).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("texto", [
    "",
    "   ",
    "assim que der",           # contém "sim" como substring — não pode casar
    "sem problema",            # "sem" é próximo de "sim" por similaridade
    "sinto muito",
    "acho que sim, mas espera",  # começa com "acho" — ambíguo de propósito
    "talvez",
    "não sei",                 # começa com "nao" -> ver teste dedicado abaixo
    "50 mercado cartão",       # pessoa mandou outro gasto em vez de responder
    "saldo",                   # trocou de assunto
    "quanto ficou?",
    "?",
    "kkkk",
])
def test_ambiguos_nao_sao_afirmativos(texto):
    assert eh_afirmativo(texto) is False, texto


@pytest.mark.parametrize("texto", [
    "",
    "assim que der",
    "sim",
    "ok",
    "50 mercado cartão",
    "saldo",
    "kkkk",
])
def test_ambiguos_e_afirmativos_nao_sao_negativos(texto):
    assert eh_negativo(texto) is False, texto


def test_nao_sei_conta_como_negativo_por_prefixo():
    """Caso de fronteira assumido conscientemente: "não sei" começa com
    "não", então cai em negativo (cancela). É o lado seguro do trade-off —
    cancelar e deixar a pessoa repetir é mais barato que registrar/executar
    algo sobre o qual ela acabou de dizer que não tem certeza."""
    assert eh_negativo("não sei") is True
    assert eh_afirmativo("não sei") is False


def test_nenhuma_palavra_e_afirmativa_e_negativa_ao_mesmo_tempo():
    """Invariante: os dois conjuntos não podem se sobrepor, senão a ordem
    de checagem em handler.py decidiria silenciosamente o comportamento."""
    from utils.respostas import _AFIRMATIVOS, _NEGATIVOS
    assert _AFIRMATIVOS & _NEGATIVOS == set()
