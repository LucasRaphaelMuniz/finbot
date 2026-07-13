"""routes/resumo.py — GET /api/resumo?mes= (Fase 4.3, agregados p/ dashboard 5.2)."""

from flask import Blueprint, request, g

from middlewares.ensure_authenticated import ensure_authenticated, requer_grupo
from services.resumo import resumo_mensal

bp = Blueprint("resumo", __name__, url_prefix="/api/resumo")


@bp.route("", methods=["GET"])
@ensure_authenticated
@requer_grupo
def obter():
    return resumo_mensal(g.usuario_id, mes=request.args.get("mes"))
