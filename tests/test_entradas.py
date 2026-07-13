"""
tests/test_entradas.py — Fase 3.5 do PLANO_EXECUCAO.md (gap G1).

Cobre só a parte pura, sem banco: `eh_entrada`, a detecção por palavra-chave
que decide se o input livre é uma entrada (não passa pelo fluxo de
categoria/forma) ou um gasto normal.

`services/entradas.py` (registrar_entrada, get_entradas_mes,
get_total_entradas_mes) depende de banco e não é coberto aqui — verificação
é manual, via bot: registrar uma entrada, checar que `resumo` mostra o total
e que `saldo` (por forma de pagamento) não muda.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser import eh_entrada


def test_recebi_e_entrada():
    assert eh_entrada("recebi 2000 de salário") is True


def test_comando_explicito_entrada_e_entrada():
    assert eh_entrada("entrada 2000 salário") is True


def test_caiu_e_entrada():
    assert eh_entrada("caiu 500 aqui hoje") is True


def test_ganhei_e_entrada():
    assert eh_entrada("ganhei um bônus de 300") is True


def test_salario_sem_acento_e_entrada():
    assert eh_entrada("meu salario de 3000 caiu") is True


def test_gasto_normal_nao_e_entrada():
    assert eh_entrada("50 mercado cartão") is False


def test_gasto_com_descricao_comum_nao_e_entrada():
    assert eh_entrada("gastei 120,90 no restaurante no pix") is False
