"""
services/parcelamento.py — compras parceladas (Fase 3.2 do PLANO_EXECUCAO.md).
"""

from datetime import date

from db import get_conn, _get_grupo_id
from services.competencia import calcular_competencia, somar_meses

_MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março",    4: "Abril",
    5: "Maio",    6: "Junho",     7: "Julho",     8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}


def dividir_parcelas(valor_total: float, parcelas: int) -> list[float]:
    """
    Divide valor_total em `parcelas` parcelas de 2 casas decimais.

    Arredonda cada parcela para 2 casas e joga o resíduo do arredondamento
    inteiro na 1ª parcela — garante que a soma das parcelas bate exatamente
    com valor_total (auditável), em vez de espalhar centavos de diferença
    entre parcelas de forma imprevisível.
    """
    if parcelas < 1:
        raise ValueError("parcelas deve ser >= 1")
    valor_parcela = round(valor_total / parcelas, 2)
    residuo = round(valor_total - valor_parcela * parcelas, 2)
    return [round(valor_parcela + residuo, 2)] + [valor_parcela] * (parcelas - 1)


def formatar_competencia(data_competencia: date) -> str:
    return f"{_MESES_PT[data_competencia.month]}/{data_competencia.year}"


def criar_compra_parcelada(usuario_id: int, grupo_id, forma: dict, categoria: dict,
                            valor_total: float, parcelas: int, descricao: str):
    """
    Cria a compra parcelada + N gastos (1 por parcela), cada um com
    parcela_num e competencia própria calculada a partir do dia_fechamento
    da forma (Fase 3.2).

    Retorna (compra, gastos_criados, valor_parcela_padrao) — valor_parcela_padrao
    é o valor das parcelas 2..N (a 1ª pode ter alguns centavos a mais, ver
    dividir_parcelas).
    """
    data_compra = date.today()
    dia_fechamento = forma.get("dia_fechamento")
    competencia_1a = calcular_competencia(data_compra, dia_fechamento)
    valores = dividir_parcelas(valor_total, parcelas)
    categoria_id = categoria["id"] if categoria else None

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO compras_parceladas
                       (usuario_id, grupo_id, forma_pagamento_id, categoria_id,
                        descricao, valor_total, parcelas, data_compra)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING *""",
                (usuario_id, grupo_id, forma["id"], categoria_id,
                 descricao, valor_total, parcelas, data_compra),
            )
            compra = dict(cur.fetchone())

            gastos_criados = []
            for i, valor_i in enumerate(valores, start=1):
                competencia_i = somar_meses(competencia_1a, i - 1)
                cur.execute(
                    """INSERT INTO gastos
                           (usuario_id, forma_pagamento_id, categoria_id, valor, descricao,
                            grupo_id, competencia, compra_parcelada_id, parcela_num)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING *""",
                    (usuario_id, forma["id"], categoria_id, valor_i,
                     descricao, grupo_id, competencia_i, compra["id"], i),
                )
                gastos_criados.append(dict(cur.fetchone()))

            conn.commit()
            valor_parcela_padrao = valores[1] if parcelas > 1 else valores[0]
            return compra, gastos_criados, valor_parcela_padrao


def listar_parcelamentos_em_andamento(usuario_id: int) -> list[dict]:
    """
    Compras parceladas que ainda têm parcela a vencer (competência >= mês
    corrente) — aba "Parcelas" da web (pedido do Lucas em 18/07/2026:
    "quantas faltam, o total, etc").

    Contagens saem de `gastos` (fonte de verdade), não de
    compras_parceladas.parcelas: parcela excluída individualmente ("excluir
    ultimo" → "só esta") some da conta de restantes — o que sobrou a pagar
    é o que existe de fato, não o plano original. `parcelas` (plano) vai
    junto só pra exibir "3/12".

    Compra 100% no passado não aparece (HAVING restantes > 0) — a aba é de
    parcelas FUTURAS; histórico completo continua nos Lançamentos.

    Também inclui despesas FIXAS com prazo (parcelas_total, migração 025 —
    financiamento é "custo fixo parcelado", pedido do Lucas em 18/07/2026):
    entram na mesma lista com tipo="fixa", restantes = parcelas_total −
    lançadas e valor_restante = restantes × valor atual. `proxima`/`ultima`
    são derivadas da última competência lançada (as parcelas restantes
    ocupam os meses consecutivos seguintes).
    """
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        filtro = "cp.grupo_id = %s" if gid else "cp.usuario_id = %s AND cp.grupo_id IS NULL"
        param = gid if gid else usuario_id
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT cp.id, cp.descricao, cp.valor_total, cp.parcelas, cp.data_compra,
                           fp.nome AS forma_nome, u.nome AS membro_nome,
                           COUNT(g.id) AS parcelas_existentes,
                           COUNT(g.id) FILTER (
                               WHERE DATE_TRUNC('month', g.competencia) >= DATE_TRUNC('month', NOW())
                           ) AS parcelas_restantes,
                           COALESCE(SUM(g.valor) FILTER (
                               WHERE DATE_TRUNC('month', g.competencia) >= DATE_TRUNC('month', NOW())
                           ), 0) AS valor_restante,
                           MIN(g.competencia) FILTER (
                               WHERE DATE_TRUNC('month', g.competencia) >= DATE_TRUNC('month', NOW())
                           ) AS proxima_competencia,
                           MAX(g.competencia) AS ultima_competencia
                    FROM compras_parceladas cp
                    JOIN gastos g ON g.compra_parcelada_id = cp.id
                    LEFT JOIN formas_pagamento fp ON fp.id = cp.forma_pagamento_id
                    LEFT JOIN usuarios u          ON u.id  = cp.usuario_id
                    WHERE {filtro}
                    GROUP BY cp.id, cp.descricao, cp.valor_total, cp.parcelas,
                             cp.data_compra, fp.nome, u.nome
                    HAVING COUNT(g.id) FILTER (
                        WHERE DATE_TRUNC('month', g.competencia) >= DATE_TRUNC('month', NOW())
                    ) > 0
                    ORDER BY MIN(g.competencia) FILTER (
                        WHERE DATE_TRUNC('month', g.competencia) >= DATE_TRUNC('month', NOW())
                    )""",
                (param,),
            )
            compras = [dict(r) | {"tipo": "compra"} for r in cur.fetchall()]

            # Fixas com prazo (financiamento etc.) — mesma lista, tipo="fixa".
            filtro_f = "f.grupo_id = %s" if gid else "f.usuario_id = %s AND f.grupo_id IS NULL"
            cur.execute(
                f"""SELECT f.id, f.descricao, f.valor, f.parcelas_total,
                           fp.nome AS forma_nome, u.nome AS membro_nome,
                           (SELECT COUNT(*) FROM gastos g WHERE g.despesa_fixa_id = f.id)
                               AS lancadas,
                           (SELECT MAX(g.competencia) FROM gastos g WHERE g.despesa_fixa_id = f.id)
                               AS ultima_lancada
                    FROM despesas_fixas f
                    LEFT JOIN formas_pagamento fp ON fp.id = f.forma_pagamento_id
                    LEFT JOIN usuarios u          ON u.id  = f.usuario_id
                    WHERE {filtro_f} AND f.ativa = TRUE AND f.parcelas_total IS NOT NULL
                    ORDER BY f.descricao""",
                (param,),
            )
            fixas = []
            hoje_mes = date.today().replace(day=1)
            for f in cur.fetchall():
                f = dict(f)
                restantes = f["parcelas_total"] - f["lancadas"]
                if restantes <= 0:
                    continue
                base = f["ultima_lancada"].replace(day=1) if f["ultima_lancada"] else somar_meses(hoje_mes, -1)
                proxima = somar_meses(base, 1)
                fixas.append({
                    "id": f"fixa-{f['id']}",
                    "tipo": "fixa",
                    "descricao": f["descricao"],
                    "forma_nome": f["forma_nome"],
                    "membro_nome": f["membro_nome"],
                    "parcelas": f["parcelas_total"],
                    "parcelas_restantes": restantes,
                    "valor_restante": float(f["valor"]) * restantes,
                    "valor_total": float(f["valor"]) * f["parcelas_total"],
                    "proxima_competencia": proxima,
                    "ultima_competencia": somar_meses(base, restantes),
                })

    return sorted(compras + fixas, key=lambda c: str(c["proxima_competencia"] or ""))


def excluir_compra_parcelada(compra_id: int) -> dict | None:
    """Exclui todas as parcelas de uma compra + o registro da compra. Retorna a compra ou None."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM compras_parceladas WHERE id = %s", (compra_id,))
            row = cur.fetchone()
            if not row:
                return None
            compra = dict(row)
            cur.execute("DELETE FROM gastos WHERE compra_parcelada_id = %s", (compra_id,))
            cur.execute("DELETE FROM compras_parceladas WHERE id = %s", (compra_id,))
            conn.commit()
            return compra
