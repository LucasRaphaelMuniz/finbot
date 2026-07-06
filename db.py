import os
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Conexão
# ---------------------------------------------------------------------------

def get_conn():
    return psycopg.connect(os.getenv("DATABASE_URL"), row_factory=dict_row)


FORMAS_PADRAO = [
    ("Cartão",       3000.00),
    ("Pix/Dinheiro", 1500.00),
    ("Ticket",        600.00),
]

# ---------------------------------------------------------------------------
# Helper interno
# ---------------------------------------------------------------------------

def _get_grupo_id(conn, usuario_id: int):
    with conn.cursor() as cur:
        cur.execute("SELECT grupo_id FROM usuarios WHERE id = %s", (usuario_id,))
        row = cur.fetchone()
        return row["grupo_id"] if row else None


# ---------------------------------------------------------------------------
# Usuários
# ---------------------------------------------------------------------------

def get_or_create_usuario(telefone: str):
    """Retorna (usuario_dict, is_new). Cria formas de pagamento padrão no 1.º acesso."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM usuarios WHERE telefone = %s", (telefone,))
            usuario = cur.fetchone()
            if usuario:
                return dict(usuario), False

            cur.execute(
                "INSERT INTO usuarios (nome, telefone) VALUES (%s, %s) RETURNING *",
                (telefone, telefone),
            )
            novo = dict(cur.fetchone())
            uid = novo["id"]

            for nome, limite in FORMAS_PADRAO:
                cur.execute(
                    "INSERT INTO formas_pagamento (usuario_id, nome, limite_mensal) "
                    "VALUES (%s, %s, %s)",
                    (uid, nome, limite),
                )

            conn.commit()
            return novo, True


def get_usuario(usuario_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM usuarios WHERE id = %s", (usuario_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def set_nome_usuario(usuario_id: int, nome: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE usuarios SET nome = %s WHERE id = %s", (nome, usuario_id))
            conn.commit()


def set_parceiro_telefone(usuario_id: int, telefone: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE usuarios SET parceiro_telefone = %s WHERE id = %s",
                (telefone, usuario_id),
            )
            conn.commit()


# ---------------------------------------------------------------------------
# Categorias e formas de pagamento
# ---------------------------------------------------------------------------

def get_categorias():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM categorias ORDER BY nome")
            return [dict(r) for r in cur.fetchall()]


def get_formas_pagamento(usuario_id: int):
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    "SELECT * FROM formas_pagamento WHERE grupo_id = %s ORDER BY nome",
                    (gid,),
                )
            else:
                cur.execute(
                    "SELECT * FROM formas_pagamento WHERE usuario_id = %s AND grupo_id IS NULL ORDER BY nome",
                    (usuario_id,),
                )
            return [dict(r) for r in cur.fetchall()]


def adicionar_forma_pagamento(usuario_id: int, nome: str, limite: float = None):
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO formas_pagamento (usuario_id, grupo_id, nome, limite_mensal) VALUES (%s, %s, %s, %s)",
                (usuario_id, gid, nome, limite),
            )
            conn.commit()


def remover_forma_pagamento(usuario_id: int, nome_forma: str) -> bool:
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    "DELETE FROM formas_pagamento WHERE grupo_id = %s AND LOWER(nome) LIKE %s RETURNING id",
                    (gid, f"%{nome_forma.lower()}%"),
                )
            else:
                cur.execute(
                    "DELETE FROM formas_pagamento WHERE usuario_id = %s AND grupo_id IS NULL AND LOWER(nome) LIKE %s RETURNING id",
                    (usuario_id, f"%{nome_forma.lower()}%"),
                )
            deleted = cur.fetchone()
            conn.commit()
            return deleted is not None


# ---------------------------------------------------------------------------
# Gastos
# ---------------------------------------------------------------------------

def registrar_gasto(usuario_id: int, forma_id: int, categoria_id: int,
                    valor: float, descricao: str, grupo_id: int = None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO gastos
                       (usuario_id, forma_pagamento_id, categoria_id, valor, descricao, grupo_id)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   RETURNING *""",
                (usuario_id, forma_id, categoria_id, valor, descricao, grupo_id),
            )
            conn.commit()
            return dict(cur.fetchone())


