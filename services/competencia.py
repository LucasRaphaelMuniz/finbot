"""
services/competencia.py — cálculo de competência (mês contábil) de um gasto.

Usado por parcelamento (Fase 3.2), despesas fixas (Fase 3.3) e pelo registro
normal de gasto avulso em db.py. Função pura, sem dependência de banco —
testável isoladamente.
"""

from datetime import date


def calcular_competencia(data_compra: date, dia_fechamento: int | None) -> date:
    """
    Retorna o primeiro dia do mês de competência de um gasto.

    Regra (Fase 3.2 do PLANO_EXECUCAO.md): se a forma de pagamento tem
    dia_fechamento (cartão) e a compra aconteceu depois do fechamento daquele
    mês, a competência é o mês seguinte — a fatura vigente já fechou. Sem
    dia_fechamento (pix/dinheiro/ticket), a competência é sempre o mês da
    própria data da compra.
    """
    ano, mes = data_compra.year, data_compra.month
    if dia_fechamento and data_compra.day > dia_fechamento:
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
