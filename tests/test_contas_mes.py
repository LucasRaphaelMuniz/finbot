"""
tests/test_contas_mes.py — board "contas do mês" (24/07/2026).

Cobre só a parte pura, sem banco, seguindo a mesma linha dos outros testes
do projeto (test_despesas_fixas.py, test_resumo.py): a montagem das linhas
depende de Postgres e é verificada à mão, mas as duas peças onde um erro
passaria despercebido são puras e ficam travadas aqui:

1. `competencias_que_vencem_em` — o inverso de mes_vencimento. É o que
   coloca a fatura no mês certo do board; errar aqui faz a conta aparecer no
   mês errado, que é exatamente o bug que o board existe pra evitar.
2. `parsear_chave` — a chave vem da URL, então é entrada não confiável.
"""

import sys
import os
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.contas_mes import (
    competencias_que_vencem_em, chave_gasto, chave_fatura, parsear_chave,
    _mes_para_data,
)
from utils.app_error import AppError


# ---------------------------------------------------------------------------
# competencias_que_vencem_em
# ---------------------------------------------------------------------------

def test_cartao_do_lucas_fecha_28_vence_no_mes_seguinte():
    """
    Caso concreto que motivou a tela: cartão que fecha 28/07 e vence dia 10
    de agosto. A fatura de julho (competência 2026-07) é conta de AGOSTO.
    """
    assert competencias_que_vencem_em(date(2026, 8, 1), 28, 10) == [date(2026, 7, 1)]


def test_cartao_do_lucas_nao_aparece_no_proprio_mes_de_fechamento():
    """O board de julho não pode mostrar a fatura que fecha em 28/07 — ela
    ainda não é uma conta a pagar em julho."""
    assert competencias_que_vencem_em(date(2026, 7, 1), 28, 10) == [date(2026, 6, 1)]


def test_cartao_que_fecha_e_vence_no_mesmo_mes():
    """dia_vencimento > dia_fechamento (fecha dia 5, vence dia 12): a fatura
    da própria competência vence no mês dela."""
    assert competencias_que_vencem_em(date(2026, 7, 1), 5, 12) == [date(2026, 7, 1)]


def test_sem_dia_vencimento_cai_no_fallback_mes_seguinte():
    """Fallback documentado em mes_vencimento: sem dia_vencimento, assume o
    padrão brasileiro (fecha num mês, vence no seguinte)."""
    assert competencias_que_vencem_em(date(2026, 8, 1), 25, None) == [date(2026, 7, 1)]


def test_forma_sem_fechamento_nao_gera_linha_de_fatura():
    """Pix/débito/Custo Fixo não têm fatura — saem linha a linha, não como
    uma conta agregada."""
    assert competencias_que_vencem_em(date(2026, 7, 1), None, None) == []


def test_virada_de_ano():
    """Board de janeiro mostra a fatura fechada em dezembro."""
    assert competencias_que_vencem_em(date(2026, 1, 1), 28, 10) == [date(2025, 12, 1)]


def test_toda_competencia_aparece_em_exatamente_um_mes():
    """
    Invariante que importa mais que qualquer caso isolado: uma fatura não
    pode sumir do board (nunca cobrada) nem aparecer em dois meses (cobrada
    duas vezes). Varre um ano inteiro pra várias configurações de cartão.
    """
    for dia_fechamento in (1, 5, 15, 25, 28, 31):
        for dia_vencimento in (None, 1, 10, 20, 28, 31):
            vistas = []
            for mes in range(1, 13):
                vistas += competencias_que_vencem_em(
                    date(2026, mes, 1), dia_fechamento, dia_vencimento
                )
            # 12 meses de board => 12 competências distintas cobradas.
            assert len(vistas) == 12, (dia_fechamento, dia_vencimento)
            assert len(set(vistas)) == 12, (dia_fechamento, dia_vencimento)


# ---------------------------------------------------------------------------
# Chaves
# ---------------------------------------------------------------------------

def test_ida_e_volta_da_chave_de_gasto():
    assert parsear_chave(chave_gasto(123)) == ("gasto", 123, None)


def test_ida_e_volta_da_chave_de_fatura():
    chave = chave_fatura(5, date(2026, 7, 1))
    assert chave == "fatura:5:2026-07-01"
    assert parsear_chave(chave) == ("fatura", 5, date(2026, 7, 1))


@pytest.mark.parametrize("chave", [
    "", None, "gasto", "gasto:abc", "fatura:5", "fatura:5:07-2026",
    "fatura:x:2026-07-01", "projetado-fixa-3-2026-08", "gasto:1:2",
    "DROP TABLE gastos",
])
def test_chave_invalida_vira_400_e_nao_explode(chave):
    with pytest.raises(AppError) as exc:
        parsear_chave(chave)
    assert exc.value.status_code == 400


def test_linha_projetada_nao_e_aceita_como_chave():
    """Linha "previsto" não existe em `gastos` — não há o que marcar como
    pago. O front já a envia como não-editável; o backend recusa de novo."""
    with pytest.raises(AppError):
        parsear_chave("projetado-fixa-7-2026-09")


# ---------------------------------------------------------------------------
# Mês
# ---------------------------------------------------------------------------

def test_mes_none_vira_mes_corrente():
    assert _mes_para_data(None) == date.today().replace(day=1)


def test_mes_valido():
    assert _mes_para_data("2026-07") == date(2026, 7, 1)


@pytest.mark.parametrize("mes", ["2026", "julho/2026", "2026-13", "abc"])
def test_mes_invalido_vira_400(mes):
    with pytest.raises(AppError) as exc:
        _mes_para_data(mes)
    assert exc.value.status_code == 400
