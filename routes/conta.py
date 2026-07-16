"""routes/conta.py — DELETE /api/conta (Fase 5.6, reescrita na Fase 7.5 /
LGPD, senha validada server-side na Fase D1). Sem @requer_grupo de
propósito: contas individuais (sem grupo, ver services/conta.py) também
precisam poder se excluir — @requer_grupo bloquearia esse caso com 404
"sem_grupo" antes mesmo de chegar aqui."""

from flask import Blueprint, request, g

from middlewares.ensure_authenticated import ensure_authenticated
from services.conta import excluir_conta, get_meu_status, marcar_tutorial_visto, atualizar_tema
from utils.app_error import AppError

bp = Blueprint("conta", __name__, url_prefix="/api/conta")


@bp.route("", methods=["DELETE"])
@ensure_authenticated
def excluir():
    if not g.usuario_id:
        raise AppError("Cadastro ainda não concluído — nada para excluir.", 404, "sem_grupo")
    dados = request.get_json(silent=True) or {}
    resultado = excluir_conta(g.usuario_id, g.auth_email, dados.get("senha", ""))
    return {"excluida": True, **resultado}


@bp.route("/eu", methods=["GET"])
@ensure_authenticated
def eu():
    """Fase C — endpoint leve consultado pelo TourPrimeiroLogin (finbot-web)
    ao montar o layout, sem precisar buscar o grupo inteiro só pra saber se
    a pessoa já viu o tutorial."""
    if not g.usuario_id:
        raise AppError("Cadastro ainda não concluído.", 404, "sem_grupo")
    return get_meu_status(g.usuario_id)


@bp.route("/tutorial-visto", methods=["POST"])
@ensure_authenticated
def tutorial_visto():
    if not g.usuario_id:
        raise AppError("Cadastro ainda não concluído.", 404, "sem_grupo")
    dados = request.get_json(silent=True) or {}
    return marcar_tutorial_visto(g.usuario_id, dados.get("visto", True))


@bp.route("/tema", methods=["PUT"])
@ensure_authenticated
def tema():
    # Sem @requer_grupo de propósito — mesma razão de excluir(): conta
    # individual (ainda sem grupo) também tem tema.
    if not g.usuario_id:
        raise AppError("Cadastro ainda não concluído.", 404, "sem_grupo")
    dados = request.get_json(silent=True) or {}
    return atualizar_tema(g.usuario_id, dados.get("tema", ""))
