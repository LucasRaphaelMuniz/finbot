"""routes/categorias.py — CRUD de categorias (Fase 4.3)."""

from flask import Blueprint, request, g

from middlewares.ensure_authenticated import ensure_authenticated, requer_grupo
from utils.app_error import AppError
from services.categorias import (
    get_categorias,
    adicionar_categoria,
    atualizar_categoria,
    remover_categoria_por_id,
)

bp = Blueprint("categorias", __name__, url_prefix="/api/categorias")


@bp.route("", methods=["GET"])
@ensure_authenticated
@requer_grupo
def listar():
    # Cada item já vem com grupo_id (NULL = padrão global) — o front usa
    # isso pra marcar "padrão" na UI (§5.5 do plano: categoria global aparece
    # como padrão, ocultável mas não deletável — ocultar ainda não existe,
    # ver nota abaixo em remover()).
    return {"itens": get_categorias(g.usuario_id)}


@bp.route("", methods=["POST"])
@ensure_authenticated
@requer_grupo
def criar():
    dados = request.get_json(silent=True) or {}
    nome = (dados.get("nome") or "").strip()
    if not nome:
        raise AppError("nome é obrigatório.", 400, "campos_obrigatorios")
    categoria = adicionar_categoria(g.usuario_id, nome)
    if not categoria:
        raise AppError(f"Já existe uma categoria '{nome}' (padrão ou do seu grupo).", 400, "categoria_duplicada")
    return categoria, 201


@bp.route("/<int:categoria_id>", methods=["PUT"])
@ensure_authenticated
@requer_grupo
def atualizar(categoria_id):
    dados = request.get_json(silent=True) or {}
    categoria = atualizar_categoria(g.usuario_id, categoria_id, dados.get("nome", ""))
    if not categoria:
        raise AppError(
            "Categoria não encontrada entre as personalizadas do seu grupo "
            "(categorias padrão não podem ser editadas — G5 do PLANO_EXECUCAO.md).",
            404, "nao_encontrado",
        )
    return categoria


@bp.route("/<int:categoria_id>", methods=["DELETE"])
@ensure_authenticated
@requer_grupo
def remover(categoria_id):
    # G5 do plano: categorias globais nunca são removidas, só ocultadas por
    # grupo. "Ocultar" exigiria uma tabela nova (categorias_ocultas por
    # grupo) que não está na Fase 2 — fora do escopo da 4.3. Por ora, DELETE
    # numa categoria global simplesmente não acha nada pra remover (o WHERE
    # em services.categorias.remover_categoria_por_id já filtra por
    # grupo_id = <grupo do usuário>, que é NULL pras globais) e cai no 404
    # abaixo — não é um bug, é essa limitação explícita.
    if not remover_categoria_por_id(g.usuario_id, categoria_id):
        raise AppError(
            "Categoria não encontrada entre as personalizadas do seu grupo.", 404, "nao_encontrado"
        )
    return {"removida": True}
