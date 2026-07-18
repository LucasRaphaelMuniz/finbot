"""routes/gastos.py — CRUD de gastos (Fase 4.3, §4.3 do PLANO_EXECUCAO.md)."""

from flask import Blueprint, request, g

from middlewares.ensure_authenticated import ensure_authenticated, requer_grupo
from utils.app_error import AppError
from services.gastos import listar_gastos, criar_gasto, atualizar_gasto, remover_gasto, obter_gasto
from services.parcelamento import excluir_compra_parcelada
from db import get_formas_pagamento

bp = Blueprint("gastos", __name__, url_prefix="/api/gastos")


@bp.route("", methods=["GET"])
@ensure_authenticated
@requer_grupo
def listar():
    return listar_gastos(
        g.usuario_id,
        mes=request.args.get("mes"),
        categoria_id=request.args.get("categoria", type=int),
        membro_id=request.args.get("membro", type=int),
        page=request.args.get("page", default=1, type=int),
        per_page=request.args.get("per_page", default=50, type=int),
    )


@bp.route("", methods=["POST"])
@ensure_authenticated
@requer_grupo
def criar():
    dados = request.get_json(silent=True) or {}
    if any(dados.get(c) is None for c in ("forma_pagamento_id", "categoria_id", "valor")):
        raise AppError(
            "forma_pagamento_id, categoria_id e valor são obrigatórios.", 400, "campos_obrigatorios"
        )

    # dia_fechamento vem da forma escolhida, não do body — mesma regra do bot
    # (handler.py:_registrar_e_confirmar): a competência tem que ser calculada
    # igual não importa se o gasto entrou pelo bot ou pela web.
    forma = next(
        (f for f in get_formas_pagamento(g.usuario_id) if f["id"] == dados["forma_pagamento_id"]),
        None,
    )
    if not forma:
        raise AppError("Forma de pagamento não encontrada.", 404, "forma_nao_encontrada")

    gasto = criar_gasto(
        g.usuario_id, dados["forma_pagamento_id"], dados["categoria_id"],
        float(dados["valor"]), dados.get("descricao", ""),
        dia_fechamento=forma.get("dia_fechamento"),
        dia_vencimento=forma.get("dia_vencimento"),
    )
    return gasto, 201


@bp.route("/<int:gasto_id>", methods=["PUT"])
@ensure_authenticated
@requer_grupo
def atualizar(gasto_id):
    dados = request.get_json(silent=True) or {}
    gasto = atualizar_gasto(g.usuario_id, gasto_id, **dados)
    if not gasto:
        raise AppError("Gasto não encontrado.", 404, "nao_encontrado")
    return gasto


@bp.route("/<int:gasto_id>", methods=["DELETE"])
@ensure_authenticated
@requer_grupo
def remover(gasto_id):
    # ?escopo=compra remove a compra parcelada inteira (todas as parcelas);
    # default ("unico") remove só o gasto/parcela clicado — mesma escolha
    # "esta x inteira" da decisão D3 do bot, aqui como parâmetro em vez de
    # pergunta na conversa.
    gasto_atual = obter_gasto(g.usuario_id, gasto_id)
    if not gasto_atual:
        raise AppError("Gasto não encontrado.", 404, "nao_encontrado")

    escopo = request.args.get("escopo", "unico")
    if escopo == "compra" and gasto_atual.get("compra_parcelada_id"):
        compra = excluir_compra_parcelada(gasto_atual["compra_parcelada_id"])
        return {"removido": "compra", "compra": compra}

    gasto = remover_gasto(g.usuario_id, gasto_id)
    return {"removido": "gasto", "gasto": gasto}
