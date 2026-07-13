"""
tests/test_despesas_fixas.py — Fase 3.3 do PLANO_EXECUCAO.md.

Cobre só a parte pura, sem banco: `_dia_efetivo`, que capa o dia de
lançamento no último dia do mês (o ponto mais fácil de errar aqui — uma
despesa fixa com dia_lancamento=31 não pode simplesmente nunca lançar em
fevereiro).

A idempotência de verdade (`lancar_despesas_fixas_do_mes` não duplicar gasto
se rodado 2x no mesmo dia) depende do índice único `uq_despesa_fixa_mes` no
banco — não é testável sem Postgres real. Verificação: rodar
`python -m jobs.lancar_fixas` duas vezes seguidas manualmente contra um banco
de teste e conferir que a 2ª chamada não insere nada.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.despesas_fixas import _dia_efetivo


def test_dia_efetivo_dentro_do_mes_fica_igual():
    assert _dia_efetivo(5, 2026, 7) == 5


def test_dia_efetivo_31_em_mes_de_30_dias():
    # Abril tem 30 dias.
    assert _dia_efetivo(31, 2026, 4) == 30


def test_dia_efetivo_31_em_fevereiro_nao_bissexto():
    assert _dia_efetivo(31, 2026, 2) == 28


def test_dia_efetivo_31_em_fevereiro_bissexto():
    assert _dia_efetivo(31, 2028, 2) == 29


def test_dia_efetivo_31_em_mes_de_31_dias_fica_igual():
    assert _dia_efetivo(31, 2026, 7) == 31


def test_dia_efetivo_dia_1_sempre_valido():
    assert _dia_efetivo(1, 2026, 2) == 1
