"""
tests/test_correcao.py — correção de algo pendente (24/07/2026).

Print do Lucas: com "Vou executar: `forma add teste 2999`. Confirma?" em
aberto, ele respondeu "falei errado, o nome correto é teste123" e o bot
ficou MUDO. O silêncio implementado logo antes tratou a correção como
ruído.

A distinção que faltava: "kkkk" não quer nada; "falei errado, o nome é X"
quer muito — só que a frase sozinha não significa nada, é um delta sobre o
que está pendente. Por isso a correção de COMANDO vai pra IA com o comando
pendente junto, em vez de passar pelo classificador de frase isolada.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from parser import parece_correcao
import services.ai_fallback as ai_fallback
import handler


# ---------------------------------------------------------------------------
# Filtro barato: separa correção de ruído sem gastar LLM
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("texto", [
    "falei errado, o nome correto é teste123",   # a frase exata do print
    "errei, é 3000",
    "na verdade o nome é teste123",
    "me enganei, era pix",
    "quis dizer 60",
    "o certo é teste123",
    "corrige o nome pra teste123",
    "desconsidera, é outro valor",
    "não era isso",
    "desculpa, seria 500",
    "foi mal, troca por 200",
])
def test_reconhece_correcao(texto):
    assert parece_correcao(texto) is True, texto


@pytest.mark.parametrize("texto", [
    "", "   ", "kkkk", "hmm", "tá", "oi", "bom dia",
    "quanto ficou?", "?", "aff", "vou ver depois",
    "50 mercado cartão",   # gasto normal não é correção
    "saldo",
])
def test_ruido_nao_e_correcao(texto):
    assert parece_correcao(texto) is False, texto


# ---------------------------------------------------------------------------
# interpretar_correcao_comando — mesma trava anti-alucinação do comando
# original (_comando_valido). Não existe caminho que execute um comando não
# validado só por ter vindo de uma correção.
# ---------------------------------------------------------------------------

def test_correcao_valida_e_aplicada(monkeypatch):
    monkeypatch.setattr(
        ai_fallback, "corrigir_comando",
        lambda pendente, msg: {
            "comando_sugerido": "forma add teste123 2999",
            "descricao_acao": "Criar a forma teste123 com limite de R$ 2.999,00",
        },
    )

    resultado = ai_fallback.interpretar_correcao_comando(
        "forma add teste 2999", "falei errado, o nome correto é teste123"
    )

    assert resultado["comando_sugerido"] == "forma add teste123 2999"
    assert "teste123" in resultado["descricao_acao"]


def test_correcao_fora_do_vocabulario_e_descartada(monkeypatch):
    """Alucinação: IA devolveu algo que não é comando do bot."""
    monkeypatch.setattr(
        ai_fallback, "corrigir_comando",
        lambda pendente, msg: {"comando_sugerido": "apaga o banco de dados"},
    )

    assert ai_fallback.interpretar_correcao_comando("forma add teste 2999", "muda") is None


def test_correcao_nao_aplicavel_devolve_none(monkeypatch):
    """IA olhou e disse que a mensagem não corrige este comando."""
    monkeypatch.setattr(
        ai_fallback, "corrigir_comando",
        lambda pendente, msg: {"comando_sugerido": None},
    )

    assert ai_fallback.interpretar_correcao_comando("forma add teste 2999", "sei la") is None


def test_falha_da_ia_devolve_none(monkeypatch):
    def _explode(pendente, msg):
        raise RuntimeError("timeout")

    monkeypatch.setattr(ai_fallback, "corrigir_comando", _explode)

    assert ai_fallback.interpretar_correcao_comando("forma add teste 2999", "errei") is None


# ---------------------------------------------------------------------------
# Ligação no handler — o cenário completo do print
# ---------------------------------------------------------------------------

_SESSAO_COMANDO = {
    "etapa": "aguardando_confirmacao_comando",
    "dados_temp": {"comando_sugerido": "forma add teste 2999"},
}


@pytest.fixture
def handler_mockado(monkeypatch):
    estado = {"deletada": False, "criada": None}
    monkeypatch.setattr(handler, "deletar_sessao", lambda uid: estado.__setitem__("deletada", True))
    monkeypatch.setattr(
        handler, "criar_sessao",
        lambda uid, **k: estado.__setitem__("criada", k.get("dados_temp")),
    )
    monkeypatch.setattr(handler, "get_dados_temp", lambda s: s.get("dados_temp") or {})
    return estado


def test_correcao_durante_confirmacao_repropoe_comando(monkeypatch, handler_mockado):
    """O caso do print: preserva o limite 2999, troca só o nome, e volta a
    pedir confirmação (a pessoa pode corrigir de novo se quiser)."""
    recebido = {}

    def _fake_corrigir(pendente, msg):
        recebido["pendente"] = pendente
        recebido["msg"] = msg
        return {
            "comando_sugerido": "forma add teste123 2999",
            "descricao_acao": "Criar a forma teste123 com limite de R$ 2.999,00",
        }

    monkeypatch.setattr(ai_fallback, "corrigir_comando", _fake_corrigir)

    resposta = handler._processar_confirmacao_comando(
        1, _SESSAO_COMANDO, "falei errado, o nome correto é teste123"
    )

    # A IA recebeu o comando PENDENTE junto — sem isso a frase não teria
    # como ser interpretada.
    assert recebido["pendente"] == "forma add teste 2999"
    assert "forma add teste123 2999" in resposta
    assert "2999" in resposta          # limite preservado
    assert "confirma" in resposta.lower()
    # Nova sessão de confirmação criada com o comando corrigido
    assert handler_mockado["criada"] == {"comando_sugerido": "forma add teste123 2999"}


def test_ruido_durante_confirmacao_continua_em_silencio(monkeypatch, handler_mockado):
    """A correção não pode ter reaberto a porta pro ruído virar chamada de
    LLM — "kkkk" não bate em parece_correcao, então nem chega na IA."""
    chamou = {"ia": False}

    def _nao_deve_chamar(pendente, msg):
        chamou["ia"] = True
        return {}

    monkeypatch.setattr(ai_fallback, "corrigir_comando", _nao_deve_chamar)

    resposta = handler._processar_confirmacao_comando(1, _SESSAO_COMANDO, "kkkk")

    assert resposta == ""
    assert chamou["ia"] is False
    assert handler_mockado["deletada"] is False   # sessão preservada


def test_ia_nao_consegue_corrigir_cai_no_fluxo_normal(monkeypatch, handler_mockado):
    """IA devolveu None: não pode travar nem executar palpite — segue o
    caminho de "resposta fora do esperado"."""
    monkeypatch.setattr(ai_fallback, "corrigir_comando", lambda p, m: {"comando_sugerido": None})
    monkeypatch.setattr(handler, "_despachar_comando", lambda uid, m: None)
    monkeypatch.setattr(handler, "_processar_input_livre", lambda uid, m: "🤔 Não entendi essa.")

    resposta = handler._processar_confirmacao_comando(
        1, _SESSAO_COMANDO, "na verdade sei lá o que eu quero"
    )

    assert resposta == "🤔 Não entendi essa."
    assert handler_mockado["deletada"] is True


def test_sim_continua_executando_o_pendente(monkeypatch, handler_mockado):
    """Regressão: a correção não pode ter atrapalhado o caminho feliz."""
    executados = []
    monkeypatch.setattr(
        handler, "_despachar_comando",
        lambda uid, cmd: executados.append(cmd) or "✅ Forma teste adicionada!",
    )

    resposta = handler._processar_confirmacao_comando(1, _SESSAO_COMANDO, "sim")

    assert executados == ["forma add teste 2999"]
    assert resposta == "✅ Forma teste adicionada!"
