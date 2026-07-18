"""
services/resumo.py — agregados prontos para o dashboard web (GET /api/resumo,
Fase 5.2 do PLANO_EXECUCAO.md). Toda a agregação roda aqui no Flask (1
request), não no browser — mesma decisão D6 de manter regra de negócio
concentrada, em vez de espalhar SUM/GROUP BY em múltiplas chamadas do front.
"""

from datetime import date

from db import get_conn, _get_grupo_id, get_saldo_todas_formas, get_formas_pagamento
from services.entradas import get_total_entradas_competencia
from services.faturas import status_cartao


def resumo_mensal(usuario_id: int, mes: str = None) -> dict:
    """mes: "YYYY-MM"; default = mês atual."""
    competencia = f"{mes}-01" if mes else date.today().replace(day=1).isoformat()

    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        if gid:
            filtro_gastos, param_gastos = "g.grupo_id = %s", gid
            filtro_entradas = "e.grupo_id = %s"
        else:
            filtro_gastos, param_gastos = "g.usuario_id = %s AND g.grupo_id IS NULL", usuario_id
            filtro_entradas = "e.usuario_id = %s AND e.grupo_id IS NULL"

        with conn.cursor() as cur:
            # Donut por categoria
            cur.execute(
                f"""SELECT c.nome AS categoria, SUM(g.valor) AS total
                    FROM gastos g JOIN categorias c ON c.id = g.categoria_id
                    WHERE {filtro_gastos}
                      AND DATE_TRUNC('month', g.competencia) = DATE_TRUNC('month', %s::date)
                    GROUP BY c.nome ORDER BY total DESC""",
                (param_gastos, competencia),
            )
            por_categoria = [{"categoria": r["categoria"], "total": float(r["total"])} for r in cur.fetchall()]

            # Fixo x variável
            cur.execute(
                f"""SELECT (g.despesa_fixa_id IS NOT NULL) AS fixo, SUM(g.valor) AS total
                    FROM gastos g
                    WHERE {filtro_gastos}
                      AND DATE_TRUNC('month', g.competencia) = DATE_TRUNC('month', %s::date)
                    GROUP BY fixo""",
                (param_gastos, competencia),
            )
            fixo_variavel = {"fixo": 0.0, "variavel": 0.0}
            for r in cur.fetchall():
                fixo_variavel["fixo" if r["fixo"] else "variavel"] = float(r["total"])

            # Últimos 6 meses — gastos por competência
            cur.execute(
                f"""SELECT DATE_TRUNC('month', g.competencia) AS mes, SUM(g.valor) AS total
                    FROM gastos g
                    WHERE {filtro_gastos}
                      AND g.competencia >= (%s::date - INTERVAL '5 months')
                    GROUP BY mes ORDER BY mes""",
                (param_gastos, competencia),
            )
            gastos_por_mes = {str(r["mes"])[:7]: float(r["total"]) for r in cur.fetchall()}

            # Últimos 6 meses — entradas por mês
            cur.execute(
                f"""SELECT DATE_TRUNC('month', e.data) AS mes, SUM(e.valor) AS total
                    FROM entradas e
                    WHERE {filtro_entradas}
                      AND e.data >= (%s::date - INTERVAL '5 months')
                    GROUP BY mes ORDER BY mes""",
                (param_gastos, competencia),
            )
            entradas_por_mes = {str(r["mes"])[:7]: float(r["total"]) for r in cur.fetchall()}

            # ── Caixa do mês (modelo "fatura como conta a pagar", revisão de
            # 17-18/07/2026 — ver services/competencia.py) ─────────────────
            # O que efetivamente SAI do caixa no mês pedido:
            # 1. gastos não-cartão da competência (débito/pix/Custo Fixo
            #    saem na hora — LEFT JOIN pra incluir gasto sem forma);
            # 2. faturas de cartão que VENCEM nesse mês. A fatura que vence
            #    no mês M é a de competência M (cartão que fecha e vence no
            #    mesmo mês: dia_vencimento > dia_fechamento) ou M-1 (venc.
            #    no mês seguinte ao fechamento — fallback quando
            #    dia_vencimento não está preenchido). Mesma regra de
            #    mes_vencimento() em services/competencia.py, expressa em
            #    SQL pra sair em 1 query em vez de 1 por forma.
            cur.execute(
                f"""SELECT COALESCE(SUM(g.valor), 0) AS total
                    FROM gastos g
                    LEFT JOIN formas_pagamento fp ON fp.id = g.forma_pagamento_id
                    WHERE {filtro_gastos}
                      AND (fp.id IS NULL OR fp.dia_fechamento IS NULL)
                      AND DATE_TRUNC('month', g.competencia) = DATE_TRUNC('month', %s::date)""",
                (param_gastos, competencia),
            )
            gastos_nao_cartao = float(cur.fetchone()["total"])

            cur.execute(
                f"""SELECT COALESCE(SUM(g.valor), 0) AS total
                    FROM gastos g
                    JOIN formas_pagamento fp ON fp.id = g.forma_pagamento_id
                    WHERE {filtro_gastos}
                      AND fp.dia_fechamento IS NOT NULL
                      AND DATE_TRUNC('month', g.competencia) =
                          DATE_TRUNC('month', %s::date)
                          - (CASE WHEN fp.dia_vencimento IS NOT NULL
                                       AND fp.dia_vencimento > fp.dia_fechamento
                                  THEN INTERVAL '0 months'
                                  ELSE INTERVAL '1 month' END)""",
                (param_gastos, competencia),
            )
            fatura_a_pagar = float(cur.fetchone()["total"])

    total_gastos = sum(c["total"] for c in por_categoria)
    total_entradas = get_total_entradas_competencia(usuario_id, competencia)

    # % médio dos limites usados (StatCard do §5.2), só pras formas COM
    # limite_mensal configurado; forma sem limite não entra na média (não
    # faz sentido dizer "0% de limite" pra algo sem limite).
    #
    # Formas tipo cartão (dia_fechamento configurado) usam limite ROTATIVO
    # real (services/faturas.py, migração 021) em vez do "gasto do mês" —
    # desde 019/020 a competência de cartão é o mês do vencimento, então
    # gasto_mes de get_saldo_todas_formas já não representa mais "quanto do
    # limite está comprometido" (ignora fatura fechada a pagar e parcelas
    # futuras). Formas sem dia_fechamento (pix/débito/Custo Fixo) continuam
    # na conta simples de sempre.
    #
    # LIMITAÇÃO CONHECIDA (herdada, ainda não resolvida): tanto
    # get_saldo_todas_formas quanto status_cartao calculam pro mês ATUAL —
    # não respeitam o parâmetro `mes` desta função. Pedir o resumo de um mês
    # passado mostra o % de limite de HOJE, não daquele mês. Corrigir exigiria
    # parametrizar as duas com a competência — fora do escopo desta Fase.
    todas_formas = get_formas_pagamento(usuario_id)
    formas_saldo = {f["id"]: f for f in get_saldo_todas_formas(usuario_id)}
    percentuais = []
    for f in todas_formas:
        if not f.get("limite_mensal"):
            continue
        limite = float(f["limite_mensal"])
        if f.get("dia_fechamento"):
            status = status_cartao(usuario_id, f["id"])
            usado = status["limite_usado"] if status else 0.0
        else:
            saldo = formas_saldo.get(f["id"])
            usado = float(saldo["gasto_mes"]) if saldo else 0.0
        percentuais.append((usado / limite) * 100)
    pct_limite_medio = sum(percentuais) / len(percentuais) if percentuais else None

    return {
        "mes": competencia[:7],
        # Controle: tudo que foi COMPRADO na competência (inclui cartão na
        # fatura do mês) — a visão pra saber "quanto estou gastando".
        "total_gastos": total_gastos,
        "total_entradas": total_entradas,
        "saldo": total_entradas - total_gastos,
        # Caixa: o que efetivamente SAI DO BOLSO no mês — gastos à vista +
        # faturas de cartão que vencem nele. É aqui que o cartão aparece
        # "provisionado" pro mês seguinte, sem tirar as compras da visão de
        # controle acima.
        "caixa": {
            "gastos_nao_cartao": gastos_nao_cartao,
            "fatura_a_pagar": fatura_a_pagar,
            "saida_total": gastos_nao_cartao + fatura_a_pagar,
            "saldo_caixa": total_entradas - gastos_nao_cartao - fatura_a_pagar,
        },
        "pct_limite_medio": pct_limite_medio,
        "por_categoria": por_categoria,
        "fixo_variavel": fixo_variavel,
        "comparativo_6_meses": montar_comparativo(gastos_por_mes, entradas_por_mes),
    }


def montar_comparativo(gastos_por_mes: dict, entradas_por_mes: dict) -> list[dict]:
    """
    Função pura (sem banco) — junta os dois dicts mês->total num array
    ordenado, preenchendo com 0 os meses sem lançamento nenhum lado.
    Extraída à parte de propósito: é a única peça de resumo_mensal testável
    sem subir um banco de verdade (mesma filosofia dos outros services —
    lógica pura tem teste, lógica com SQL é verificada manualmente via bot/API).
    """
    meses = sorted(set(gastos_por_mes) | set(entradas_por_mes))
    return [
        {"mes": m, "gastos": gastos_por_mes.get(m, 0.0), "entradas": entradas_por_mes.get(m, 0.0)}
        for m in meses
    ]
