"""
services/formas.py — CRUD de formas de pagamento para a API web (Fase 4.3).
db.py já tem get_formas_pagamento/adicionar_forma_pagamento/etc. usados pelo
bot, mas lá a busca de update/remove é sempre por nome (fuzzy, LIKE) — faz
sentido no chat, não faz sentido na web, onde o front já manda o id exato
vindo da linha clicada na tabela. Por isso as operações por id ficam aqui,
em vez de generalizar as funções do bot.
"""

from db import get_conn, _get_grupo_id


def criar_forma(usuario_id: int, nome: str, limite_mensal: float = None,
                 dia_fechamento: int = None) -> dict:
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO formas_pagamento
                       (usuario_id, grupo_id, nome, limite_mensal, dia_fechamento)
                   VALUES (%s, %s, %s, %s, %s) RETURNING *""",
                (usuario_id, gid, nome, limite_mensal, dia_fechamento),
            )
            conn.commit()
            return dict(cur.fetchone())


def atualizar_forma(usuario_id: int, forma_id: int, nome: str = None,
                     limite_mensal: float = None, dia_fechamento: int = None) -> dict | None:
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        sets, params = [], []
        if nome is not None:
            sets.append("nome = %s")
            params.append(nome)
        if limite_mensal is not None:
            sets.append("limite_mensal = %s")
            params.append(limite_mensal)
        if dia_fechamento is not None:
            sets.append("dia_fechamento = %s")
            params.append(dia_fechamento)
        if not sets:
            return None

        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    f"UPDATE formas_pagamento SET {', '.join(sets)} "
                    "WHERE id = %s AND grupo_id = %s RETURNING *",
                    params + [forma_id, gid],
                )
            else:
                cur.execute(
                    f"UPDATE formas_pagamento SET {', '.join(sets)} "
                    "WHERE id = %s AND usuario_id = %s AND grupo_id IS NULL RETURNING *",
                    params + [forma_id, usuario_id],
                )
            row = cur.fetchone()
            conn.commit()
            return dict(row) if row else None


def remover_forma(usuario_id: int, forma_id: int) -> bool:
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    "DELETE FROM formas_pagamento WHERE id = %s AND grupo_id = %s RETURNING id",
                    (forma_id, gid),
                )
            else:
                cur.execute(
                    "DELETE FROM formas_pagamento WHERE id = %s AND usuario_id = %s "
                    "AND grupo_id IS NULL RETURNING id",
                    (forma_id, usuario_id),
                )
            deleted = cur.fetchone()
            conn.commit()
            return deleted is not None
