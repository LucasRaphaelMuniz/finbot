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


# ---------------------------------------------------------------------------
# Usuários
# ---------------------------------------------------------------------------

FORMAS_PADRAO = [
    ("Cartão",       3000.00),
    ("Pix/Dinheiro", 1500.00),
    ("Ticket",        600.00),
]

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
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM formas_pagamento WHERE usuario_id = %s ORDER BY nome",
                (usuario_id,),
            )
            return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Gastos
# ---------------------------------------------------------------------------

def registrar_gasto(usuario_id: int, forma_id: int, categoria_id: int,
                    valor: float, descricao: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO gastos
                       (usuario_id, forma_pagamento_id, categoria_id, valor, descricao)
                   VALUES (%s, %s, %s, %s, %s)
                   RETURNING *""",
                (usuario_id, forma_id, categoria_id, valor, descricao),
            )
            conn.commit()
            return dict(cur.fetchone())


# ---------------------------------------------------------------------------
# Saldo
# ---------------------------------------------------------------------------

def get_saldo_forma(usuario_id: int, forma_id: int):
    """Retorna dict com gasto_mes, limite_mensal, nome."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT fp.nome,
                          fp.limite_mensal,
                          COALESCE(SUM(g.valor), 0) AS gasto_mes
                   FROM formas_pagamento fp
                   LEFT JOIN gastos g
                     ON g.forma_pagamento_id = fp.id
                    AND g.usuario_id = %s
                    AND DATE_TRUNC('month', g.data) = DATE_TRUNC('month', NOW())
                   WHERE fp.id = %s
                     AND fp.usuario_id = %s
                   GROUP BY fp.id, fp.nome, fp.limite_mensal""",
                (usuario_id, forma_id, usuario_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def get_saldo_todas_formas(usuario_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT fp.id,
                          fp.nome,
                          fp.limite_mensal,
                          COALESCE(SUM(g.valor), 0) AS gasto_mes
                   FROM formas_pagamento fp
                   LEFT JOIN gastos g
                     ON g.forma_pagamento_id = fp.id
                    AND g.usuario_id = %s
                    AND DATE_TRUNC('month', g.data) = DATE_TRUNC('month', NOW())
                   WHERE fp.usuario_id = %s
                   GROUP BY fp.id, fp.nome, fp.limite_mensal
                   ORDER BY fp.nome""",
                (usuario_id, usuario_id),
            )
            return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Resumo mensal
# ---------------------------------------------------------------------------

def get_resumo_mes(usuario_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT c.nome  AS categoria,
                          fp.nome AS forma,
                          SUM(g.valor) AS total
                   FROM gastos g
                   JOIN categorias c        ON c.id  = g.categoria_id
                   JOIN formas_pagamento fp ON fp.id = g.forma_pagamento_id
                   WHERE g.usuario_id = %s
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
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE formas_pagamento
                   SET limite_mensal = %s
                   WHERE usuario_id = %s
                     AND LOWER(nome) LIKE %s
                   RETURNING id""",
                (novo_limite, usuario_id, f"%{forma_nome.lower()}%"),
            )
            updated = cur.fetchone()
            conn.commit()
            return updated is not None
