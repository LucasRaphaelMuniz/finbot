"""
tests/test_mover_fatura.py — aviso de compra perto do fechamento e comandos
*próxima fatura* / *fatura anterior* (02/10/2026, pedido do Lucas: compra de
28/09 num cartão que fecha dia 28 caiu na fatura seguinte no banco — o
fechamento real muda conforme o dia e não dá pra saber a regra do banco).
"""

import sys
import os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import handler


def test_sem_aviso_longe_do_fechamento():
    assert handler._aviso_perto_fechamento(date(2026, 9, 20), 28, date(2026, 9, 1)) is None


def test_sem_aviso_fora_do_cartao():
    assert handler._aviso_perto_fechamento(date(2026, 9, 28), None, date(2026, 9, 1)) is None


def test_aviso_no_dia_do_fechamento_sugere_proxima():
    aviso = handler._aviso_perto_fechamento(date(2026, 9, 28), 28, date(2026, 9, 1))
    assert "próxima fatura" in aviso


def test_aviso_logo_depois_do_fechamento_sugere_anterior():
    aviso = handler._aviso_perto_fechamento(date(2026, 9, 30), 28, date(2026, 10, 1))
    assert "fatura anterior" in aviso


def _mover(monkeypatch, resultado):
    chamadas = []
    monkeypatch.setattr(
        handler, "mover_ultimo_gasto_fatura",
        lambda uid, delta: chamadas.append(delta) or resultado,
    )
    return chamadas


def test_comando_proxima_fatura_com_e_sem_acento(monkeypatch):
    chamadas = _mover(monkeypatch, {"valor": 38.99, "categoria_nome": "Moradia",
                                    "forma_nome": "CRÉDITO", "competencia": date(2026, 10, 1)})
    resp = handler._despachar_comando(1, "Próxima fatura")
    assert "R$ 38,99" in resp and "2026" in resp
    handler._despachar_comando(1, "proxima fatura")
    assert chamadas == [1, 1]


def test_comando_fatura_anterior(monkeypatch):
    chamadas = _mover(monkeypatch, {"valor": 10, "categoria_nome": "Mercado",
                                    "forma_nome": "CRÉDITO", "competencia": date(2026, 9, 1)})
    resp = handler._cmd_mover_fatura(1, -1)
    assert chamadas == [-1] and "✅" in resp


def test_erros_viram_mensagem(monkeypatch):
    for erro in ("sem_gasto", "nao_cartao", "parcela"):
        _mover(monkeypatch, {"erro": erro})
        assert handler._cmd_mover_fatura(1, +1).startswith("❌")


def test_comandos_abandonam_sessao_pendente():
    assert handler._parece_nova_intencao("próxima fatura")
    assert handler._parece_nova_intencao("fatura anterior")
