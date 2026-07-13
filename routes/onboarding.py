"""routes/onboarding.py — POST /api/onboarding (Fase 4.3)."""

from flask import Blueprint, request, g

from middlewares.ensure_authenticated import ensure_authenticated
from services.onboarding import completar_onboarding

bp = Blueprint("onboarding", __name__, url_prefix="/api/onboarding")


@bp.route("", methods=["POST"])
@ensure_authenticated
def criar():
    dados = request.get_json(silent=True) or {}
    usuario = completar_onboarding(
        auth_user_id=g.auth_user_id,
        nome=dados.get("nome") or (g.auth_email or "").split("@")[0],
        nome_grupo=dados.get("nome_grupo", ""),
        telefone=dados.get("telefone", ""),
    )
    return usuario, 201
