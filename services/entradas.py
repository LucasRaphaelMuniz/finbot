"""
services/entradas.py — entradas/receitas (Fase 3.5 do PLANO_EXECUCAO.md, gap G1).

Entrada NÃO afeta saldo por forma de pagamento — limite mensal é um conceito
de gasto, não de receita. Entradas só entram no resumo do mês (bot) e no
dashboard web (saldo do mês = entradas − gastos).

Segue o mesmo padrão grupo_id/usuario_id de formas_pagamento e despesas_fixas:
com grupo, a entrada é compartilhada (soma pra todo mundo do grupo); sem
grupo, é pessoal.
"""

from db import get_conn, _get_grupo_id


def registrar_entrada(usuario_id: int, valor: float, descricao: str = "") -> dict:
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO entradas (usuario_id, grupo_id, descricao, valor)
                   VALUES (%s, %s, %s, %s)
                   RETURNING *""",
                (usuario_id, gid, descricao, valor),
            )
            conn.commit()
            return dict(cur.fetchone())


def get_entradas_mes(usuario_id: int) -> list[dict]:
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    """SELECT * FROM entradas
                       WHERE grupo_id = %s
                         AND DATE_TRUNC('month', data) = DATE_TRUNC('month', NOW())
                       ORDER BY data DESC""",
                    (gid,),
                )
            else:
                cur.execute(
                    """SELECT * FROM entradas
                       WHERE usuario_id = %s AND grupo_id IS NULL
                         AND DATE_TRUNC('month', data) = DATE_TRUNC('month', NOW())
                       ORDER BY data DESC""",
                    (usuario_id,),
                )
            return [dict(r) for r in cur.fetchall()]


def get_total_entradas_mes(usuario_id: int) -> float:
    entradas = get_entradas_mes(usuario_id)
    return sum(float(e["valor"]) for e in entradas)



# ---------------------------------------------------------------------------
# Fase 4.3 — API web: GET /api/resumo?mes= precisa do total de entradas de
# QUALQUER mês (histórico), não só do mês corrente. get_total_entradas_mes
# acima é usado pelo bot (`resumo` sempre é "esse mês") e fica como está;
# esta versão recebe a competência explícita.
# ---------------------------------------------------------------------------

def get_total_entradas_competencia(usuario_id: int, competencia: str) -> float:
    """competencia: "YYYY-MM-01" (ou qualquer data — só o mês/ano importam)."""
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    """SELECT COALESCE(SUM(valor), 0) AS total FROM entradas
                       WHERE grupo_id = %s AND DATE_TRUNC('month', data) = DATE_TRUNC('month', %s::date)""",
                    (gid, competencia),
                )
            else:
                cur.execute(
                    """SELECT COALESCE(SUM(valor), 0) AS total FROM entradas
                       WHERE usuario_id = %s AND grupo_id IS NULL
                         AND DATE_TRUNC('month', data) = DATE_TRUNC('month', %s::date)""",
                    (usuario_id, competencia),
                )
            return float(cur.fetchone()["total"])



# ---------------------------------------------------------------------------
# Fase 4.3 — API web: PUT/DELETE /api/entradas/:id. O bot não edita/exclui
# entrada por id (não tem esse comando ainda), só a API web precisa disso —
# fica aqui, não em routes/entradas.py, pra manter rota fina → service
# (padrão CLAUDE.md).
# ---------------------------------------------------------------------------

def atualizar_entrada(usuario_id: int, entrada_id: int, valor: float = None,
                       descricao: str = None) -> dict | None:
    sets, params = [], []
    if valor is not None:
        sets.append("valor = %s")
        params.append(valor)
    if descricao is not None:
        sets.append("descricao = %s")
        params.append(descricao)
    if not sets:
        return None

    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    f"UPDATE entradas SET {', '.join(sets)} WHERE id = %s AND grupo_id = %s RETURNING *",
                    params + [entrada_id, gid],
                )
            else:
                cur.execute(
                    f"UPDATE entradas SET {', '.join(sets)} "
                    "WHERE id = %s AND usuario_id = %s AND grupo_id IS NULL RETURNING *",
                    params + [entrada_id, usuario_id],
                )
            row = cur.fetchone()
            conn.commit()
            return dict(row) if row else None


def remover_entrada(usuario_id: int, entrada_id: int) -> dict | None:
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    "DELETE FROM entradas WHERE id = %s AND grupo_id = %s RETURNING *",
                    (entrada_id, gid),
                )
            else:
                cur.execute(
                    "DELETE FROM entradas WHERE id = %s AND usuario_id = %s "
                    "AND grupo_id IS NULL RETURNING *",
                    (entrada_id, usuario_id),
                )
            row = cur.fetchone()
            conn.commit()
            return dict(row) if row else None