def get_ultimos_gastos(usuario_id: int, limit: int = 5):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT g.id, g.valor, g.data,
                          c.nome  AS categoria_nome,
                          fp.nome AS forma_nome
                   FROM gastos g
                   LEFT JOIN categorias c        ON c.id  = g.categoria_id
                   LEFT JOIN formas_pagamento fp ON fp.id = g.forma_pagamento_id
                   WHERE g.usuario_id = %s
                   ORDER BY g.data DESC
                   LIMIT %s""",
                (usuario_id, limit),
            )
            return [dict(r) for r in cur.fetchall()]


def excluir_ultimo_gasto(usuario_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT g.id, g.valor,
                          c.nome  AS categoria_nome,
                          fp.nome AS forma_nome
                   FROM gastos g
                   LEFT JOIN categorias c        ON c.id  = g.categoria_id
                   LEFT JOIN formas_pagamento fp ON fp.id = g.forma_pagamento_id
                   WHERE g.usuario_id = %s
                   ORDER BY g.data DESC
                   LIMIT 1""",
                (usuario_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            gasto = dict(row)
            cur.execute("DELETE FROM gastos WHERE id = %s", (gasto["id"],))
            conn.commit()
            return gasto


def editar_ultimo_gasto_valor(usuario_id: int, novo_valor: float) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM gastos WHERE usuario_id = %s ORDER BY data DESC LIMIT 1",
                (usuario_id,),
            )
            row = cur.fetchone()
            if not row:
                return False
            cur.execute("UPDATE gastos SET valor = %s WHERE id = %s", (novo_valor, row["id"]))
            conn.commit()
            return True


# ---------------------------------------------------------------------------
# Saldo
# ---------------------------------------------------------------------------

def get_saldo_forma(usuario_id: int, forma_id: int):
    """Retorna dict com gasto_mes, limite_mensal, nome. Soma todos os gastos da forma."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT fp.nome,
                          fp.limite_mensal,
                          COALESCE(SUM(g.valor), 0) AS gasto_mes
                   FROM formas_pagamento fp
                   LEFT JOIN gastos g
                     ON g.forma_pagamento_id = fp.id
                    AND DATE_TRUNC('month', g.data) = DATE_TRUNC('month', NOW())
                   WHERE fp.id = %s
                   GROUP BY fp.id, fp.nome, fp.limite_mensal""",
                (forma_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def get_saldo_todas_formas(usuario_id: int):
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    """SELECT fp.id, fp.nome, fp.limite_mensal,
                              COALESCE(SUM(g.valor), 0) AS gasto_mes
                       FROM formas_pagamento fp
                       LEFT JOIN gastos g
                         ON g.forma_pagamento_id = fp.id
                        AND DATE_TRUNC('month', g.data) = DATE_TRUNC('month', NOW())
                       WHERE fp.grupo_id = %s
                       GROUP BY fp.id, fp.nome, fp.limite_mensal
                       ORDER BY fp.nome""",
                    (gid,),
                )
            else:
                cur.execute(
                    """SELECT fp.id, fp.nome, fp.limite_mensal,
                              COALESCE(SUM(g.valor), 0) AS gasto_mes
                       FROM formas_pagamento fp
                       LEFT JOIN gastos g
                         ON g.forma_pagamento_id = fp.id
                        AND DATE_TRUNC('month', g.data) = DATE_TRUNC('month', NOW())
                       WHERE fp.usuario_id = %s AND fp.grupo_id IS NULL
                       GROUP BY fp.id, fp.nome, fp.limite_mensal
                       ORDER BY fp.nome""",
                    (usuario_id,),
                )
            return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Resumo mensal
# ---------------------------------------------------------------------------

