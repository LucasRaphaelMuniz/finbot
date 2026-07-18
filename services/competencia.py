"""
services/competencia.py — cálculo de competência (mês contábil) de um gasto.

Usado por parcelamento (Fase 3.2), despesas fixas (Fase 3.3) e pelo registro
normal de gasto avulso em db.py. Função pura, sem dependência de banco —
testável isoladamente.
"""

from datetime import date


def calcular_competencia(data_compra: date, dia_fechamento: int | None) -> date:
    """
    Retorna o primeiro dia do mês de competência de um gasto — o mês da
    FATURA a que ele pertence.

    Regra (Fase 3.2 do PLANO_EXECUCAO.md): se a forma de pagamento tem
    dia_fechamento (cartão) e a compra aconteceu depois do fechamento daquele
    mês, a competência é o mês seguinte — a fatura vigente já fechou. Sem
    dia_fechamento (pix/dinheiro/ticket/Custo Fixo), a competência é sempre
    o mês da própria data da compra.

    NOTA (17-18/07/2026, reversão da migração 020 pela 022): chegamos a
    mudar esta função pra competência = mês do VENCIMENTO da fatura
    ("provisionar o cartão no mês em que é pago"). Revertido: isso fazia a
    compra de hoje sumir das telas do mês corrente — impossível acompanhar
    o mês. O modelo final é "fatura como conta a pagar": o gasto fica no
    mês da fatura (esta função), e só o CAIXA provisiona a fatura no mês do
    vencimento — via `mes_vencimento()` abaixo, usada por services/resumo.py
    e services/faturas.py, nunca gravada em gastos.competencia.
    """
    ano, mes = data_compra.year, data_compra.month
    if dia_fechamento and data_compra.day > dia_fechamento:
        mes += 1
        if mes > 12:
            mes = 1
            ano += 1
    return date(ano, mes, 1)


def mes_vencimento(competencia: date, dia_fechamento: int | None,
                    dia_vencimento: int | None) -> date:
    """
    Dado o mês da fatura (competencia, ver calcular_competencia), retorna o
    primeiro dia do mês em que essa fatura VENCE — o mês em que ela pesa no
    caixa (migração 019: dia_vencimento).

    - dia_vencimento > dia_fechamento: fecha e vence no mesmo mês
      (ex.: fecha dia 5, vence dia 12) — retorna a própria competencia.
    - dia_vencimento <= dia_fechamento, ou não informado (fallback — caso
      mais comum no Brasil: fecha ~dia 25, vence ~dia 5 do mês seguinte):
      vence no mês seguinte.
    - Sem dia_fechamento (não é cartão): não existe fatura; retorna a
      própria competencia (o gasto sai do caixa no mês em que aconteceu).

    Função pura, sem banco — testável isoladamente, mesma filosofia de
    calcular_competencia/somar_meses.
    """
    if not dia_fechamento:
        return competencia
    if dia_vencimento is not None and dia_vencimento > dia_fechamento:
        return competencia
    return somar_meses(competencia, 1)


def somar_meses(competencia: date, n: int) -> date:
    """
    Soma n meses a uma competência (primeiro dia do mês). Usada para calcular
    a competência de cada parcela a partir da competência da 1ª.
    """
    mes_total = competencia.month - 1 + n
    ano = competencia.year + mes_total // 12
    mes = mes_total % 12 + 1
    return date(ano, mes, 1)
