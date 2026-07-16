"""routes/categorias.py — CRUD de categorias (Fase 4.3)."""

from flask import Blueprint, request, g

from middlewares.ensure_authenticated import ensure_authenticated, requer_grupo
from utils.app_error import AppError
from services.categorias import (
    get_categorias,
    adicionar_categoria,
    atualizar_categoria,
    remover_categoria_por_id,
    alternar_categoria_ativa,
)

bp = Blueprint("categorias", __name__, url_prefix="/api/categorias")


@bp.route("", methods=["GET"])
@ensure_authenticated
@requer_grupo
def listar():
    # Cada item já vem com grupo_id (NULL = padrão global) e `ativo`
    # calculado por grupo (migração 016 — ver services/categorias.py) — o
    # front usa grupo_id pra marcar "padrão" na UI e `ativo` pro checkbox
    # de ativar/desativar (§5.5 do plano: categoria global é ocultável por
    # grupo via PUT .../ativo, mas nunca deletável — G5).
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


@bp.route("/<int:categoria_id>/ativo", methods=["PUT"])
@ensure_authenticated
@requer_grupo
def alternar_ativo(categoria_id):
    # Diferente de atualizar() acima: isso vale tanto pra categoria
    # customizada quanto pra padrão (G5 continua valendo — nunca edita nome
    # nem remove categoria global, só controla se ela aparece pro grupo).
    dados = request.get_json(silent=True) or {}
    if "ativo" not in dados:
        raise AppError("ativo é obrigatório.", 400, "campos_obrigatorios")
    categoria = alternar_categoria_ativa(g.usuario_id, categoria_id, bool(dados["ativo"]))
    if not categoria:
        raise AppError("Categoria não encontrada.", 404, "nao_encontrado")
    return categoria


@bp.route("/<int:categoria_id>", methods=["DELETE"])
@ensure_authenticated
@requer_grupo
def remover(categoria_id):
    # G5 do plano: categorias globais nunca são removidas, só ocultadas por
    # grupo — pra isso existe PUT /<id>/ativo (migração 016), não este DELETE.
    # Aqui, DELETE numa categoria global simplesmente não acha nada pra
    # remover (o WHERE em services.categorias.remover_categoria_por_id já
    # filtra por grupo_id = <grupo do usuário>, que é NULL pras globais) e
    # cai no 404 abaixo — não é um bug, é essa limitação explícita.
    if not remover_categoria_por_id(g.usuario_id, categoria_id):
        raise AppError(
            "Categoria não encontrada entre as personalizadas do seu grupo.", 404, "nao_encontrado"
        )
    return {"removida": True}
