"""
services/resumo.py — agregados prontos para o dashboard web (GET /api/resumo,
Fase 5.2 do PLANO_EXECUCAO.md). Toda a agregação roda aqui no Flask (1
request), não no browser — mesma decisão D6 de manter regra de negócio
concentrada, em vez de espalhar SUM/GROUP BY em múltiplas chamadas do front.
"""

from datetime import date

from db import get_conn, _get_grupo_id, get_saldo_todas_formas
from services.entradas import get_total_entradas_competencia


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

    total_gastos = sum(c["total"] for c in por_categoria)
    total_entradas = get_total_entradas_competencia(usuario_id, competencia)

    # % médio dos limites usados (StatCard do §5.2) — reaproveita
    # db.get_saldo_todas_formas (mesma query que o bot usa em "saldo"), só
    # pras formas COM limite_mensal configurado; forma sem limite não entra
    # na média (não faz sentido dizer "0% de limite" pra algo sem limite).
    #
    # LIMITAÇÃO CONHECIDA: get_saldo_todas_formas sempre calcula pro mês
    # ATUAL (usa NOW() na query, mesma função que o bot usa em "saldo") —
    # não respeita o parâmetro `mes` desta função. Pedir o resumo de um mês
    # passado mostra o % de limite de HOJE, não daquele mês. Corrigir exigiria
    # parametrizar get_saldo_todas_formas com a competência (mexendo em
    # db.py, usado pelo bot) — fora do escopo desta Fase 5.2; documentado
    # aqui em vez de silenciado.
    formas = get_saldo_todas_formas(usuario_id)
    percentuais = [
        (float(f["gasto_mes"]) / float(f["limite_mensal"])) * 100
        for f in formas if f.get("limite_mensal")
    ]
    pct_limite_medio = sum(percentuais) / len(percentuais) if percentuais else None

    return {
        "mes": competencia[:7],
        "total_gastos": total_gastos,
        "total_entradas": total_entradas,
        "saldo": total_entradas - total_gastos,
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
