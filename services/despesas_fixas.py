"""
services/despesas_fixas.py — despesas fixas recorrentes (Fase 3.3 do PLANO_EXECUCAO.md).

Uma despesa fixa é lançada automaticamente como um gasto normal todo mês, no
dia configurado (dia_lancamento), por `lancar_despesas_fixas_do_mes()` —
chamada pelo cron diário do Railway (jobs/lancar_fixas.py, decisão D4).

Ao contrário de categorias (Fase 3.1), `despesas_fixas` tem `usuario_id` além
de `grupo_id` (migração 004) — funciona tanto pra quem tem grupo quanto pra
conta individual, sem o gap que apareceu em categorias.

Decisão que vale destacar: "remover" é soft-delete (`ativa = FALSE`), não
DELETE. Motivo: uma vez que uma despesa fixa já lançou pelo menos um gasto,
`gastos.despesa_fixa_id` referencia essa linha sem ON DELETE CASCADE/SET NULL
(migração 004) — um DELETE de verdade quebraria com violação de FK assim que
houvesse histórico. A coluna `ativa` já existe no schema aprovado justamente
para isso; o lançador só considera `ativa = TRUE`.

Simplificação assumida: a competência do gasto lançado é sempre o mês em que
ele foi lançado (não ajustada pelo dia_fechamento da forma de pagamento, ao
contrário do parcelamento — Fase 3.2). Se uma despesa fixa em cartão precisar
do mesmo deslocamento de competência que compras avulsas têm, isso fica pra
revisar depois — o plano não especificou esse detalhe para despesas fixas.
"""

import calendar
from datetime import date

import psycopg
from db import get_conn, _get_grupo_id


def get_despesas_fixas(usuario_id: int, apenas_ativas: bool = True) -> list[dict]:
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            filtro_ativa = "AND ativa = TRUE" if apenas_ativas else ""
            if gid:
                cur.execute(
                    f"SELECT * FROM despesas_fixas WHERE grupo_id = %s {filtro_ativa} "
                    "ORDER BY dia_lancamento, descricao",
                    (gid,),
                )
            else:
                cur.execute(
                    f"SELECT * FROM despesas_fixas WHERE usuario_id = %s AND grupo_id IS NULL "
                    f"{filtro_ativa} ORDER BY dia_lancamento, descricao",
                    (usuario_id,),
                )
            return [dict(r) for r in cur.fetchall()]


