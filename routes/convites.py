"""routes/convites.py — GET/POST /api/convites, POST /api/convites/aceitar (Fase 4.3)."""

from flask import Blueprint, request, g

from middlewares.ensure_authenticated import ensure_authenticated, requer_grupo
from services.convites import gerar_convite, listar_convites, aceitar_convite

bp = Blueprint("convites", __name__, url_prefix="/api/convites")


@bp.route("", methods=["GET"])
@ensure_authenticated
@requer_grupo
def listar():
    return {"itens": listar_convites(g.usuario_id)}


@bp.route("", methods=["POST"])
@ensure_authenticated
@requer_grupo
def criar():
    dados = request.get_json(silent=True) or {}
    convite = gerar_convite(g.usuario_id, telefone=dados.get("telefone"))
    return convite, 201


@bp.route("/aceitar", methods=["POST"])
@ensure_authenticated
def aceitar():
    # Sem @requer_grupo de propósito: esta rota é o que RESOLVE a falta de
    # grupo pro convidado (ver services/convites.py:aceitar_convite) — exigir
    # grupo aqui criaria uma dependência circular.
    dados = request.get_json(silent=True) or {}
    usuario = aceitar_convite(
        auth_user_id=g.auth_user_id,
        nome=dados.get("nome") or (g.auth_email or "").split("@")[0],
        codigo=dados.get("codigo", ""),
        telefone=dados.get("telefone"),
    )
    return usuario, 200
