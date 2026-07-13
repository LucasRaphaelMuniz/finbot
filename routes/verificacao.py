"""routes/verificacao.py — POST /api/verificacao/enviar, /confirmar (Fase B
do AUDITORIA_E_PLANO_CADASTRO.md). Rotas finas — toda a lógica de OTP vive
em services/verificacao.py, conforme padrão CLAUDE.md."""

from flask import Blueprint, request, g

from middlewares.ensure_authenticated import ensure_authenticated
from services.verificacao import enviar_codigo, confirmar_codigo

bp = Blueprint("verificacao", __name__, url_prefix="/api/verificacao")


@bp.route("/enviar", methods=["POST"])
@ensure_authenticated
def enviar():
    dados = request.get_json(silent=True) or {}
    resultado = enviar_codigo(g.auth_user_id, dados.get("telefone", ""))
    return resultado, 200


@bp.route("/confirmar", methods=["POST"])
@ensure_authenticated
def confirmar():
    dados = request.get_json(silent=True) or {}
    resultado = confirmar_codigo(g.auth_user_id, dados.get("telefone", ""), dados.get("codigo", ""))
    return resultado, 200
