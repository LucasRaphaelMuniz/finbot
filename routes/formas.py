"""routes/formas.py — CRUD de formas de pagamento (Fase 4.3)."""

from flask import Blueprint, request, g

from middlewares.ensure_authenticated import ensure_authenticated, requer_grupo
from utils.app_error import AppError
from db import get_formas_pagamento
from services.formas import criar_forma, atualizar_forma, remover_forma
from services.faturas import status_cartao, marcar_fatura_paga

bp = Blueprint("formas", __name__, url_prefix="/api/formas")


@bp.route("", methods=["GET"])
@ensure_authenticated
@requer_grupo
def listar():
    return {"itens": get_formas_pagamento(g.usuario_id)}


@bp.route("", methods=["POST"])
@ensure_authenticated
@requer_grupo
def criar():
    dados = request.get_json(silent=True) or {}
    nome = (dados.get("nome") or "").strip()
    if not nome:
        raise AppError("nome é obrigatório.", 400, "campos_obrigatorios")
    forma = criar_forma(
        g.usuario_id, nome,
        limite_mensal=dados.get("limite_mensal"), dia_fechamento=dados.get("dia_fechamento"),
        dia_vencimento=dados.get("dia_vencimento"),
    )
    return forma, 201


@bp.route("/<int:forma_id>", methods=["PUT"])
@ensure_authenticated
@requer_grupo
def atualizar(forma_id):
    dados = request.get_json(silent=True) or {}
    forma = atualizar_forma(
        g.usuario_id, forma_id,
        nome=dados.get("nome"), limite_mensal=dados.get("limite_mensal"),
        dia_fechamento=dados.get("dia_fechamento"),
        dia_vencimento=dados.get("dia_vencimento"),
    )
    if not forma:
        raise AppError("Forma de pagamento não encontrada (ou nenhum campo pra atualizar).", 404, "nao_encontrado")
    return forma


@bp.route("/<int:forma_id>", methods=["DELETE"])
@ensure_authenticated
@requer_grupo
def remover(forma_id):
    if not remover_forma(g.usuario_id, forma_id):
        raise AppError("Forma de pagamento não encontrada.", 404, "nao_encontrado")
    return {"removida": True}


@bp.route("/<int:forma_id>/status-cartao", methods=["GET"])
@ensure_authenticated
@requer_grupo
def status_cartao_view(forma_id):
    """Limite rotativo real (fatura fechada a pagar + fatura aberta +
    limite usado/disponível) — services/faturas.py, migração 021. Só faz
    sentido pra formas com dia_fechamento; devolve os totais zerados pra
    quem não tem (o front decide se mostra ou não)."""
    status = status_cartao(g.usuario_id, forma_id)
    if not status:
        raise AppError("Forma de pagamento não encontrada.", 404, "nao_encontrado")
    return status


@bp.route("/<int:forma_id>/pagar-fatura", methods=["POST"])
@ensure_authenticated
@requer_grupo
def pagar_fatura(forma_id):
    """Marca a fatura de uma competência (padrão: mês atual) como paga.
    Idempotente — chamar de novo não duplica nem quebra."""
    dados = request.get_json(silent=True) or {}
    resultado = marcar_fatura_paga(g.usuario_id, forma_id, competencia=dados.get("competencia"))
    if not resultado:
        raise AppError("Forma de pagamento não encontrada.", 404, "nao_encontrado")
    return resultado, 201
