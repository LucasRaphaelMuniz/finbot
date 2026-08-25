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


def dia_corte_como_fechamento(dia_corte: int | None) -> int | None:
    """
    Converte "dia de corte" (dia_corte, migração 028 — o dia em que o NOVO
    ciclo já começa, ex.: dia do pagamento) pro formato que
    calcular_competencia entende (dia_fechamento — o ÚLTIMO dia do ciclo
    ATUAL, "day > fechamento" empurra pro mês seguinte).

    São regras INVERSAS de propósito: cartão que "fecha dia 25" ainda conta
    a compra do próprio dia 25 na fatura que está fechando (dia 25 fica no
    mês atual) — mas dia_corte=25 ("recebo dia 25") já é o PRIMEIRO dia do
    ciclo novo (dia 25 já vai pro mês seguinte). Bug corrigido em
    25/08/2026: a 1ª versão desta função tratava os dois igual, e o dia 25
    (dia do pagamento, quando VA/VR renovam de verdade) continuava mostrando
    saldo do ciclo antigo até o dia 26.

    Daí o -1: pra calcular_competencia empurrar a partir do próprio
    dia_corte (day >= dia_corte), o "fechamento equivalente" é o dia
    anterior (day > dia_corte - 1  ⟺  day >= dia_corte).

    dia_corte=1 vira None (0 é falsy em Python) — coerente: um ciclo que já
    começa no dia 1 É o mês calendário, não tem o que deslocar.
    """
    if not dia_corte:
        return None
    return (dia_corte - 1) or None


def dia_regra(dia_fechamento: int | None, dia_corte: int | None) -> int | None:
    """
    Qual "dia" manda na competência de um lançamento: cartão manda
    (dia_fechamento da própria forma) — não muda, decisão do Lucas em
    25/08/2026. Sem cartão (pix/dinheiro/ticket/Custo Fixo, despesa fixa
    fora do cartão, entrada), cai pro dia_corte do usuário (dia em que ele
    recebe — migração 028), já convertido pra semântica de
    calcular_competencia via dia_corte_como_fechamento (ver docstring lá —
    IMPORTANTE: dia_corte não é passado direto, "day > corte" e "day >=
    corte" são regras diferentes).

    Sem os dois (usuário sem dia_corte configurado, hipótese só de dado
    legado/teste — a coluna tem DEFAULT 25), retorna None e
    calcular_competencia cai no comportamento antigo (mês calendário puro).

    Função central de propósito: todo lugar que decide "qual dia usar pra
    calcular_competencia" passa por aqui, em vez de espalhar essa lógica
    pelos services — 1 fonte de verdade pra prioridade
    cartão > corte > mês calendário.
    """
    return dia_fechamento or dia_corte_como_fechamento(dia_corte)


def somar_meses(competencia: date, n: int) -> date:
    """
    Soma n meses a uma competência (primeiro dia do mês). Usada para calcular
    a competência de cada parcela a partir da competência da 1ª.
    """
    mes_total = competencia.month - 1 + n
    ano = competencia.year + mes_total // 12
    mes = mes_total % 12 + 1
    return date(ano, mes, 1)
