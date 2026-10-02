"""
tests/test_verificacao_gasto.py — verificação por IA de todo gasto antes de
gravar (02/10/2026, pedido do Lucas). Bug que motivou: "credito mercado
30/09 feira 12" registrou R$30 — o regex leu o dia da data como valor.

IA nunca é chamada de verdade aqui: `extrair_gasto` (services.ai_fallback) e
`verificar_gasto` (handler) são substituídos por monkeypatch.
"""

import sys
import os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import handler
import services.ai_fallback as ai_fallback
from services.ai_fallback import verificar_gasto


_HOJE = date(2026, 10, 2)
_CATS = [{"id": 1, "nome": "Mercado"}, {"id": 2, "nome": "Farmácia"}]
_FORMAS = [{"id": 7, "nome": "CRÉDITO", "dia_fechamento": 28}]


# ---------------------------------------------------------------------------
# verificar_gasto
# ---------------------------------------------------------------------------

def _ia_responde(monkeypatch, resposta):
    monkeypatch.setattr(ai_fallback, "extrair_gasto", lambda *a, **k: resposta)


def test_concorda_quando_valor_e_data_batem(monkeypatch):
    _ia_responde(monkeypatch, {"eh_gasto": True, "valor": 12, "data": "2026-09-30",
                               "categoria_sugerida": "Mercado", "forma_sugerida": "CRÉDITO"})
    r = verificar_gasto("credito mercado 30/09 feira 12", _CATS, _FORMAS, 12.0, date(2026, 9, 30), hoje=_HOJE)
    assert r["eh_gasto"] and r["concorda"]
    assert r["categoria"]["id"] == 1 and r["forma"]["id"] == 7


def test_discorda_do_valor_lido_da_data(monkeypatch):
    # O cenário do bug: regex leu 30, IA leu 12.
    _ia_responde(monkeypatch, {"eh_gasto": True, "valor": 12, "data": "2026-09-30"})
    r = verificar_gasto("credito mercado 30/09 feira 12", _CATS, _FORMAS, 30.0, None, hoje=_HOJE)
    assert not r["concorda"]
    assert r["valor"] == 12.0 and r["data"] == date(2026, 9, 30)


def test_data_nula_da_ia_equivale_a_hoje(monkeypatch):
    _ia_responde(monkeypatch, {"eh_gasto": True, "valor": 50, "data": None})
    r = verificar_gasto("50 mercado credito", _CATS, _FORMAS, 50.0, None, hoje=_HOJE)
    assert r["concorda"]
    r = verificar_gasto("50 mercado credito", _CATS, _FORMAS, 50.0, _HOJE, hoje=_HOJE)
    assert r["concorda"]


def test_decimal_com_tolerancia(monkeypatch):
    _ia_responde(monkeypatch, {"eh_gasto": True, "valor": "7.90", "data": None})
    assert verificar_gasto("feira 7,90", _CATS, _FORMAS, 7.9, None, hoje=_HOJE)["concorda"]


def test_falha_da_ia_devolve_none(monkeypatch):
    def explode(*a, **k):
        raise TimeoutError("openai fora")
    monkeypatch.setattr(ai_fallback, "extrair_gasto", explode)
    assert verificar_gasto("50 mercado", _CATS, _FORMAS, 50.0, None, hoje=_HOJE) is None


def test_lixo_da_ia_vira_discordancia_nao_excecao(monkeypatch):
    _ia_responde(monkeypatch, {"eh_gasto": True, "valor": "doze", "data": "30/09"})
    r = verificar_gasto("x 12", _CATS, _FORMAS, 12.0, None, hoje=_HOJE)
    assert r["valor"] is None and r["data"] is None and not r["concorda"]


# ---------------------------------------------------------------------------
# handler._processar_input_livre
# ---------------------------------------------------------------------------

def _handler_base(monkeypatch, verificacao):
    estado = {"registrado": None, "sessao": None}
    monkeypatch.setattr(handler, "get_categorias", lambda uid: _CATS)
    monkeypatch.setattr(handler, "get_formas_pagamento", lambda uid: _FORMAS)
    monkeypatch.setattr(handler, "parece_comando_natural", lambda m: False)
    monkeypatch.setattr(handler, "verificar_gasto", lambda *a, **k: verificacao)
    monkeypatch.setattr(
        handler, "_registrar_e_confirmar",
        lambda uid, forma, cat, valor, desc, deduzido_por_ia=False, data=None:
            estado.__setitem__("registrado", (valor, data, desc)) or "ok",
    )
    monkeypatch.setattr(handler, "criar_sessao", lambda uid, **kw: estado.__setitem__("sessao", kw))
    return estado


def test_ia_concorda_registra_direto(monkeypatch):
    estado = _handler_base(monkeypatch, {"eh_gasto": True, "concorda": True, "valor": 12.0,
                                         "data": date(2026, 9, 30), "categoria": None, "forma": None})
    assert handler._processar_input_livre(1, "credito mercado 30/09 feira 12") == "ok"
    valor, data, desc = estado["registrado"]
    assert valor == 12.0 and data.month == 9 and data.day == 30
    assert "30/09" not in desc


def test_ia_discorda_pede_confirmacao_e_nao_grava(monkeypatch):
    estado = _handler_base(monkeypatch, {"eh_gasto": True, "concorda": False, "valor": 12.0,
                                         "data": date(2026, 9, 30), "categoria": None, "forma": None})
    resp = handler._processar_input_livre(1, "mercado credito feira 30 12")
    assert estado["registrado"] is None
    assert estado["sessao"]["etapa"] == "aguardando_confirmacao_ia"
    assert estado["sessao"]["valor_temp"] == 12.0
    assert estado["sessao"]["dados_temp"]["data"] == "2026-09-30"
    assert "R$ 12,00" in resp and "30/09/2026" in resp


def test_ia_acha_que_nao_e_gasto_pede_confirmacao(monkeypatch):
    estado = _handler_base(monkeypatch, {"eh_gasto": False, "concorda": False, "valor": None,
                                         "data": None, "categoria": None, "forma": None})
    handler._processar_input_livre(1, "50 mercado credito")
    assert estado["registrado"] is None
    assert estado["sessao"]["valor_temp"] == 50.0


def test_ia_fora_do_ar_segue_com_regex(monkeypatch):
    estado = _handler_base(monkeypatch, None)
    handler._processar_input_livre(1, "50 mercado credito")
    assert estado["registrado"][0] == 50.0


def test_confirmacao_sim_grava_com_a_data_da_ia(monkeypatch):
    estado = _handler_base(monkeypatch, None)
    monkeypatch.setattr(handler, "deletar_sessao", lambda uid: None)
    monkeypatch.setattr(handler, "get_dados_temp", lambda s: s["dados_temp"])
    sessao = {"valor_temp": 12.0, "categoria_temp": 1, "forma_temp": 7,
              "dados_temp": {"descricao": "feira", "parcelas": None, "data": "2026-09-30"}}
    handler._processar_confirmacao_ia(1, sessao, "sim")
    assert estado["registrado"] == (12.0, date(2026, 9, 30), "feira")
