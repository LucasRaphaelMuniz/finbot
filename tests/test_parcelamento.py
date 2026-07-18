"""
tests/test_parcelamento.py — Fase 3.2 do PLANO_EXECUCAO.md.

Cobre só as partes puras, sem banco: detecção de parcelas no texto
(parser.extrair_parcelas), cálculo de competência (services/competencia.py)
e divisão de parcelas (services/parcelamento.dividir_parcelas).

`criar_compra_parcelada` e `excluir_compra_parcelada` dependem de banco
(get_conn) e não são cobertos aqui — verificação é manual, via bot.
"""

import sys
import os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser import extrair_parcelas
from services.competencia import calcular_competencia, mes_vencimento, somar_meses
from services.parcelamento import dividir_parcelas, formatar_competencia


# ---------------------------------------------------------------------------
# extrair_parcelas
# ---------------------------------------------------------------------------

def test_extrair_parcelas_formato_12x():
    assert extrair_parcelas("notebook 1103,04 em 12x no cartão") == 12


def test_extrair_parcelas_formato_x_colado():
    assert extrair_parcelas("1103,04 12x cartão") == 12


def test_extrair_parcelas_formato_em_vezes():
    assert extrair_parcelas("comprei em 6 vezes no cartão") == 6


def test_extrair_parcelas_formato_parcelado_em():
    assert extrair_parcelas("parcelado em 3 no cartão") == 3


def test_extrair_parcelas_ausente():
    assert extrair_parcelas("50 mercado cartão") is None


def test_extrair_parcelas_1x_nao_e_parcelamento():
    assert extrair_parcelas("50 mercado 1x no cartão") is None


# ---------------------------------------------------------------------------
# calcular_competencia — competência = MÊS DA FATURA (regra original da
# Fase 3.2, restaurada pela migração 022; ver nota em services/competencia.py:
# o experimento de competência = mês do vencimento foi revertido em
# 17-18/07/2026 porque tirava a compra de hoje das telas do mês corrente).
# ---------------------------------------------------------------------------

def test_competencia_sem_dia_fechamento_e_mes_da_data():
    assert calcular_competencia(date(2026, 7, 15), None) == date(2026, 7, 1)


def test_competencia_antes_do_fechamento_fica_no_mes_atual():
    # dia_fechamento=25, compra dia 20 -> ainda dentro da fatura de julho
    assert calcular_competencia(date(2026, 7, 20), 25) == date(2026, 7, 1)


def test_competencia_depois_do_fechamento_vai_pro_mes_seguinte():
    # dia_fechamento=25, compra dia 28 -> fatura de julho já fechou
    assert calcular_competencia(date(2026, 7, 28), 25) == date(2026, 8, 1)


def test_competencia_no_dia_exato_do_fechamento_fica_no_mes_atual():
    assert calcular_competencia(date(2026, 7, 25), 25) == date(2026, 7, 1)


def test_competencia_depois_do_fechamento_em_dezembro_vira_janeiro():
    assert calcular_competencia(date(2026, 12, 28), 25) == date(2027, 1, 1)


# ---------------------------------------------------------------------------
# mes_vencimento — em qual mês a fatura de uma competência PESA NO CAIXA
# (migração 019 + modelo "fatura como conta a pagar"). Nunca altera
# gastos.competencia — só é usada por services/resumo.py (provisão de
# caixa) e services/faturas.py (limite rotativo).
# ---------------------------------------------------------------------------

def test_mes_vencimento_sem_cartao_e_o_proprio_mes():
    # pix/débito/Custo Fixo: sai do caixa no mês em que aconteceu
    assert mes_vencimento(date(2026, 7, 1), None, None) == date(2026, 7, 1)


def test_mes_vencimento_fallback_sem_dia_vencimento_e_mes_seguinte():
    # fecha ~25, sem vencimento informado -> assume mês seguinte (caso comum)
    assert mes_vencimento(date(2026, 7, 1), 25, None) == date(2026, 8, 1)


def test_mes_vencimento_vencimento_depois_do_fechamento_mesmo_mes():
    # fecha dia 5, vence dia 12 -> mesma competência
    assert mes_vencimento(date(2026, 7, 1), 5, 12) == date(2026, 7, 1)


def test_mes_vencimento_vencimento_antes_do_fechamento_mes_seguinte():
    # fecha dia 25, vence dia 5 -> mês seguinte
    assert mes_vencimento(date(2026, 7, 1), 25, 5) == date(2026, 8, 1)


def test_mes_vencimento_vira_o_ano():
    assert mes_vencimento(date(2026, 12, 1), 25, 5) == date(2027, 1, 1)


# ---------------------------------------------------------------------------
# somar_meses
# ---------------------------------------------------------------------------

def test_somar_meses_dentro_do_ano():
    assert somar_meses(date(2026, 7, 1), 3) == date(2026, 10, 1)


def test_somar_meses_vira_o_ano():
    assert somar_meses(date(2026, 11, 1), 3) == date(2027, 2, 1)


def test_somar_zero_meses_e_a_mesma_competencia():
    assert somar_meses(date(2026, 7, 1), 0) == date(2026, 7, 1)


def test_somar_meses_negativo_volta_um_mes():
    # usado por services/faturas.py pra achar a fatura fechada (aberta - 1)
    assert somar_meses(date(2026, 7, 1), -1) == date(2026, 6, 1)


def test_somar_meses_negativo_vira_o_ano_pra_tras():
    assert somar_meses(date(2026, 1, 1), -1) == date(2025, 12, 1)


# ---------------------------------------------------------------------------
# dividir_parcelas
# ---------------------------------------------------------------------------

def test_dividir_parcelas_divisao_exata():
    # Exemplo do PLANO_EXECUCAO.md: 1103.04 / 12 = 91.92 exatas.
    valores = dividir_parcelas(1103.04, 12)
    assert len(valores) == 12
    assert all(v == 91.92 for v in valores)
    assert round(sum(valores), 2) == 1103.04


def test_dividir_parcelas_com_residuo_na_primeira():
    valores = dividir_parcelas(100.0, 3)
    assert len(valores) == 3
    assert valores[0] == 33.34
    assert valores[1] == valores[2] == 33.33
    assert round(sum(valores), 2) == 100.00


def test_dividir_parcelas_soma_sempre_bate_com_total():
    for total, n in [(999.99, 7), (10.0, 3), (0.03, 3), (50000.0, 24)]:
        valores = dividir_parcelas(total, n)
        assert round(sum(valores), 2) == round(total, 2)


# ---------------------------------------------------------------------------
# formatar_competencia
# ---------------------------------------------------------------------------

def test_formatar_competencia():
    assert formatar_competencia(date(2026, 8, 1)) == "Agosto/2026"
