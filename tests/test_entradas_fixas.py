"""
tests/test_entradas_fixas.py — migração 023 (entradas recorrentes).

Mesma filosofia dos outros módulos: só a parte pura (sem banco) tem teste
automatizado — _dia_efetivo. O lançador e a idempotência dependem de
get_conn e do índice único uq_entrada_fixa_mes; verificação manual via
web/bot, como em despesas fixas.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.entradas_fixas import _dia_efetivo


def test_dia_efetivo_normal():
    assert _dia_efetivo(5, 2026, 7) == 5


def test_dia_efetivo_capado_em_fevereiro():
    # dia 31 em fevereiro não existe — lança no último dia (28 em 2026)
    assert _dia_efetivo(31, 2026, 2) == 28


def test_dia_efetivo_capado_em_fevereiro_bissexto():
    assert _dia_efetivo(31, 2028, 2) == 29


def test_dia_efetivo_dia_30_em_mes_de_31():
    assert _dia_efetivo(30, 2026, 7) == 30
