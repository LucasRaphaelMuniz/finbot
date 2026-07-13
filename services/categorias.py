"""
services/categorias.py — categorias por grupo (Fase 3.1 do PLANO_EXECUCAO.md).

Modelo (migração 001): `categorias.grupo_id IS NULL` = categoria padrão global,
visível para todo mundo. `grupo_id` preenchido = categoria customizada, visível
só para aquele grupo. Categorias globais nunca são removidas (G5 do
PLANO_EXECUCAO.md) — um grupo só acrescenta as suas por cima do catálogo padrão.

Decisão que vale destacar: a migração 001 não adicionou `usuario_id` em
`categorias` (só `grupo_id`) — ela segue exatamente o schema já aprovado no
plano. Consequência: usuário sem grupo (conta individual) não tem onde guardar
uma categoria customizada seguindo esse schema; `adicionar_categoria` recusa
explicitamente nesse caso (ver `_cmd_categoria` em handler.py) em vez de
inserir com grupo_id NULL, que corromperia o catálogo global compartilhado
por todos os usuários. Se isso for uma limitação real pro Lucas, a correção é
uma nova migração adicionando `usuario_id` — não fiz isso por conta própria
por estar fora do que foi aprovado na Fase 2.
"""

from db import get_conn, _get_grupo_id


def get_categorias(usuario_id: int) -> list[dict]:
    """Retorna as categorias globais + as customizadas do grupo do usuário (se houver)."""
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    "SELECT * FROM categorias WHERE grupo_id IS NULL OR grupo_id = %s ORDER BY nome",
                    (gid,),
                )
            else:
                cur.execute(
                    "SELECT * FROM categorias WHERE grupo_id IS NULL ORDER BY nome",
                )
            return [dict(r) for r in cur.fetchall()]


def adicionar_categoria(usuario_id: int, nome: str) -> dict | None:
    """
    Cria categoria customizada para o grupo do usuário.
    Retorna None se: usuário não tem grupo, nome vazio, ou já existe categoria
    com esse nome (padrão ou já cadastrada no grupo).
    """
    nome = nome.strip()
    if not nome:
        return None

    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        if not gid:
            return None

        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM categorias "
                "WHERE (grupo_id IS NULL OR grupo_id = %s) AND LOWER(nome) = LOWER(%s)",
                (gid, nome),
            )
            if cur.fetchone():
                return None

            cur.execute(
                "INSERT INTO categorias (nome, grupo_id) VALUES (%s, %s) RETURNING *",
                (nome, gid),
            )
            conn.commit()
            return dict(cur.fetchone())


def remover_categoria(usuario_id: int, nome: str) -> bool:
    """Remove categoria customizada do grupo. Nunca remove categoria global (G5)."""
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        if not gid:
            return False

        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM categorias WHERE grupo_id = %s AND LOWER(nome) LIKE %s RETURNING id",
                (gid, f"%{nome.lower()}%"),
            )
            deleted = cur.fetchone()
            conn.commit()
            return deleted is not None



# ---------------------------------------------------------------------------
# Operações por id (Fase 4.3 — API web, PUT/DELETE /api/categorias/:id)
#
# As funções acima (por nome, fuzzy) servem o bot, onde o usuário digita
# "categoria remover Assinaturas" sem saber nenhum id. Na web o front já tem
# o id exato da linha clicada na tabela — criar uma versão por id em vez de
# forçar essas rotas a squeezar um id num fluxo de busca por nome.
# ---------------------------------------------------------------------------

def atualizar_categoria(usuario_id: int, categoria_id: int, nome: str) -> dict | None:
    """Só edita categoria CUSTOMIZADA do próprio grupo — nunca uma global (G5)."""
    nome = (nome or "").strip()
    if not nome:
        return None
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        if not gid:
            return None
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE categorias SET nome = %s WHERE id = %s AND grupo_id = %s RETURNING *",
                (nome, categoria_id, gid),
            )
            row = cur.fetchone()
            conn.commit()
            return dict(row) if row else None


def remover_categoria_por_id(usuario_id: int, categoria_id: int) -> bool:
    """Só remove categoria CUSTOMIZADA do próprio grupo — nunca uma global (G5:
    categorias globais nunca somem, grupo só as oculta; ocultar não está
    implementado ainda, ver nota em routes/categorias.py)."""
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        if not gid:
            return False
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM categorias WHERE id = %s AND grupo_id = %s RETURNING id",
                (categoria_id, gid),
            )
            deleted = cur.fetchone()
            conn.commit()
            return deleted is not None
