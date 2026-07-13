"""routes/grupo.py — GET/PUT /api/grupo, POST/PUT/DELETE /api/grupo/membros (Fase 4.3)."""

from flask import Blueprint, request, g

from middlewares.ensure_authenticated import ensure_authenticated, requer_grupo
from utils.app_error import AppError
from services.grupos import (
    get_grupo_completo,
    atualizar_nome_grupo,
    adicionar_membro,
    atualizar_membro,
    remover_membro,
)

bp = Blueprint("grupo", __name__, url_prefix="/api/grupo")


@bp.route("", methods=["GET"])
@ensure_authenticated
@requer_grupo
def obter():
    # Este é o endpoint que finbot-web/(app)/layout.jsx chama pra decidir se
    # mostra CompletarCadastro (404 "sem_grupo", levantado pelo próprio
    # decorator @requer_grupo) ou o dashboard normal.
    return get_grupo_completo(g.usuario_id)


@bp.route("", methods=["PUT"])
@ensure_authenticated
@requer_grupo
def atualizar():
    dados = request.get_json(silent=True) or {}
    nome = (dados.get("nome") or "").strip()
    if not nome:
        raise AppError("nome é obrigatório.", 400, "campos_obrigatorios")
    return atualizar_nome_grupo(g.usuario_id, nome)


@bp.route("/membros", methods=["POST"])
@ensure_authenticated
@requer_grupo
def adicionar():
    dados = request.get_json(silent=True) or {}
    telefone = (dados.get("telefone") or "").strip()
    if not telefone:
        raise AppError("telefone é obrigatório.", 400, "campos_obrigatorios")
    membro, ja_em_grupo = adicionar_membro(g.usuario_id, telefone)
    if ja_em_grupo:
        raise AppError("Esse número já pertence a um grupo (talvez o seu).", 400, "membro_ja_vinculado")
    return membro, 201


@bp.route("/membros/<int:membro_id>", methods=["PUT"])
@ensure_authenticated
@requer_grupo
def atualizar_membro_rota(membro_id):
    dados = request.get_json(silent=True) or {}
    membro = atualizar_membro(g.usuario_id, membro_id, nome=dados.get("nome"), telefone=dados.get("telefone"))
    if not membro:
        raise AppError("Membro não encontrado no seu grupo (ou nenhum campo pra atualizar).", 404, "nao_encontrado")
    return membro


@bp.route("/membros/<int:membro_id>", methods=["DELETE"])
@ensure_authenticated
@requer_grupo
def remover_membro_rota(membro_id):
    if not remover_membro(g.usuario_id, membro_id):
        raise AppError("Membro não encontrado no seu grupo.", 404, "nao_encontrado")
    return {"removido": True}