def get_resumo_mes(usuario_id: int):
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    """SELECT c.nome AS categoria, fp.nome AS forma, SUM(g.valor) AS total
                       FROM gastos g
                       JOIN categorias c        ON c.id  = g.categoria_id
                       JOIN formas_pagamento fp ON fp.id = g.forma_pagamento_id
                       WHERE fp.grupo_id = %s
                         AND DATE_TRUNC('month', g.data) = DATE_TRUNC('month', NOW())
                       GROUP BY c.nome, fp.nome
                       ORDER BY total DESC""",
                    (gid,),
                )
            else:
                cur.execute(
                    """SELECT c.nome AS categoria, fp.nome AS forma, SUM(g.valor) AS total
                       FROM gastos g
                       JOIN categorias c        ON c.id  = g.categoria_id
                       JOIN formas_pagamento fp ON fp.id = g.forma_pagamento_id
                       WHERE g.usuario_id = %s
                         AND g.grupo_id IS NULL
                         AND DATE_TRUNC('month', g.data) = DATE_TRUNC('month', NOW())
                       GROUP BY c.nome, fp.nome
                       ORDER BY total DESC""",
                    (usuario_id,),
                )
            return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Limite
# ---------------------------------------------------------------------------

def atualizar_limite(usuario_id: int, forma_nome: str, novo_limite: float) -> bool:
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    """UPDATE formas_pagamento SET limite_mensal = %s
                       WHERE grupo_id = %s AND LOWER(nome) LIKE %s RETURNING id""",
                    (novo_limite, gid, f"%{forma_nome.lower()}%"),
                )
            else:
                cur.execute(
                    """UPDATE formas_pagamento SET limite_mensal = %s
                       WHERE usuario_id = %s AND grupo_id IS NULL AND LOWER(nome) LIKE %s RETURNING id""",
                    (novo_limite, usuario_id, f"%{forma_nome.lower()}%"),
                )
            updated = cur.fetchone()
            conn.commit()
            return updated is not None


# ---------------------------------------------------------------------------
# Grupos (contas compartilhadas)
# ---------------------------------------------------------------------------

def get_grupo(grupo_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM grupos WHERE id = %s", (grupo_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def get_membros_grupo(grupo_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM usuarios WHERE grupo_id = %s ORDER BY id", (grupo_id,))
            return [dict(r) for r in cur.fetchall()]


def criar_grupo(usuario_id: int, nome: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO grupos (nome) VALUES (%s) RETURNING *", (nome,))
            grupo = dict(cur.fetchone())
            gid = grupo["id"]
            cur.execute("UPDATE usuarios SET grupo_id = %s WHERE id = %s", (gid, usuario_id))
            cur.execute(
                "UPDATE formas_pagamento SET grupo_id = %s WHERE usuario_id = %s AND grupo_id IS NULL",
                (gid, usuario_id),
            )
            cur.execute(
                "UPDATE gastos SET grupo_id = %s WHERE usuario_id = %s AND grupo_id IS NULL",
                (gid, usuario_id),
            )
            conn.commit()
            return grupo


def adicionar_membro_grupo(grupo_id: int, telefone: str):
    """Retorna (usuario, ja_em_outro_grupo)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM usuarios WHERE telefone = %s", (telefone,))
            row = cur.fetchone()
            if row:
                usuario = dict(row)
                if usuario.get("grupo_id"):
                    return usuario, True
                cur.execute("UPDATE usuarios SET grupo_id = %s WHERE id = %s", (grupo_id, usuario["id"]))
                conn.commit()
                return usuario, False

            cur.execute(
                "INSERT INTO usuarios (nome, telefone, grupo_id) VALUES (%s, %s, %s) RETURNING *",
                (telefone, telefone, grupo_id),
            )
            usuario = dict(cur.fetchone())
            conn.commit()
            return usuario, False


def sair_grupo(usuario_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE usuarios SET grupo_id = NULL WHERE id = %s", (usuario_id,))
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM formas_pagamento WHERE usuario_id = %s AND grupo_id IS NULL",
                (usuario_id,),
            )
            cnt = cur.fetchone()["cnt"]
            if cnt == 0:
                for nome, limite in FORMAS_PADRAO:
                    cur.execute(
                        "INSERT INTO formas_pagamento (usuario_id, nome, limite_mensal) VALUES (%s, %s, %s)",
                        (usuario_id, nome, limite),
                    )
            conn.commit()
