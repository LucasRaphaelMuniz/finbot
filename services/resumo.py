"""
services/resumo.py — agregados prontos para o dashboard web (GET /api/resumo,
Fase 5.2 do PLANO_EXECUCAO.md). Toda a agregação roda aqui no Flask (1
request), não no browser — mesma decisão D6 de manter regra de negócio
concentrada, em vez de espalhar SUM/GROUP BY em múltiplas chamadas do front.
"""

from datetime import date

from db import get_conn, _get_grupo_id, get_saldo_todas_formas
from services.entradas import get_total_entradas_competencia
from services.entradas_fixas import total_entradas_fixas_previstas
from services.gastos import projetar_despesas_fixas


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

        # Fixas previstas (pedido do Lucas em 18/07/2026): navegando pra um
        # mês corrente/futuro, os totais devem antecipar as despesas fixas
        # que ainda não foram lançadas pelo cron naquele mês — mesma
        # projeção que os Lançamentos já mostram como "fixa (previsto)"
        # (services/gastos.projetar_despesas_fixas; retorna [] pra mês
        # passado, então mês fechado nunca mistura previsto com real).
        projetadas = projetar_despesas_fixas(conn, gid, usuario_id, competencia[:7])
        fixas_previstas = sum(float(p["valor"]) for p in projetadas)

        # Par das fixas previstas, do lado das receitas (migração 023):
        # salário recorrente ainda não lançado no mês também entra na
        # previsão — senão o mês seguinte mostraria só o lado dos gastos
        # previstos e um saldo artificialmente negativo.
        entradas_previstas = total_entradas_fixas_previstas(
            conn, gid, usuario_id, date(*(int(p) for p in competencia.split("-")[:2]), 1)
        )

    total_gastos = sum(c["total"] for c in por_categoria)
    total_entradas = get_total_entradas_competencia(usuario_id, competencia)

    # % médio dos limites usados (StatCard do §5.2) — gasto do mês (por
    # competência corrente) vs limite_mensal, pra toda forma COM limite.
    # Voltou à conta simples original depois do desvio pelo "limite
    # rotativo" (removido em 18/07/2026 — ver services/faturas.py): com
    # competência = mês da fatura, gasto do mês do cartão É a fatura atual,
    # exatamente o número que o Lucas acompanha contra o limite.
    #
    # LIMITAÇÃO CONHECIDA (herdada): get_saldo_todas_formas calcula sempre
    # pro mês ATUAL (NOW() na query) — não respeita o parâmetro `mes`.
    # Resumo de mês passado mostra o % de limite de hoje, não daquele mês.
    formas = get_saldo_todas_formas(usuario_id)
    percentuais = [
        (float(f["gasto_mes"]) / float(f["limite_mensal"])) * 100
        for f in formas if f.get("limite_mensal")
    ]
    pct_limite_medio = sum(percentuais) / len(percentuais) if percentuais else None

    return {
        "mes": competencia[:7],
        # Controle: tudo que foi COMPRADO na competência (inclui cartão na
        # fatura do mês) — a visão pra saber "quanto estou gastando".
        "total_gastos": total_gastos,
        # Fixas ativas que ainda não foram lançadas nessa competência (0 pra
        # mês passado). total_gastos_previsto = real + previsto — é o número
        # a olhar ao navegar pro mês seguinte.
        "fixas_previstas": fixas_previstas,
        "total_gastos_previsto": total_gastos + fixas_previstas,
        "total_entradas": total_entradas,
        # Entradas recorrentes (salário) ainda não lançadas no mês — par das
        # fixas_previstas do lado das receitas (0 pra mês passado).
        "entradas_previstas": entradas_previstas,
        "total_entradas_previsto": total_entradas + entradas_previstas,
        "saldo": total_entradas - total_gastos,
        # Saldo projetado do mês considerando os dois lados previstos — o
        # número a olhar ao navegar pro mês seguinte.
        "saldo_previsto": (total_entradas + entradas_previstas)
                          - (total_gastos + fixas_previstas),
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
