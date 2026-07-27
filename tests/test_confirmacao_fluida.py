"""
tests/test_confirmacao_fluida.py — três estados na confirmação (24/07/2026).

Pedido do Lucas: "faça de forma que a utilização do usuário seja fluida".

O comportamento antigo era binário: afirmativo exato executa, TODO o resto
cancela. Este arquivo trava o comportamento novo — afirmativo executa,
negativo cancela, e ambíguo PRESERVA a sessão perguntando de novo (o caso
que antes fazia a pessoa perder o registro por responder "ok").

Banco e sessão são mockados; o que está sob teste é só a árvore de decisão
de handler.py, não persistência.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import handler


@pytest.fixture
def sessao_mock(monkeypatch):
    """Captura se deletar_sessao foi chamada — é o sinal observável de
    'a sessão foi encerrada' (executou ou cancelou) vs 'foi preservada'
    (perguntou de novo)."""
    estado = {"deletada": False}
    monkeypatch.setattr(handler, "deletar_sessao", lambda uid: estado.__setitem__("deletada", True))
    return estado


# ---------------------------------------------------------------------------
# Confirmação de COMANDO (grupo add, forma add, ...) — a de maior risco:
# altera grupo/membros/formas, e desfazer é caro.
# ---------------------------------------------------------------------------

_SESSAO_COMANDO = {
    "etapa": "aguardando_confirmacao_comando",
    "dados_temp": {"comando_sugerido": "grupo add 44912345678"},
}


def test_comando_afirmativo_executa(monkeypatch, sessao_mock):
    executados = []
    monkeypatch.setattr(
        handler, "_despachar_comando",
        lambda uid, cmd: executados.append(cmd) or "✅ adicionado!",
    )
    monkeypatch.setattr(handler, "get_dados_temp", lambda s: s["dados_temp"])

    resposta = handler._processar_confirmacao_comando(1, _SESSAO_COMANDO, "pode")

    assert executados == ["grupo add 44912345678"]
    assert resposta == "✅ adicionado!"
    assert sessao_mock["deletada"] is True


def test_comando_negativo_cancela_sem_executar(monkeypatch, sessao_mock):
    executados = []
    monkeypatch.setattr(
        handler, "_despachar_comando",
        lambda uid, cmd: executados.append(cmd) or "não deveria executar",
    )
    monkeypatch.setattr(handler, "get_dados_temp", lambda s: s["dados_temp"])

    resposta = handler._processar_confirmacao_comando(1, _SESSAO_COMANDO, "não")

    assert executados == []
    assert "nada foi executado" in resposta.lower()
    assert sessao_mock["deletada"] is True


def test_comando_ambiguo_preserva_sessao_e_repergunta(monkeypatch, sessao_mock):
    """O caso que motivou a mudança: resposta que não é nem sim nem não
    NÃO pode destruir a sessão — senão a pessoa teria que reescrever a
    frase inteira em linguagem natural e torcer pra IA interpretar igual."""
    executados = []
    monkeypatch.setattr(
        handler, "_despachar_comando",
        lambda uid, cmd: executados.append(cmd) or "não deveria executar",
    )
    monkeypatch.setattr(handler, "get_dados_temp", lambda s: s["dados_temp"])

    resposta = handler._processar_confirmacao_comando(1, _SESSAO_COMANDO, "e aí, quanto ficou?")

    assert executados == []
    assert sessao_mock["deletada"] is False  # sessão VIVA
    assert "sim" in resposta.lower() and "não" in resposta.lower()


@pytest.mark.parametrize("resposta_usuario", ["sim", "ok", "pode", "isso", "blz", "👍", "manda"])
def test_comando_aceita_variacoes_de_sim(monkeypatch, sessao_mock, resposta_usuario):
    """Regressão do atrito original: antes só 4 strings exatas executavam."""
    executados = []
    monkeypatch.setattr(
        handler, "_despachar_comando",
        lambda uid, cmd: executados.append(cmd) or "✅ ok",
    )
    monkeypatch.setattr(handler, "get_dados_temp", lambda s: s["dados_temp"])

    handler._processar_confirmacao_comando(1, _SESSAO_COMANDO, resposta_usuario)

    assert executados == ["grupo add 44912345678"], resposta_usuario


def test_comando_invalido_no_despacho_nao_trava_usuario(monkeypatch, sessao_mock):
    """Salvaguarda: prefixo passou na validação de ai_fallback mas a sintaxe
    completa não bate em nada — não pode devolver None pro webhook."""
    monkeypatch.setattr(handler, "_despachar_comando", lambda uid, cmd: None)
    monkeypatch.setattr(handler, "get_dados_temp", lambda s: s["dados_temp"])

    resposta = handler._processar_confirmacao_comando(1, _SESSAO_COMANDO, "sim")

    assert "não consegui executar" in resposta.lower()
    assert sessao_mock["deletada"] is True


# ---------------------------------------------------------------------------
# Confirmação de GASTO deduzido pela IA (valor incerto — por isso confirma)
# ---------------------------------------------------------------------------

_SESSAO_GASTO = {
    "etapa": "aguardando_confirmacao_ia",
    "valor_temp": 50.0,
    "categoria_temp": 1,
    "forma_temp": 10,
    "dados_temp": {"descricao": "remedio", "parcelas": None},
}


def test_gasto_negativo_cancela(monkeypatch, sessao_mock):
    registrados = []
    monkeypatch.setattr(
        handler, "_registrar_e_confirmar",
        lambda *a, **k: registrados.append(a) or "não deveria registrar",
    )
    monkeypatch.setattr(handler, "get_dados_temp", lambda s: s["dados_temp"])

    resposta = handler._processar_confirmacao_ia(1, _SESSAO_GASTO, "nao")

    assert registrados == []
    assert "nada foi registrado" in resposta.lower()
    assert sessao_mock["deletada"] is True


def test_gasto_ambiguo_preserva_sessao(monkeypatch, sessao_mock):
    registrados = []
    monkeypatch.setattr(
        handler, "_registrar_e_confirmar",
        lambda *a, **k: registrados.append(a) or "não deveria registrar",
    )
    monkeypatch.setattr(handler, "get_dados_temp", lambda s: s["dados_temp"])

    resposta = handler._processar_confirmacao_ia(1, _SESSAO_GASTO, "hmm deixa eu ver")

    assert registrados == []
    assert sessao_mock["deletada"] is False
    assert "sim" in resposta.lower()


def test_gasto_afirmativo_registra(monkeypatch, sessao_mock):
    registrados = []
    monkeypatch.setattr(handler, "get_dados_temp", lambda s: s["dados_temp"])
    monkeypatch.setattr(handler, "get_categorias", lambda uid: [{"id": 1, "nome": "Farmácia"}])
    monkeypatch.setattr(handler, "get_formas_pagamento", lambda uid: [{"id": 10, "nome": "Cartão"}])
    monkeypatch.setattr(
        handler, "_registrar_e_confirmar",
        lambda uid, forma, cat, valor, desc, **k: registrados.append((valor, cat["nome"], forma["nome"])) or "✅ ok",
    )

    resposta = handler._processar_confirmacao_ia(1, _SESSAO_GASTO, "isso mesmo")

    assert registrados == [(50.0, "Farmácia", "Cartão")]
    assert resposta == "✅ ok"
    assert sessao_mock["deletada"] is True
