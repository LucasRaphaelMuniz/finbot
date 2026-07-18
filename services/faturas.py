"""
services/faturas.py — status simples de cartão (revisão final 18/07/2026).

Modelo de uma frase, fechado com o Lucas depois de DUAS tentativas mais
complexas: **o gasto mensal do cartão e o valor da fatura são o mesmo
número** — o que se gasta no cartão em julho é a fatura de julho; a única
diferença é quando sai do bolso (agosto, via provisão de caixa em
services/resumo.py).

Histórico do que foi tentado e descartado, pra ninguém reintroduzir sem
saber por quê:
1. Competência = mês do vencimento (migração 020): a compra de hoje sumia
   das telas do mês corrente. Revertido pela 022.
2. Limite rotativo real (021: faturas_pagas + parcelas futuras + fatura
   fechada não paga + comando "paguei a fatura"): modelava como o BANCO
   enxerga limite, não como o Lucas acompanha o orçamento — o número
   "limite usado" misturava meses e parcelas futuras e não respondia
   "quanto gastei este mês?". Removido pela migração 024 (dropa
   faturas_pagas).

O que ficou:
- fatura_atual: a fatura que está acumulando as compras de agora
  (calcular_competencia de hoje) — É o gasto mensal do cartão, comparado
  direto com limite_mensal.
- fatura_anterior: a fatura já fechada, com o mês em que vence
  (mes_vencimento) — informativo de "quanto vou pagar agora", mesma conta
  que o caixa do resumo provisiona.
"""

from datetime import date

from db import get_conn, _get_grupo_id
from services.competencia import calcular_competencia, mes_vencimento, somar_meses


def _forma_pertence_ao_usuario(conn, usuario_id: int, forma_id: int) -> bool:
    gid = _get_grupo_id(conn, usuario_id)
    with conn.cursor() as cur:
        if gid:
            cur.execute(
                "SELECT 1 FROM formas_pagamento WHERE id = %s AND grupo_id = %s",
                (forma_id, gid),
            )
        else:
            cur.execute(
                "SELECT 1 FROM formas_pagamento WHERE id = %s AND usuario_id = %s AND grupo_id IS NULL",
                (forma_id, usuario_id),
            )
        return cur.fetchone() is not None


def status_cartao(usuario_id: int, forma_id: int) -> dict | None:
    """
    Status da forma tipo cartão:

    - fatura_atual: soma dos gastos da competência que ainda aceita compras
      hoje. É O GASTO MENSAL DO CARTÃO — comparar com limite_mensal.
    - fatura_anterior: a fatura fechada, e em que mês ela vence
      (vencimento_fatura_anterior) — o valor que vai sair do caixa.

    Retorna None se a forma não existe/não pertence ao usuário.
    """
    with get_conn() as conn:
        if not _forma_pertence_ao_usuario(conn, usuario_id, forma_id):
            return None

        with conn.cursor() as cur:
            cur.execute(
                "SELECT nome, limite_mensal, dia_fechamento, dia_vencimento "
                "FROM formas_pagamento WHERE id = %s",
                (forma_id,),
            )
            forma = cur.fetchone()
            if not forma:
                return None
            forma = dict(forma)

            hoje = date.today()
            comp_atual = calcular_competencia(hoje, forma.get("dia_fechamento"))
            comp_anterior = somar_meses(comp_atual, -1)

            cur.execute(
                """SELECT
                       COALESCE(SUM(valor) FILTER (
                           WHERE DATE_TRUNC('month', competencia) = %s
                       ), 0) AS fatura_atual,
                       COALESCE(SUM(valor) FILTER (
                           WHERE DATE_TRUNC('month', competencia) = %s
                       ), 0) AS fatura_anterior
                   FROM gastos
                   WHERE forma_pagamento_id = %s""",
                (comp_atual, comp_anterior, forma_id),
            )
            row = dict(cur.fetchone())

    limite_mensal = float(forma["limite_mensal"]) if forma["limite_mensal"] else None
    fatura_atual = float(row["fatura_atual"])
    venc_anterior = mes_vencimento(comp_anterior, forma.get("dia_fechamento"),
                                    forma.get("dia_vencimento"))

    return {
        "forma_id": forma_id,
        "nome": forma["nome"],
        "limite_mensal": limite_mensal,
        "fatura_atual": fatura_atual,
        "limite_disponivel": (limite_mensal - fatura_atual) if limite_mensal is not None else None,
        "fatura_anterior": float(row["fatura_anterior"]),
        "competencia_atual": comp_atual.isoformat(),
        "competencia_anterior": comp_anterior.isoformat(),
        "vencimento_fatura_anterior": venc_anterior.isoformat(),
    }


def status_todos_cartoes(usuario_id: int) -> list[dict]:
    """status_cartao para toda forma com dia_fechamento (as sem — pix/
    débito/Custo Fixo — não têm fatura; ficam no saldo simples)."""
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    "SELECT id FROM formas_pagamento WHERE grupo_id = %s AND dia_fechamento IS NOT NULL "
                    "ORDER BY nome",
                    (gid,),
                )
            else:
                cur.execute(
                    "SELECT id FROM formas_pagamento WHERE usuario_id = %s AND grupo_id IS NULL "
                    "AND dia_fechamento IS NOT NULL ORDER BY nome",
                    (usuario_id,),
                )
            ids = [r["id"] for r in cur.fetchall()]

    return [status_cartao(usuario_id, fid) for fid in ids]