def criar_despesa_fixa(usuario_id: int, descricao: str, valor: float, dia_lancamento: int,
                        categoria_id: int = None, forma_pagamento_id: int = None) -> dict:
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO despesas_fixas
                       (grupo_id, usuario_id, categoria_id, forma_pagamento_id,
                        descricao, valor, dia_lancamento)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   RETURNING *""",
                (gid, usuario_id, categoria_id, forma_pagamento_id, descricao, valor, dia_lancamento),
            )
            conn.commit()
            return dict(cur.fetchone())


def desativar_despesa_fixa(usuario_id: int, descricao: str) -> bool:
    """Soft-delete: marca ativa=False. Não lança mais, mas preserva o histórico já lançado."""
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    "UPDATE despesas_fixas SET ativa = FALSE "
                    "WHERE grupo_id = %s AND ativa = TRUE AND LOWER(descricao) LIKE %s RETURNING id",
                    (gid, f"%{descricao.lower()}%"),
                )
            else:
                cur.execute(
                    "UPDATE despesas_fixas SET ativa = FALSE "
                    "WHERE usuario_id = %s AND grupo_id IS NULL AND ativa = TRUE "
                    "AND LOWER(descricao) LIKE %s RETURNING id",
                    (usuario_id, f"%{descricao.lower()}%"),
                )
            updated = cur.fetchone()
            conn.commit()
            return updated is not None


def _dia_efetivo(dia_lancamento: int, ano: int, mes: int) -> int:
    """
    Capa o dia de lançamento no último dia do mês — ex.: dia_lancamento=31 em
    fevereiro lança no dia 28 (ou 29 em ano bissexto), em vez de nunca lançar
    naquele mês porque ele não tem dia 31.
    """
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    return min(dia_lancamento, ultimo_dia)


def lancar_despesas_fixas_do_mes(hoje: date = None) -> list[dict]:
    """
    Lança como gasto normal toda despesa fixa ativa cujo dia efetivo de
    lançamento é hoje, e que ainda não foi lançada nessa competência.

    Idempotente: chamar de novo no mesmo dia não duplica — checagem prévia
    (SELECT) mais o índice único uq_despesa_fixa_mes como segunda camada de
    proteção contra corrida (2 execuções do cron sobrepostas, por exemplo).
    Pensada pra rodar 1x/dia via cron (jobs/lancar_fixas.py, decisão D4).
    """
    hoje = hoje or date.today()
    competencia = hoje.replace(day=1)
    lancados = []

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM despesas_fixas WHERE ativa = TRUE")
            fixas = [dict(r) for r in cur.fetchall()]

        for fixa in fixas:
            dia_efetivo = _dia_efetivo(fixa["dia_lancamento"], hoje.year, hoje.month)
            if hoje.day != dia_efetivo:
                continue

            with conn.cursor() as cur:
                cur.execute(
                    """SELECT 1 FROM gastos
                       WHERE despesa_fixa_id = %s
                         AND DATE_TRUNC('month', competencia) = DATE_TRUNC('month', %s::date)""",
                    (fixa["id"], competencia),
                )
                if cur.fetchone():
                    continue  # já lançada essa competência

                try:
                    cur.execute(
                        """INSERT INTO gastos
                               (usuario_id, forma_pagamento_id, categoria_id, valor, descricao,
                                grupo_id, competencia, despesa_fixa_id)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                           RETURNING *""",
                        (fixa["usuario_id"], fixa["forma_pagamento_id"], fixa["categoria_id"],
                         fixa["valor"], fixa["descricao"], fixa["grupo_id"], competencia, fixa["id"]),
                    )
                    gasto = dict(cur.fetchone())
                    conn.commit()
                    lancados.append(gasto)
                except psycopg.errors.UniqueViolation:
                    conn.rollback()
                    continue

    return lancados



# ---------------------------------------------------------------------------
# Operações por id (Fase 4.3 — API web, PUT/DELETE /api/fixas/:id)
# Mesmo raciocínio de services/categorias.py: bot busca por descrição
# (fuzzy), web já tem o id exato.
# ---------------------------------------------------------------------------

def atualizar_despesa_fixa(usuario_id: int, fixa_id: int, descricao: str = None,
                            valor: float = None, dia_lancamento: int = None,
                            categoria_id: int = None, forma_pagamento_id: int = None) -> dict | None:
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        sets, params = [], []
        for campo, valor_campo in (
            ("descricao", descricao), ("valor", valor), ("dia_lancamento", dia_lancamento),
            ("categoria_id", categoria_id), ("forma_pagamento_id", forma_pagamento_id),
        ):
            if valor_campo is not None:
                sets.append(f"{campo} = %s")
                params.append(valor_campo)
        if not sets:
            return None

        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    f"UPDATE despesas_fixas SET {', '.join(sets)} "
                    "WHERE id = %s AND grupo_id = %s RETURNING *",
                    params + [fixa_id, gid],
                )
            else:
                cur.execute(
                    f"UPDATE despesas_fixas SET {', '.join(sets)} "
                    "WHERE id = %s AND usuario_id = %s AND grupo_id IS NULL RETURNING *",
                    params + [fixa_id, usuario_id],
                )
            row = cur.fetchone()
            conn.commit()
            return dict(row) if row else None


def desativar_despesa_fixa_por_id(usuario_id: int, fixa_id: int) -> bool:
    """Soft-delete por id (mesma razão da versão por descrição usada pelo
    bot: gastos.despesa_fixa_id não tem ON DELETE CASCADE/SET NULL)."""
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    "UPDATE despesas_fixas SET ativa = FALSE "
                    "WHERE id = %s AND grupo_id = %s AND ativa = TRUE RETURNING id",
                    (fixa_id, gid),
                )
            else:
                cur.execute(
                    "UPDATE despesas_fixas SET ativa = FALSE "
                    "WHERE id = %s AND usuario_id = %s AND grupo_id IS NULL AND ativa = TRUE RETURNING id",
                    (fixa_id, usuario_id),
                )
            updated = cur.fetchone()
            conn.commit()
            return updated is not None
