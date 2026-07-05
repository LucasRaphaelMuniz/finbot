import psycopg2
from psycopg2.extras import RealDictCursor
from db import get_conn


def get_sessao_ativa(usuario_id: int):
    """Retorna a sessão ativa (não expirada) mais recente ou None."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT *
                   FROM sessoes
                   WHERE usuario_id = %s
                     AND expira_em > NOW()
                   ORDER BY criado_em DESC
                   LIMIT 1""",
                (usuario_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def criar_sessao(usuario_id: int, etapa: str,
                 valor_temp=None, categoria_temp=None, forma_temp=None):
    """Deleta sessão existente e cria nova com timeout de 5 minutos."""
    deletar_sessao(usuario_id)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO sessoes
                       (usuario_id, etapa, valor_temp, categoria_temp, forma_temp,
                        expira_em)
                   VALUES (%s, %s, %s, %s, %s,
                           NOW() + INTERVAL '5 minutes')""",
                (usuario_id, etapa, valor_temp, categoria_temp, forma_temp),
            )
            conn.commit()


def atualizar_sessao(usuario_id: int, etapa: str = None,
                     categoria_temp=None, forma_temp=None):
    """Atualiza campos da sessão ativa e renova o timeout."""
    sets = ["expira_em = NOW() + INTERVAL '5 minutes'"]
    params = []

    if etapa is not None:
        sets.append("etapa = %s")
        params.append(etapa)
    if categoria_temp is not None:
        sets.append("categoria_temp = %s")
        params.append(categoria_temp)
    if forma_temp is not None:
        sets.append("forma_temp = %s")
        params.append(forma_temp)

    params.append(usuario_id)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE sessoes SET {', '.join(sets)} "
                f"WHERE usuario_id = %s AND expira_em > NOW()",
                params,
            )
            conn.commit()


def deletar_sessao(usuario_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sessoes WHERE usuario_id = %s", (usuario_id,))
            conn.commit()


def verificar_sessao_expirada(usuario_id: int) -> bool:
    """Retorna True (e deleta) se existe sessão expirada. False se não há nada."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id FROM sessoes
                   WHERE usuario_id = %s AND expira_em <= NOW()
                   LIMIT 1""",
                (usuario_id,),
            )
            expirada = cur.fetchone()
            if expirada:
                cur.execute("DELETE FROM sessoes WHERE usuario_id = %s", (usuario_id,))
                conn.commit()
                return True
    return False
