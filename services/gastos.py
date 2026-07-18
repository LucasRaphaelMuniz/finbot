"""
services/gastos.py — CRUD web de gastos (Fase 4.3, contrato §4.3 do
PLANO_EXECUCAO.md: GET /api/gastos?mes=&categoria=&membro=, POST,
PUT/DELETE /api/gastos/:id). O bot (handler.py) tem seu próprio fluxo
conversacional de registro, que já usa db.registrar_gasto/get_ultimos_gastos
etc. — este módulo é a camada REST equivalente, sem sessão/vai-e-vem.
"""

from datetime import date

from db import get_conn, _get_grupo_id, registrar_gasto
from services.categorias import categoria_pertence_ao_usuario
from services.competencia import calcular_competencia
from services.despesas_fixas import _dia_efetivo
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

            # Pedido do Lucas (16/07/2026): ao navegar pra um mês futuro em
            # Lançamentos, custos fixos que ainda não foram lançados pelo
            # cron (jobs/lancar_fixas.py) não aparecem em `gastos` — a
            # pessoa via o mês "vazio" mesmo tendo despesa fixa cadastrada
            # pra ele. `_projetar_despesas_fixas` preenche isso com linhas
            # sintéticas (não gravadas em `gastos`, `projetado: True`) só
            # quando `mes` filtra um único mês específico — não faz sentido
            # numa listagem sem filtro de competência.
            if mes:
                itens = itens + _projetar_despesas_fixas(conn, gid, usuario_id, mes, itens)

    return {"itens": itens, "total": total, "page": page, "per_page": per_page}


def _projetar_despesas_fixas(conn, gid: int | None, usuario_id: int, mes: str, itens_reais: list[dict]) -> list[dict]:
    """
    Gera linhas "projetadas" (não persistidas em `gastos`) para despesas
    fixas ativas que, pela regra de competência (mesma `calcular_competencia`
    usada pelo lançador — services/despesas_fixas.py), cairiam no mês `mes`
    mas ainda não têm um gasto real lançado ali (cron ainda não rodou pra
    aquele mês, ou o mês é futuro).

    Só projeta mês atual pra frente (não polui mês passado com "buracos" do
    cron — isso seria sinal de outro problema, não de projeção legítima).

    Cada fixa é testada contra TRÊS candidatos de data de lançamento (mês
    alvo e os dois meses anteriores a ele) porque `calcular_competencia`
    (migração 019/020) pode empurrar a competência em até 2 meses à frente
    da data real de lançamento: 1 mês se ela cair depois do dia_fechamento
    do cartão, mais 1 mês pro mês de vencimento da fatura — a data real de
    lançamento pode cair até 2 meses antes da competência resultante.
    """
    ano, mes_num = (int(p) for p in mes.split("-"))
    competencia_alvo = date(ano, mes_num, 1)

    hoje = date.today()
    if competencia_alvo < hoje.replace(day=1):
        return []

    ja_lancadas = {i["despesa_fixa_id"] for i in itens_reais if i.get("despesa_fixa_id")}

    with conn.cursor() as cur:
        if gid:
            cur.execute(
                """SELECT df.*, c.nome AS categoria_nome, fp.nome AS forma_nome,
                          fp.dia_fechamento, fp.dia_vencimento, u.nome AS membro_nome
                   FROM despesas_fixas df
                   LEFT JOIN categorias c        ON c.id  = df.categoria_id
                   LEFT JOIN formas_pagamento fp ON fp.id = df.forma_pagamento_id
                   LEFT JOIN usuarios u          ON u.id  = df.usuario_id
                   WHERE df.grupo_id = %s AND df.ativa = TRUE""",
                (gid,),
            )
        else:
            cur.execute(
                """SELECT df.*, c.nome AS categoria_nome, fp.nome AS forma_nome,
                          fp.dia_fechamento, fp.dia_vencimento, u.nome AS membro_nome
                   FROM despesas_fixas df
                   LEFT JOIN categorias c        ON c.id  = df.categoria_id
                   LEFT JOIN formas_pagamento fp ON fp.id = df.forma_pagamento_id
                   LEFT JOIN usuarios u          ON u.id  = df.usuario_id
                   WHERE df.usuario_id = %s AND df.grupo_id IS NULL AND df.ativa = TRUE""",
                (usuario_id,),
            )
        fixas = [dict(r) for r in cur.fetchall()]

    def _mes_anterior(ano: int, mes_num: int) -> tuple[int, int]:
        return (ano - 1, 12) if mes_num == 1 else (ano, mes_num - 1)

    projetados = []
    for fixa in fixas:
        if fixa["id"] in ja_lancadas:
            continue  # já lançada de verdade nesse mês — não duplica

        candidatos = [(ano, mes_num)]
        mes_1_atras = _mes_anterior(ano, mes_num)
        candidatos.append(mes_1_atras)
        candidatos.append(_mes_anterior(*mes_1_atras))

        data_projetada = None
        for ano_c, mes_c in candidatos:
            dia_c = _dia_efetivo(fixa["dia_lancamento"], ano_c, mes_c)
            candidata = date(ano_c, mes_c, dia_c)
            if calcular_competencia(candidata, fixa.get("dia_fechamento"), fixa.get("dia_vencimento")) == competencia_alvo:
                data_projetada = candidata
                break

        if not data_projetada:
            continue  # não deveria acontecer, mas não trava a listagem por isso

        projetados.append({
            "id": f"projetado-fixa-{fixa['id']}-{mes}",
            "data": data_projetada.isoformat(),
            "competencia": competencia_alvo.isoformat(),
            "descricao": fixa["descricao"],
            "categoria_id": fixa["categoria_id"],
            "categoria_nome": fixa["categoria_nome"],
            "forma_pagamento_id": fixa["forma_pagamento_id"],
            "forma_nome": fixa["forma_nome"],
            "membro_nome": fixa["membro_nome"],
            "valor": fixa["valor"],
            "compra_parcelada_id": None,
            "despesa_fixa_id": fixa["id"],
            "projetado": True,
        })

    return projetados


def criar_gasto(usuario_id: int, forma_pagamento_id: int, categoria_id: int,
                 valor: float, descricao: str = "", dia_fechamento: int = None,
                 dia_vencimento: int = None) -> dict:
    # Fase D3 do AUDITORIA_E_PLANO_CADASTRO.md — recusa categoria que não é
    # global nem do próprio grupo, antes de gravar (ver services/categorias.py).
    if not categoria_pertence_ao_usuario(usuario_id, categoria_id):
        raise AppError("Categoria inválida.", 400, "categoria_invalida")

    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
    return registrar_gasto(
        usuario_id, forma_pagamento_id, categoria_id, valor, descricao,
        grupo_id=gid, dia_fechamento=dia_fechamento, dia_vencimento=dia_vencimento,
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
