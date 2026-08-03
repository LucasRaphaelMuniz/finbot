"""
tests/test_extrair_data.py — data explícita no fim da mensagem (03/08/2026,
pedido do Lucas): "restaurante 28,78 credito japones almoço de sexta 01-08"
tem que registrar o gasto com data 01/08, não hoje. Aceita dd-mm, dd/mm,
dd.mm (ano corrente) e com ano explícito.

Só olha o ÚLTIMO token de propósito — "Amazon 2/12" (descrição de parcela
digitada à mão, ver print do Lucas em Lançamentos) não pode virar data só
por ter uma barra no meio da frase.
"""

import sys
import os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser import extrair_data


_HOJE = date(2026, 8, 3)


def test_dd_hifen_mm():
    assert extrair_data("... japones almoço de sexta 01-08", hoje=_HOJE) == date(2026, 8, 1)


def test_dd_barra_mm():
    assert extrair_data("... japones almoço de sexta 01/08", hoje=_HOJE) == date(2026, 8, 1)


def test_dd_ponto_mm():
    assert extrair_data("... japones almoço de sexta 01.08", hoje=_HOJE) == date(2026, 8, 1)


def test_com_ano_explicito_4_digitos():
    assert extrair_data("mercado 50 pix 25/12/2025", hoje=_HOJE) == date(2025, 12, 25)


def test_com_ano_explicito_2_digitos():
    assert extrair_data("mercado 50 pix 25-12-25", hoje=_HOJE) == date(2025, 12, 25)


def test_sem_data_no_final_devolve_none():
    assert extrair_data("50 mercado cartão", hoje=_HOJE) is None


def test_data_invalida_dia_devolve_none():
    assert extrair_data("mercado 50 pix 32-08", hoje=_HOJE) is None


def test_data_invalida_mes_devolve_none():
    assert extrair_data("mercado 50 pix 10-13", hoje=_HOJE) is None


def test_data_inexistente_no_calendario_devolve_none():
    assert extrair_data("mercado 50 pix 31-02", hoje=_HOJE) is None


def test_padrao_parcela_no_meio_da_frase_nao_e_data():
    # "Amazon 2/12" como descrição inteira (sem valor/data de verdade) —
    # o token final AQUI é "2/12", que tecnicamente bate no regex (dia
    # 2, mês 12) — comportamento aceito: só quando é mesmo o último token.
    # O que este teste garante é que um "N/M" no MEIO da frase não conta.
    assert extrair_data("Amazon 2/12 comprado ontem", hoje=_HOJE) is None


def test_texto_vazio_devolve_none():
    assert extrair_data("", hoje=_HOJE) is None
