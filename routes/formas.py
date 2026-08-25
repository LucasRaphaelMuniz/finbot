"""routes/formas.py — CRUD de formas de pagamento (Fase 4.3)."""

from datetime import date

from flask import Blueprint, request, g

from middlewares.ensure_authenticated import ensure_authenticated, requer_grupo
from utils.app_error import AppError
from db import get_formas_pagamento
from services.formas import criar_forma, atualizar_forma, remover_forma
from services.faturas import status_cartao, definir_ajuste_fatura, remover_ajuste_fatura

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
    """Fatura atual (= gasto do mês do cartão) vs limite + fatura anterior
    a pagar — services/faturas.py, modelo final de 18/07/2026. Só faz
    sentido pra formas com dia_fechamento; devolve totais zerados pra quem
    não tem (o front decide se mostra)."""
    status = status_cartao(g.usuario_id, forma_id)
    if not status:
        raise AppError("Forma de pagamento não encontrada.", 404, "nao_encontrado")
    return status


def _competencia_do_body(dados: dict) -> date:
    """"YYYY-MM" ou "YYYY-MM-DD" -> date(YYYY, MM, 1). Sem `competencia` no
    body, usa o mês atual — caso comum (corrigir a fatura que está fechando
    agora)."""
    valor = dados.get("competencia")
    if not valor:
        return date.today().replace(day=1)
    try:
        partes = [int(p) for p in valor.split("-")[:2]]
        return date(partes[0], partes[1], 1)
    except (ValueError, IndexError, TypeError):
        raise AppError("competencia inválida — use o formato YYYY-MM.", 400, "competencia_invalida")


@bp.route("/<int:forma_id>/ajuste-fatura", methods=["PUT"])
@ensure_authenticated
@requer_grupo
def definir_ajuste_fatura_view(forma_id):
    """Ajuste manual da fatura (migração 028, pedido do Lucas: "às vezes dá
    uma pequena diferença por fechamento") — soma/subtrai um valor fixo por
    cima da soma dos gastos daquela competência, sem redistribuir entre eles.
    `valor_ajuste` pode ser negativo (fatura fechou menor que a soma)."""
    dados = request.get_json(silent=True) or {}
    if dados.get("valor_ajuste") is None:
        raise AppError("valor_ajuste é obrigatório.", 400, "campos_obrigatorios")
    try:
        valor_ajuste = float(dados["valor_ajuste"])
    except (TypeError, ValueError):
        raise AppError("valor_ajuste inválido.", 400, "valor_invalido")
    competencia = _competencia_do_body(dados)
    ajuste = definir_ajuste_fatura(
        g.usuario_id, forma_id, competencia, valor_ajuste, motivo=dados.get("motivo")
    )
    if ajuste is None:
        raise AppError("Forma de pagamento não encontrada.", 404, "nao_encontrado")
    return ajuste


@bp.route("/<int:forma_id>/ajuste-fatura", methods=["DELETE"])
@ensure_authenticated
@requer_grupo
def remover_ajuste_fatura_view(forma_id):
    dados = request.get_json(silent=True) or {}
    competencia = _competencia_do_body(dados)
    if not remover_ajuste_fatura(g.usuario_id, forma_id, competencia):
        raise AppError("Ajuste não encontrado.", 404, "nao_encontrado")
    return {"removido": True}
