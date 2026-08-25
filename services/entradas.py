"""
services/entradas.py — entradas/receitas (Fase 3.5 do PLANO_EXECUCAO.md, gap G1).

Entrada NÃO afeta saldo por forma de pagamento — limite mensal é um conceito
de gasto, não de receita. Entradas só entram no resumo do mês (bot) e no
dashboard web (saldo do mês = entradas − gastos).

Segue o mesmo padrão grupo_id/usuario_id de formas_pagamento e despesas_fixas:
com grupo, a entrada é compartilhada (soma pra todo mundo do grupo); sem
grupo, é pessoal.
"""

from datetime import date as _date

from db import get_conn, _get_grupo_id, _get_dia_corte
from services.competencia import calcular_competencia, dia_corte_como_fechamento


def registrar_entrada(usuario_id: int, valor: float, descricao: str = "",
                       entrada_fixa_id: int = None, data=None) -> dict:
    """
    entrada_fixa_id (migração 023): vincula a entrada ao modelo recorrente
    que a originou — o índice uq_entrada_fixa_mes usa isso pra impedir 2
    lançamentos da mesma fixa no mesmo mês.

    `data` (24/07/2026, pedido do Lucas: "opção de incluir uma nova [entrada]
    no mês em referência" — o board de /contas navega meses, e sem isso
    toda entrada criada por lá nascia com a data de HOJE, mesmo olhando
    agosto em julho). None = comportamento de sempre, usa o DEFAULT NOW()
    da coluna (migração 005) — o bot e o form de Lançamentos não precisam
    mudar nada.

    `competencia` (migração 028): mesma régua de `gastos.competencia`, só
    que entrada não tem cartão — usa sempre o dia_corte do usuário (dia do
    pagamento/recebimento, pedido do Lucas em 25/08/2026), convertido via
    dia_corte_como_fechamento (regra INVERSA de dia_fechamento — o próprio
    dia_corte já pertence ao ciclo novo). Salário recebido no dia_corte ou
    depois já entra no mês seguinte.
    """
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        dia_corte = _get_dia_corte(conn, usuario_id)
        data_ref = data if data is not None else _date.today()
        competencia = calcular_competencia(data_ref, dia_corte_como_fechamento(dia_corte))
        with conn.cursor() as cur:
            if data is not None:
                cur.execute(
                    """INSERT INTO entradas
                           (usuario_id, grupo_id, descricao, valor, entrada_fixa_id, data, competencia)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)
                       RETURNING *""",
                    (usuario_id, gid, descricao, valor, entrada_fixa_id, data, competencia),
                )
            else:
                cur.execute(
                    """INSERT INTO entradas
                           (usuario_id, grupo_id, descricao, valor, entrada_fixa_id, competencia)
                       VALUES (%s, %s, %s, %s, %s, %s)
                       RETURNING *""",
                    (usuario_id, gid, descricao, valor, entrada_fixa_id, competencia),
                )
            conn.commit()
            return dict(cur.fetchone())


def get_entradas_mes(usuario_id: int) -> list[dict]:
    # LEFT JOIN entradas_fixas pra devolver recorrente_ativa — a tela de
    # editar precisa saber se a recorrência está LIGADA agora, não só se a
    # entrada nasceu de um modelo (entrada_fixa_id fica pra sempre, mesmo
    # depois de desativar; usar só ele deixaria o checkbox marcado errado).
    #
    # "Mês atual" (migração 028) é sobre e.competencia (dia_corte), não mais
    # e.data — mesma mudança de db.py::_SQL_COMPETENCIA_ATUAL, só que aqui
    # não tem cartão envolvido, então dá pra calcular em Python direto.
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        dia_corte = _get_dia_corte(conn, usuario_id)
        competencia_atual = calcular_competencia(_date.today(), dia_corte_como_fechamento(dia_corte))
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    """SELECT e.*, COALESCE(ef.ativa, FALSE) AS recorrente_ativa,
                              ef.dia_lancamento AS recorrente_dia
                       FROM entradas e
                       LEFT JOIN entradas_fixas ef ON ef.id = e.entrada_fixa_id
                       WHERE e.grupo_id = %s
                         AND DATE_TRUNC('month', e.competencia) = DATE_TRUNC('month', %s::date)
                       ORDER BY e.data DESC""",
                    (gid, competencia_atual),
                )
            else:
                cur.execute(
                    """SELECT e.*, COALESCE(ef.ativa, FALSE) AS recorrente_ativa,
                              ef.dia_lancamento AS recorrente_dia
                       FROM entradas e
                       LEFT JOIN entradas_fixas ef ON ef.id = e.entrada_fixa_id
                       WHERE e.usuario_id = %s AND e.grupo_id IS NULL
                         AND DATE_TRUNC('month', e.competencia) = DATE_TRUNC('month', %s::date)
                       ORDER BY e.data DESC""",
                    (usuario_id, competencia_atual),
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

def get_entradas_competencia(usuario_id: int, competencia: str) -> list[dict]:
    """
    Versão lista (não só soma) de get_total_entradas_competencia — gap
    documentado desde a Fase 4.3 em routes/entradas.py (GET só cobria o mês
    corrente via get_entradas_mes). Preenchido em 24/07/2026 pro popup de
    detalhe do gráfico "últimos 6 meses" do dashboard: clicar numa barra de
    entrada de um mês qualquer precisa dos lançamentos daquele mês, não só
    do corrente.
    """
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    """SELECT * FROM entradas
                       WHERE grupo_id = %s AND DATE_TRUNC('month', competencia) = DATE_TRUNC('month', %s::date)
                       ORDER BY data DESC""",
                    (gid, competencia),
                )
            else:
                cur.execute(
                    """SELECT * FROM entradas
                       WHERE usuario_id = %s AND grupo_id IS NULL
                         AND DATE_TRUNC('month', competencia) = DATE_TRUNC('month', %s::date)
                       ORDER BY data DESC""",
                    (usuario_id, competencia),
                )
            return [dict(r) for r in cur.fetchall()]


def get_total_entradas_competencia(usuario_id: int, competencia: str) -> float:
    """competencia: "YYYY-MM-01" (ou qualquer data — só o mês/ano importam)."""
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    """SELECT COALESCE(SUM(valor), 0) AS total FROM entradas
                       WHERE grupo_id = %s AND DATE_TRUNC('month', competencia) = DATE_TRUNC('month', %s::date)""",
                    (gid, competencia),
                )
            else:
                cur.execute(
                    """SELECT COALESCE(SUM(valor), 0) AS total FROM entradas
                       WHERE usuario_id = %s AND grupo_id IS NULL
                         AND DATE_TRUNC('month', competencia) = DATE_TRUNC('month', %s::date)""",
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
