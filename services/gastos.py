"""
services/gastos.py — CRUD web de gastos (Fase 4.3, contrato §4.3 do
PLANO_EXECUCAO.md: GET /api/gastos?mes=&categoria=&membro=, POST,
PUT/DELETE /api/gastos/:id). O bot (handler.py) tem seu próprio fluxo
conversacional de registro, que já usa db.registrar_gasto/get_ultimos_gastos
etc. — este módulo é a camada REST equivalente, sem sessão/vai-e-vem.
"""

from db import get_conn, _get_grupo_id, registrar_gasto
from services.categorias import categoria_pertence_ao_usuario
from utils.app_error import AppError


def listar_gastos(usuario_id: int, mes: str = None, categoria_id: int = None,
                   membro_id: int = None, page: int = 1, per_page: int = 50) -> dict:
    """
    mes: "YYYY-MM" — filtra por competência (não por data, mesma decisão da
    Fase 3.2/P2: gasto de cartão perto do fechamento pode "pertencer" ao mês
    seguinte). Retorna {"itens": [...], "total": N, "page": ..., "per_page": ...}.
    """
    page = max(1, page)
    per_page = min(max(1, per_page), 200)

    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            condicoes, params = [], []

            if gid:
                condicoes.append("g.grupo_id = %s")
                params.append(gid)
            else:
                condicoes.append("g.usuario_id = %s AND g.grupo_id IS NULL")
                params.append(usuario_id)

            if mes:
                condicoes.append("DATE_TRUNC('month', g.competencia) = DATE_TRUNC('month', %s::date)")
                params.append(f"{mes}-01")
            if categoria_id:
                condicoes.append("g.categoria_id = %s")
                params.append(categoria_id)
            if membro_id:
                condicoes.append("g.usuario_id = %s")
                params.append(membro_id)

            where = " AND ".join(condicoes)

            cur.execute(f"SELECT COUNT(*) AS total FROM gastos g WHERE {where}", params)
            total = cur.fetchone()["total"]

            offset = (page - 1) * per_page
            cur.execute(
                f"""SELECT g.*, c.nome AS categoria_nome, fp.nome AS forma_nome,
                           u.nome AS membro_nome
                    FROM gastos g
                    LEFT JOIN categorias c        ON c.id  = g.categoria_id
                    LEFT JOIN formas_pagamento fp ON fp.id = g.forma_pagamento_id
                    LEFT JOIN usuarios u          ON u.id  = g.usuario_id
                    WHERE {where}
                    ORDER BY g.data DESC
                    LIMIT %s OFFSET %s""",
                params + [per_page, offset],
            )
            itens = [dict(r) for r in cur.fetchall()]

    return {"itens": itens, "total": total, "page": page, "per_page": per_page}


def criar_gasto(usuario_id: int, forma_pagamento_id: int, categoria_id: int,
                 valor: float, descricao: str = "", dia_fechamento: int = None) -> dict:
    # Fase D3 do AUDITORIA_E_PLANO_CADASTRO.md — recusa categoria que não é
    # global nem do próprio grupo, antes de gravar (ver services/categorias.py).
    if not categoria_pertence_ao_usuario(usuario_id, categoria_id):
        raise AppError("Categoria inválida.", 400, "categoria_invalida")

    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
    return registrar_gasto(
        usuario_id, forma_pagamento_id, categoria_id, valor, descricao,
        grupo_id=gid, dia_fechamento=dia_fechamento,
    )


_CAMPOS_EDITAVEIS = ("valor", "descricao", "categoria_id", "forma_pagamento_id")


def atualizar_gasto(usuario_id: int, gasto_id: int, **campos) -> dict | None:
    # Fase D3 — só valida se categoria_id veio no PUT (campo opcional aqui;
    # ausência não deve travar edição de valor/descrição/forma sozinhos).
    if campos.get("categoria_id") is not None and not categoria_pertence_ao_usuario(
        usuario_id, campos["categoria_id"]
    ):
        raise AppError("Categoria inválida.", 400, "categoria_invalida")

    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        sets, params = [], []
        for chave in _CAMPOS_EDITAVEIS:
            if campos.get(chave) is not None:
                sets.append(f"{chave} = %s")
                params.append(campos[chave])
        if not sets:
            return None

        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    f"UPDATE gastos SET {', '.join(sets)} WHERE id = %s AND grupo_id = %s RETURNING *",
                    params + [gasto_id, gid],
                )
            else:
                cur.execute(
                    f"UPDATE gastos SET {', '.join(sets)} "
                    "WHERE id = %s AND usuario_id = %s AND grupo_id IS NULL RETURNING *",
                    params + [gasto_id, usuario_id],
                )
            row = cur.fetchone()
            conn.commit()
            return dict(row) if row else None


def obter_gasto(usuario_id: int, gasto_id: int) -> dict | None:
    """Peek (sem excluir) — usado pela rota DELETE pra decidir, antes de
    mexer no banco, se é uma parcela (e então perguntar/aceitar o parâmetro
    ?escopo=compra x unico, mesma decisão D3 do bot) ou um gasto avulso."""
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute("SELECT * FROM gastos WHERE id = %s AND grupo_id = %s", (gasto_id, gid))
            else:
                cur.execute(
                    "SELECT * FROM gastos WHERE id = %s AND usuario_id = %s AND grupo_id IS NULL",
                    (gasto_id, usuario_id),
                )
            row = cur.fetchone()
            return dict(row) if row else None


def remover_gasto(usuario_id: int, gasto_id: int) -> dict | None:
    """
    Retorna o gasto removido, ou None se não encontrado/não pertence ao
    usuário/grupo. Se `compra_parcelada_id` estiver presente, quem chama
    (routes/gastos.py) decide entre excluir só esta parcela (esta função) ou
    a compra inteira (services.parcelamento.excluir_compra_parcelada) — a
    mesma escolha "esta x inteira" da decisão D3 do bot, só que aqui como
    dois endpoints/parâmetros REST em vez de uma pergunta na conversa.
    """
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute("SELECT * FROM gastos WHERE id = %s AND grupo_id = %s", (gasto_id, gid))
            else:
                cur.execute(
                    "SELECT * FROM gastos WHERE id = %s AND usuario_id = %s AND grupo_id IS NULL",
                    (gasto_id, usuario_id),
                )
            row = cur.fetchone()
            if not row:
                return None
            gasto = dict(row)
            cur.execute("DELETE FROM gastos WHERE id = %s", (gasto_id,))
            conn.commit()
            return gasto
