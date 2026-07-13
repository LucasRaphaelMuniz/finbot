"""
routes/importacao.py — POST /api/importacao/upload, POST /api/importacao/confirmar,
DELETE /api/importacao/:id (Fase 5.3 do PLANO_EXECUCAO.md).

Único blueprint da API que recebe multipart/form-data (upload de arquivo)
em vez de JSON — os outros usam request.get_json().
"""

from flask import Blueprint, request, g

from middlewares.ensure_authenticated import ensure_authenticated, requer_grupo
from utils.app_error import AppError
from services.importacao import montar_preview, confirmar_importacao, remover_importacao

bp = Blueprint("importacao", __name__, url_prefix="/api/importacao")


@bp.route("/upload", methods=["POST"])
@ensure_authenticated
@requer_grupo
def upload():
    arquivo = request.files.get("arquivo")
    forma_pagamento_id = request.form.get("forma_pagamento_id", type=int)
    if not arquivo or not forma_pagamento_id:
        raise AppError("Envie o arquivo e a forma de pagamento.", 400, "campos_obrigatorios")

    conteudo = arquivo.read()
    return montar_preview(g.usuario_id, forma_pagamento_id, arquivo.filename, conteudo, arquivo.mimetype)


@bp.route("/confirmar", methods=["POST"])
@ensure_authenticated
@requer_grupo
def confirmar():
    dados = request.get_json(silent=True) or {}
    forma_pagamento_id = dados.get("forma_pagamento_id")
    if not forma_pagamento_id:
        raise AppError("forma_pagamento_id é obrigatório.", 400, "campos_obrigatorios")

    importacao = confirmar_importacao(
        g.usuario_id, forma_pagamento_id, dados.get("arquivo_nome", ""), dados.get("linhas") or []
    )
    return importacao, 201


@bp.route("/<int:importacao_id>", methods=["DELETE"])
@ensure_authenticated
@requer_grupo
def desfazer(importacao_id):
    if not remover_importacao(g.usuario_id, importacao_id):
        raise AppError("Importação não encontrada.", 404, "nao_encontrado")
    return {"removida": True}
