"""
services/parcelamento.py — compras parceladas (Fase 3.2 do PLANO_EXECUCAO.md).
"""

from datetime import date

from db import get_conn
from services.competencia import calcular_competencia, somar_meses

_MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março",    4: "Abril",
    5: "Maio",    6: "Junho",     7: "Julho",     8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}


def dividir_parcelas(valor_total: float, parcelas: int) -> list[float]:
    """
    Divide valor_total em `parcelas` parcelas de 2 casas decimais.

    Arredonda cada parcela para 2 casas e joga o resíduo do arredondamento
    inteiro na 1ª parcela — garante que a soma das parcelas bate exatamente
    com valor_total (auditável), em vez de espalhar centavos de diferença
    entre parcelas de forma imprevisível.
    """
    if parcelas < 1:
        raise ValueError("parcelas deve ser >= 1")
    valor_parcela = round(valor_total / parcelas, 2)
    residuo = round(valor_total - valor_parcela * parcelas, 2)
    return [round(valor_parcela + residuo, 2)] + [valor_parcela] * (parcelas - 1)


def formatar_competencia(data_competencia: date) -> str:
    return f"{_MESES_PT[data_competencia.month]}/{data_competencia.year}"


def criar_compra_parcelada(usuario_id: int, grupo_id, forma: dict, categoria: dict,
                            valor_total: float, parcelas: int, descricao: str):
    """
    Cria a compra parcelada + N gastos (1 por parcela), cada um com
    parcela_num e competencia própria calculada a partir do dia_fechamento
    da forma (Fase 3.2).

    Retorna (compra, gastos_criados, valor_parcela_padrao) — valor_parcela_padrao
    é o valor das parcelas 2..N (a 1ª pode ter alguns centavos a mais, ver
    dividir_parcelas).
    """
    data_compra = date.today()
    dia_fechamento = forma.get("dia_fechamento")
    dia_vencimento = forma.get("dia_vencimento")
    competencia_1a = calcular_competencia(data_compra, dia_fechamento, dia_vencimento)
    valores = dividir_parcelas(valor_total, parcelas)
    categoria_id = categoria["id"] if categoria else None

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO compras_parceladas
                       (usuario_id, grupo_id, forma_pagamento_id, categoria_id,
                        descricao, valor_total, parcelas, data_compra)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING *""",
                (usuario_id, grupo_id, forma["id"], categoria_id,
                 descricao, valor_total, parcelas, data_compra),
            )
            compra = dict(cur.fetchone())

            gastos_criados = []
            for i, valor_i in enumerate(valores, start=1):
                competencia_i = somar_meses(competencia_1a, i - 1)
                cur.execute(
                    """INSERT INTO gastos
                           (usuario_id, forma_pagamento_id, categoria_id, valor, descricao,
                            grupo_id, competencia, compra_parcelada_id, parcela_num)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING *""",
                    (usuario_id, forma["id"], categoria_id, valor_i,
                     descricao, grupo_id, competencia_i, compra["id"], i),
                )
                gastos_criados.append(dict(cur.fetchone()))

            conn.commit()
            valor_parcela_padrao = valores[1] if parcelas > 1 else valores[0]
            return compra, gastos_criados, valor_parcela_padrao


def excluir_compra_parcelada(compra_id: int) -> dict | None:
    """Exclui todas as parcelas de uma compra + o registro da compra. Retorna a compra ou None."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM compras_parceladas WHERE id = %s", (compra_id,))
            row = cur.fetchone()
            if not row:
                return None
            compra = dict(row)
            cur.execute("DELETE FROM gastos WHERE compra_parcelada_id = %s", (compra_id,))
            cur.execute("DELETE FROM compras_parceladas WHERE id = %s", (compra_id,))
            conn.commit()
            return compra
