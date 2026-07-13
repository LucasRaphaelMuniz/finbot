"""
Testes de tests/test_parser.py — Fase 1 do PLANO_EXECUCAO.md.

Cobrem o bug original (`_VALOR_RE` capturando '1.10' de '1.103,04') e a
normalização BR adotada em D1 (`_normalizar_numero_br`).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser import extrair_valor


def test_valor_com_milhar_e_decimal():
    # Bug original: virava 1.10 (R$ 1,10). Correto: 1103.04.
    assert extrair_valor("1.103,04") == 1103.04


def test_valor_inteiro_simples():
    assert extrair_valor("50") == 50.0


def test_valor_com_decimal_virgula():
    assert extrair_valor("50,90") == 50.9


def test_valor_com_prefixo_moeda_e_milhar():
    assert extrair_valor("R$ 1.234,56") == 1234.56


def test_valor_so_ponto_duas_casas_decimal_por_d1():
    # Caminho valor-da-IA -> texto -> parser: '1103.04' (str de float).
    assert extrair_valor("1103.04") == 1103.04


def test_valor_so_ponto_tres_digitos_e_milhar():
    assert extrair_valor("1.103") == 1103.0


def test_valor_so_ponto_um_digito_e_milhar_nao_decimal():
    # Caso que motivou o fix em app.py: '50.0' (str de 50.0) não deve virar 5.0.
    assert extrair_valor("50.0") == 500.0


def test_valor_muitos_digitos_sem_pontuacao():
    assert extrair_valor("1234567") == 1234567.0


def test_valor_milhar_multiplo_grupo():
    assert extrair_valor("1.234.567,89") == 1234567.89


def test_valor_em_frase():
    assert extrair_valor("gastei 1.103,04 no mercado") == 1103.04


def test_palavra_numerica_simples():
    assert extrair_valor("cem") == 100.0


def test_palavra_numerica_composta():
    assert extrair_valor("cento e cinquenta") == 150.0


def test_palavra_numerica_mil():
    assert extrair_valor("mil e duzentos") == 1200.0


def test_valor_nao_encontrado():
    assert extrair_valor("não tem número nenhum aqui") is None
