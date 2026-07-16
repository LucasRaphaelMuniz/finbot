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
    """
    Retorna as categorias globais + as customizadas do grupo do usuário (se
    houver), cada uma já com o campo `ativo` calculado (migração 016):

    - Customizada (grupo_id do próprio grupo): usa a coluna categorias.ativo
      direto — a linha já pertence só a esse grupo.
    - Padrão (grupo_id NULL): a coluna categorias.ativo NUNCA é usada aqui —
      é compartilhada por todos os grupos do SaaS. `ativo` vira `true` a
      menos que exista uma linha em categorias_ocultas pra este grupo
      específico (grupo escondeu essa categoria padrão só pra si).
    """
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    """
                    SELECT c.*,
                           CASE WHEN c.grupo_id IS NULL THEN (o.categoria_id IS NULL)
                                ELSE c.ativo END AS ativo
                    FROM categorias c
                    LEFT JOIN categorias_ocultas o
                           ON o.categoria_id = c.id AND o.grupo_id = %s
                    WHERE c.grupo_id IS NULL OR c.grupo_id = %s
                    ORDER BY c.nome
                    """,
                    (gid, gid),
                )
            else:
                # Sem grupo não há onde guardar categoria_oculta (a tabela
                # exige grupo_id) — pra esse caso, categoria padrão é sempre
                # ativa, sem exceção possível.
                cur.execute(
                    "SELECT *, true AS ativo FROM categorias WHERE grupo_id IS NULL ORDER BY nome",
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
    categorias globais nunca somem, grupo só as oculta via
    alternar_categoria_ativa)."""
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


def alternar_categoria_ativa(usuario_id: int, categoria_id: int, ativo: bool) -> dict | None:
    """
    Ativa/desativa uma categoria pra exibição no grupo do usuário (migração
    016). Não apaga nada — só controla se ela aparece pra escolha em novo
    gasto (CategoriaSelect no front filtra por esse campo); gastos antigos
    lançados com ela continuam normais.

    Padrão (grupo_id NULL): NUNCA escreve na linha compartilhada — grava
    em categorias_ocultas, escopado só a este grupo (ver get_categorias).
    Customizada do próprio grupo: grava direto em categorias.ativo.
    Customizada de OUTRO grupo: recusa (retorna None), mesma regra de posse
    das demais funções por-id desta service.
    """
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        if not gid:
            return None
        with conn.cursor() as cur:
            cur.execute("SELECT grupo_id FROM categorias WHERE id = %s", (categoria_id,))
            categoria = cur.fetchone()
            if not categoria:
                return None

            if categoria["grupo_id"] is None:
                if ativo:
                    cur.execute(
                        "DELETE FROM categorias_ocultas WHERE grupo_id = %s AND categoria_id = %s",
                        (gid, categoria_id),
                    )
                else:
                    cur.execute(
                        "INSERT INTO categorias_ocultas (grupo_id, categoria_id) VALUES (%s, %s) "
                        "ON CONFLICT (grupo_id, categoria_id) DO NOTHING",
                        (gid, categoria_id),
                    )
            elif categoria["grupo_id"] == gid:
                cur.execute(
                    "UPDATE categorias SET ativo = %s WHERE id = %s AND grupo_id = %s",
                    (ativo, categoria_id, gid),
                )
            else:
                return None

            conn.commit()

    # Reconsulta em vez de duplicar aqui o CASE WHEN de get_categorias.
    return next((c for c in get_categorias(usuario_id) if c["id"] == categoria_id), None)


def categoria_pertence_ao_usuario(usuario_id: int, categoria_id: int) -> bool:
    """
    Fase D3 do AUDITORIA_E_PLANO_CADASTRO.md — usado por services/gastos.py
    antes de gravar/atualizar um gasto. Sem essa checagem, POST/PUT
    /api/gastos aceitava qualquer categoria_id existente no banco, mesmo
    customizada de OUTRO grupo (cross-tenant fraco: dava pra "usar" uma
    categoria que não é sua, embora não desse pra ler/editar o resto do
    grupo alheio). Categoria global (grupo_id IS NULL) sempre vale, pra
    qualquer usuário — customizada só vale pro grupo dono dela.
    """
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM categorias WHERE id = %s AND (grupo_id IS NULL OR grupo_id = %s)",
                (categoria_id, gid),
            )
            return cur.fetchone() is not None
