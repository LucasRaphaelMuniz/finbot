"""
services/competencia.py — cálculo de competência (mês contábil) de um gasto.

Usado por parcelamento (Fase 3.2), despesas fixas (Fase 3.3) e pelo registro
normal de gasto avulso em db.py. Função pura, sem dependência de banco —
testável isoladamente.
"""

from datetime import date


def calcular_competencia(data_compra: date, dia_fechamento: int | None,
                          dia_vencimento: int | None = None) -> date:
    """
    Retorna o primeiro dia do mês de competência de um gasto.

    Duas etapas independentes (decisão P, aceita por Lucas em 17/07/2026):

    1. Mês da FATURA: se a forma de pagamento tem dia_fechamento (cartão) e
       a compra aconteceu depois do fechamento daquele mês, a fatura é a do
       mês seguinte — a vigente já fechou. Sem dia_fechamento
       (pix/dinheiro/ticket/Custo Fixo), não existe fatura — a competência
       pára aqui, no mês da própria compra.
    2. Mês do VENCIMENTO: uma fatura de cartão só sai do caixa quando é
       paga, não quando fecha — por isso a competência final (o mês que
       pesa no orçamento) é o mês em que essa fatura VENCE, não o mês em
       que ela fechou. Se dia_vencimento > dia_fechamento, o vencimento cai
       no mesmo mês do fechamento (ex.: fecha dia 5, vence dia 12). Caso
       contrário — dia_vencimento <= dia_fechamento, ou não informado
       (fallback, caso mais comum no Brasil: fecha por volta do dia 25,
       vence no mês seguinte por volta do dia 5) — o vencimento cai no mês
       seguinte ao fechamento.
    """
    ano, mes = data_compra.year, data_compra.month
    if dia_fechamento and data_compra.day > dia_fechamento:
        mes += 1
        if mes > 12:
            mes = 1
            ano += 1

    if dia_fechamento and (dia_vencimento is None or dia_vencimento <= dia_fechamento):
        mes += 1
        if mes > 12:
            mes = 1
            ano += 1

    return date(ano, mes, 1)


def somar_meses(competencia: date, n: int) -> date:
    """
    Soma n meses a uma competência (primeiro dia do mês). Usada para calcular
    a competência de cada parcela a partir da competência da 1ª.
    """
    mes_total = competencia.month - 1 + n
    ano = competencia.year + mes_total // 12
    mes = mes_total % 12 + 1
    return date(ano, mes, 1)
