"""routes/planos.py — GET /api/planos, GET /api/assinatura (Fase 4.3)."""

from flask import Blueprint, g

from middlewares.ensure_authenticated import ensure_authenticated, requer_grupo
from services.planos import listar_planos, obter_assinatura

bp = Blueprint("planos", __name__, url_prefix="/api")


@bp.route("/planos", methods=["GET"])
@ensure_authenticated
def planos():
    # Sem @requer_grupo: a tela /planos (Fase 6) precisa mostrar os planos
    # disponíveis mesmo pra quem ainda está no meio do onboarding.
    return {"itens": listar_planos()}


@bp.route("/assinatura", methods=["GET"])
@ensure_authenticated
@requer_grupo
def assinatura():
    dados = obter_assinatura(g.usuario_id)
    return dados or {"status": "sem_assinatura"}
