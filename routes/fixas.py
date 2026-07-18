"""routes/fixas.py — CRUD de despesas fixas (Fase 4.3)."""

from flask import Blueprint, request, g

from middlewares.ensure_authenticated import ensure_authenticated, requer_grupo
from utils.app_error import AppError
from services.despesas_fixas import (
    get_despesas_fixas,
    criar_despesa_fixa,
    atualizar_despesa_fixa,
    desativar_despesa_fixa_por_id,
)

bp = Blueprint("fixas", __name__, url_prefix="/api/fixas")


@bp.route("", methods=["GET"])
@ensure_authenticated
@requer_grupo
def listar():
    return {"itens": get_despesas_fixas(g.usuario_id)}


@bp.route("", methods=["POST"])
@ensure_authenticated
@requer_grupo
def criar():
    dados = request.get_json(silent=True) or {}
    obrigatorios = ("descricao", "valor", "dia_lancamento")
    if any(dados.get(c) is None for c in obrigatorios):
        raise AppError(
            "descricao, valor e dia_lancamento são obrigatórios.", 400, "campos_obrigatorios"
        )
    fixa = criar_despesa_fixa(
        g.usuario_id, dados["descricao"], float(dados["valor"]), int(dados["dia_lancamento"]),
        categoria_id=dados.get("categoria_id"), forma_pagamento_id=dados.get("forma_pagamento_id"),
        parcelas_total=dados.get("parcelas_total"),
    )
    return fixa, 201


@bp.route("/<int:fixa_id>", methods=["PUT"])
@ensure_authenticated
@requer_grupo
def atualizar(fixa_id):
    dados = request.get_json(silent=True) or {}
    fixa = atualizar_despesa_fixa(
        g.usuario_id, fixa_id,
        descricao=dados.get("descricao"), valor=dados.get("valor"),
        dia_lancamento=dados.get("dia_lancamento"), categoria_id=dados.get("categoria_id"),
        forma_pagamento_id=dados.get("forma_pagamento_id"),
        parcelas_total=dados.get("parcelas_total"),
        aplicar_a_partir=dados.get("aplicar_a_partir", "imediato"),
    )
    if not fixa:
        raise AppError("Despesa fixa não encontrada (ou nenhum campo pra atualizar).", 404, "nao_encontrado")
    return fixa


# NOTA: o endpoint POST /:id/confirmar (botão "Confirmar" das linhas
# "previsto") foi REMOVIDO em 18/07/2026 a pedido do Lucas — custo fixo não
# pode exigir ritual manual. O gap que ele cobria (lançador só rodava no
# dia exato) foi resolvido na raiz: catch-up automático em
# lancar_despesas_fixas_do_mes (>= em vez de ==) + execução na subida do
# processo (app.py).


@bp.route("/<int:fixa_id>", methods=["DELETE"])
@ensure_authenticated
@requer_grupo
def remover(fixa_id):
    # Soft-delete (ativa=FALSE), não DELETE de verdade — mesma razão do bot:
    # gastos.despesa_fixa_id não tem ON DELETE CASCADE/SET NULL (migração 004).
    if not desativar_despesa_fixa_por_id(g.usuario_id, fixa_id):
        raise AppError("Despesa fixa não encontrada.", 404, "nao_encontrado")
    return {"desativada": True}
