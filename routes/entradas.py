"""routes/entradas.py — GET/POST /api/entradas, PUT/DELETE /api/entradas/:id (Fase 4.3)."""

from datetime import date

from flask import Blueprint, request, g

from middlewares.ensure_authenticated import ensure_authenticated, requer_grupo
from utils.app_error import AppError
from services.entradas import (
    registrar_entrada,
    get_entradas_mes,
    atualizar_entrada,
    remover_entrada,
)
from services.entradas_fixas import criar_entrada_fixa, definir_recorrencia_entrada

bp = Blueprint("entradas", __name__, url_prefix="/api/entradas")


@bp.route("", methods=["GET"])
@ensure_authenticated
@requer_grupo
def listar():
    # services/entradas.py hoje só tem get_entradas_mes (mês corrente, usado
    # pelo bot). Filtro por mês arbitrário fica pendente — o dashboard usa
    # GET /api/resumo (services/resumo.py) pro histórico agregado; a lista
    # crua por mês passado só importa pra tela de /lancamentos (Fase 5.1),
    # que ainda não existe.
    return {"itens": get_entradas_mes(g.usuario_id)}


@bp.route("", methods=["POST"])
@ensure_authenticated
@requer_grupo
def criar():
    dados = request.get_json(silent=True) or {}
    if dados.get("valor") is None:
        raise AppError("valor é obrigatório.", 400, "campos_obrigatorios")

    # `recorrente: true` (migração 023): além de registrar a entrada de
    # agora, cria o modelo em entradas_fixas — o lançador diário repete nos
    # próximos meses no dia informado (default: dia de hoje). A entrada de
    # hoje já nasce vinculada ao modelo (entrada_fixa_id) pra o índice
    # único não deixar o lançador duplicar ainda este mês.
    if dados.get("recorrente"):
        dia = int(dados.get("dia_lancamento") or date.today().day)
        if not 1 <= dia <= 31:
            raise AppError("dia_lancamento deve estar entre 1 e 31.", 400, "dia_invalido")
        fixa = criar_entrada_fixa(
            g.usuario_id, dados.get("descricao", ""), float(dados["valor"]), dia,
        )
        entrada = registrar_entrada(
            g.usuario_id, float(dados["valor"]), dados.get("descricao", ""),
            entrada_fixa_id=fixa["id"],
        )
        return {**entrada, "entrada_fixa": fixa}, 201

    entrada = registrar_entrada(g.usuario_id, float(dados["valor"]), dados.get("descricao", ""))
    return entrada, 201


@bp.route("/<int:entrada_id>", methods=["PUT"])
@ensure_authenticated
@requer_grupo
def atualizar(entrada_id):
    dados = request.get_json(silent=True) or {}
    entrada = atualizar_entrada(g.usuario_id, entrada_id, valor=dados.get("valor"), descricao=dados.get("descricao"))

    # `recorrente` presente no body: liga/desliga a recorrência a partir
    # desta entrada (pedido 18/07/2026 — o flag só existia no criar).
    # Ordem importa: atualizar valor/descricao ANTES, porque ligar a
    # recorrência sincroniza o modelo com os valores atuais da entrada.
    if "recorrente" in dados:
        resultado = definir_recorrencia_entrada(
            g.usuario_id, entrada_id, bool(dados["recorrente"]),
            dia_lancamento=dados.get("dia_lancamento"),
        )
        if resultado:
            return resultado
        if not entrada:
            raise AppError("Entrada não encontrada.", 404, "nao_encontrado")
        return entrada

    if not entrada:
        raise AppError("Entrada não encontrada (ou nenhum campo pra atualizar).", 404, "nao_encontrado")
    return entrada


@bp.route("/<int:entrada_id>", methods=["DELETE"])
@ensure_authenticated
@requer_grupo
def remover(entrada_id):
    entrada = remover_entrada(g.usuario_id, entrada_id)
    if not entrada:
        raise AppError("Entrada não encontrada.", 404, "nao_encontrado")
    return entrada
