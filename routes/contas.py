"""
routes/contas.py — board "contas do mês" (pedido do Lucas, 24/07/2026).

Rotas finas, no padrão do CLAUDE.md: nenhuma regra de negócio aqui, tudo em
services/contas_mes.py. A chave da conta ("gasto:123" ou
"fatura:5:2026-07-01") vem no path — o front trata as duas identidades de
linha como uma coisa só e devolve a chave que recebeu, sem saber a diferença
entre um boleto e uma fatura de cartão.
"""

from flask import Blueprint, request, g

from middlewares.ensure_authenticated import ensure_authenticated, requer_grupo
from utils.app_error import AppError
from services.contas_mes import listar_contas_mes, marcar_conta, editar_valor_conta

bp = Blueprint("contas", __name__, url_prefix="/api/contas")


@bp.route("", methods=["GET"])
@ensure_authenticated
@requer_grupo
def listar():
    """?mes=YYYY-MM — mês do CAIXA (quando a conta é paga), não a competência
    do gasto. Default: mês corrente."""
    return listar_contas_mes(g.usuario_id, mes=request.args.get("mes"))


@bp.route("/<path:chave>", methods=["PATCH"])
@ensure_authenticated
@requer_grupo
def atualizar(chave):
    """
    Um PATCH só pras duas interações do card, porque as duas podem acontecer
    no mesmo gesto: ao marcar uma fatura como paga informando quanto pagou,
    `pago` e `valor` chegam juntos e precisam ser aplicados na mesma
    requisição (senão a UI teria que fazer 2 chamadas e tratar a falha da
    segunda com a primeira já gravada).

    Body: {"pago": bool} e/ou {"valor": number}.
    """
    dados = request.get_json(silent=True) or {}
    if "pago" not in dados and "valor" not in dados:
        raise AppError("Informe 'pago' e/ou 'valor'.", 400, "campos_obrigatorios")

    resultado = {"chave": chave}

    # `pago` ANTES de `valor`, e não o contrário: numa fatura, marcar como
    # paga é o que cria a linha em faturas_pagamentos, e é ela que
    # editar_valor_conta atualiza (numa fatura não paga, editar valor é
    # recusado de propósito — ver o service). Na ordem inversa, "marcar como
    # paga informando o valor" falharia com 409 no primeiro passo.
    if "pago" in dados:
        resultado.update(
            marcar_conta(
                g.usuario_id, chave, bool(dados["pago"]),
                valor_pago=dados.get("valor"),
            )
        )

    # Desmarcar apaga a linha da fatura — não há mais valor pago pra gravar.
    if "valor" in dados and dados.get("pago") is not False:
        resultado.update(editar_valor_conta(g.usuario_id, chave, dados["valor"]))

    return resultado
