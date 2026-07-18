"""
services/faturas.py — limite rotativo real do cartão (decisão P, aceita por
Lucas em 17/07/2026; migração 021).

Com a mudança de `services/competencia.py` (019/020), `gastos.competencia`
de cartão virou o mês do VENCIMENTO da fatura — bom pro orçamento, mas
"gasto do mês corrente" sozinho não responde mais "quanto do limite eu já
comprometi": uma parcela que só vai virar gasto lançado daqui a 3 meses já
ocupa limite no cartão de verdade, e uma fatura fechada ainda não paga
também. Este módulo trata isso à parte do saldo/orçamento (db.py,
services/resumo.py).

Modelo: limite_usado = tudo que já foi gasto na forma, menos o que já foi
coberto por fatura marcada como paga (`faturas_pagas`). Sem tabela de
"valor da fatura" separada — soma direto de `gastos` por competência.
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


def marcar_fatura_paga(usuario_id: int, forma_id: int, competencia: str = None) -> dict | None:
    """
    Marca a fatura de `competencia` como paga. Padrão (sem competencia
    explícita): a fatura FECHADA mais recente — a anterior à que ainda
    aceita compras hoje. É a que a pessoa quer dizer com "paguei a fatura":
    a aberta ainda nem fechou, não tem como ter sido paga.

    Idempotente: marcar de novo a mesma competência não duplica (UNIQUE de
    021) nem quebra — retorna o registro já existente.

    Retorna None se a forma não existe ou não pertence ao usuário/grupo.
    """
    with get_conn() as conn:
        if not _forma_pertence_ao_usuario(conn, usuario_id, forma_id):
            return None

        if competencia:
            comp = date(*(int(p) for p in competencia.split("-")[:2]), 1)
        else:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT dia_fechamento FROM formas_pagamento WHERE id = %s", (forma_id,)
                )
                row = cur.fetchone()
            dia_fechamento = row["dia_fechamento"] if row else None
            comp = somar_meses(calcular_competencia(date.today(), dia_fechamento), -1)

        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO faturas_pagas (forma_pagamento_id, competencia)
                   VALUES (%s, %s)
                   ON CONFLICT (forma_pagamento_id, competencia) DO NOTHING
                   RETURNING *""",
                (forma_id, comp),
            )
            row = cur.fetchone()
            if not row:
                # Já estava marcada — devolve o registro existente em vez
                # de None, pra "paguei a fatura" 2x seguidas não parecer erro.
                cur.execute(
                    "SELECT * FROM faturas_pagas WHERE forma_pagamento_id = %s AND competencia = %s",
                    (forma_id, comp),
                )
                row = cur.fetchone()
            conn.commit()
            return dict(row) if row else None


def status_cartao(usuario_id: int, forma_id: int) -> dict | None:
    """
    Retorna o status de limite rotativo de uma forma de pagamento tipo
    cartão. Sob o modelo "fatura como conta a pagar" (revisão de
    17-18/07/2026, ver services/competencia.py):

    - fatura ABERTA: a competência que ainda aceita compras hoje —
      `calcular_competencia(hoje, dia_fechamento)`. Antes do fechamento do
      mês, é o próprio mês; depois, o seguinte.
    - fatura FECHADA a pagar: a competência anterior à aberta, se ainda não
      tem registro em faturas_pagas. Vence em `vencimento_fatura_fechada`
      (mes_vencimento — é essa data que o caixa do resumo provisiona).
    - limite_usado: tudo que já foi gasto na forma menos o coberto por
      fatura paga — inclui parcelas futuras, como num cartão real.

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
            comp_aberta = calcular_competencia(hoje, forma.get("dia_fechamento"))
            comp_fechada = somar_meses(comp_aberta, -1)

            cur.execute(
                """SELECT
                       COALESCE(SUM(g.valor), 0) AS total_gasto,
                       COALESCE(SUM(g.valor) FILTER (
                           WHERE fpg.competencia IS NOT NULL
                       ), 0) AS total_pago,
                       COALESCE(SUM(g.valor) FILTER (
                           WHERE DATE_TRUNC('month', g.competencia) = %s AND fpg.competencia IS NULL
                       ), 0) AS fatura_fechada_a_pagar,
                       COALESCE(SUM(g.valor) FILTER (
                           WHERE DATE_TRUNC('month', g.competencia) = %s
                       ), 0) AS fatura_aberta
                   FROM gastos g
                   LEFT JOIN faturas_pagas fpg
                     ON fpg.forma_pagamento_id = g.forma_pagamento_id
                    AND DATE_TRUNC('month', fpg.competencia) = DATE_TRUNC('month', g.competencia)
                   WHERE g.forma_pagamento_id = %s""",
                (comp_fechada, comp_aberta, forma_id),
            )
            row = dict(cur.fetchone())

    limite_mensal = float(forma["limite_mensal"]) if forma["limite_mensal"] else None
    limite_usado = float(row["total_gasto"]) - float(row["total_pago"])
    venc_fechada = mes_vencimento(comp_fechada, forma.get("dia_fechamento"),
                                   forma.get("dia_vencimento"))

    return {
        "forma_id": forma_id,
        "nome": forma["nome"],
        "limite_mensal": limite_mensal,
        "limite_usado": limite_usado,
        "limite_disponivel": (limite_mensal - limite_usado) if limite_mensal is not None else None,
        "fatura_fechada_a_pagar": float(row["fatura_fechada_a_pagar"]),
        "fatura_aberta": float(row["fatura_aberta"]),
        "competencia_fechada": comp_fechada.isoformat(),
        "competencia_aberta": comp_aberta.isoformat(),
        "vencimento_fatura_fechada": venc_fechada.isoformat(),
    }


def status_todos_cartoes(usuario_id: int) -> list[dict]:
    """Mesma coisa que status_cartao, mas para toda forma com dia_fechamento
    (as sem dia_fechamento — pix/débito/Custo Fixo — não têm fatura, não
    entram aqui; continuam no saldo simples de db.get_saldo_todas_formas)."""
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
