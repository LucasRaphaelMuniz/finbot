"""
tests/test_resumo.py — Fase 4.3 do PLANO_EXECUCAO.md (GET /api/resumo).

Cobre só `montar_comparativo`, a única parte de services/resumo.py sem
banco — junta os dicts mês->total de gastos e entradas num array ordenado
pro gráfico comparativo do dashboard (§5.2 do plano). O resto de
resumo_mensal depende de SQL/conexão real e é verificado manualmente
(mesma filosofia dos outros services: lógica pura tem teste automatizado,
query com banco não).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.resumo import montar_comparativo


def test_meses_iguais_nos_dois_lados():
    gastos = {"2026-05": 100.0, "2026-06": 200.0}
    entradas = {"2026-05": 300.0, "2026-06": 400.0}
    resultado = montar_comparativo(gastos, entradas)
    assert resultado == [
        {"mes": "2026-05", "gastos": 100.0, "entradas": 300.0},
        {"mes": "2026-06", "gastos": 200.0, "entradas": 400.0},
    ]


def test_mes_so_com_gasto_preenche_entrada_com_zero():
    gastos = {"2026-06": 150.0}
    entradas = {}
    resultado = montar_comparativo(gastos, entradas)
    assert resultado == [{"mes": "2026-06", "gastos": 150.0, "entradas": 0.0}]


def test_mes_so_com_entrada_preenche_gasto_com_zero():
    gastos = {}
    entradas = {"2026-07": 500.0}
    resultado = montar_comparativo(gastos, entradas)
    assert resultado == [{"mes": "2026-07", "gastos": 0.0, "entradas": 500.0}]


def test_meses_ficam_em_ordem_cronologica():
    gastos = {"2026-07": 10.0, "2026-05": 20.0, "2026-06": 30.0}
    entradas = {}
    resultado = montar_comparativo(gastos, entradas)
    assert [item["mes"] for item in resultado] == ["2026-05", "2026-06", "2026-07"]


def test_sem_lancamentos_retorna_lista_vazia():
    assert montar_comparativo({}, {}) == []
