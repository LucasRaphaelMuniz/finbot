"""
services/faturas.py — status simples de cartão (revisão final 18/07/2026).

Modelo de uma frase, fechado com o Lucas depois de DUAS tentativas mais
complexas: **o gasto mensal do cartão e o valor da fatura são o mesmo
número** — o que se gasta no cartão em julho é a fatura de julho; a única
diferença é quando sai do bolso (agosto, via provisão de caixa em
services/resumo.py).

Histórico do que foi tentado e descartado, pra ninguém reintroduzir sem
saber por quê:
1. Competência = mês do vencimento (migração 020): a compra de hoje sumia
   das telas do mês corrente. Revertido pela 022.
2. Limite rotativo real (021: faturas_pagas + parcelas futuras + fatura
   fechada não paga + comando "paguei a fatura"): modelava como o BANCO
   enxerga limite, não como o Lucas acompanha o orçamento — o número
   "limite usado" misturava meses e parcelas futuras e não respondia
   "quanto gastei este mês?". Removido pela migração 024 (dropa
   faturas_pagas).

O que ficou:
- fatura_atual: a fatura que está acumulando as compras de agora
  (calcular_competencia de hoje) — É o gasto mensal do cartão, comparado
  direto com limite_mensal.
- fatura_anterior: a fatura já fechada, com o mês em que vence
  (mes_vencimento) — informativo de "quanto vou pagar agora", mesma conta
  que o caixa do resumo provisiona.

AJUSTE MANUAL (migração 028, pedido do Lucas em 25/08/2026: "às vezes dá uma
pequena diferença por fechamento") — a fatura calculada aqui é a SOMA dos
gastos lançados; o banco pode fechar com juros/IOF/arredondamento que não
viram um gasto individual. `ajustes_fatura` guarda essa diferença por
(forma, competência), somada por cima da soma bruta — mesma filosofia de
`faturas_pagamentos` (migração 027, contas_mes.py): não redistribui entre os
gastos que já existem, só anota a diferença à parte.

ESTIMATIVA (Q2 do pedido do Lucas: "valor estimado, com os parcelamentos")
— fatura_atual_estimada = fatura_atual (real, já lançado + ajuste) + as
despesas fixas DAQUELE cartão que ainda não foram lançadas nessa competência
(mesma projeção de services/gastos.py::projetar_despesas_fixas que o
dashboard já usa em `fixas_previstas`, só filtrada pra 1 forma). Compra
parcelada NÃO entra na estimativa por separado: as parcelas futuras já são
gastos reais com competência própria desde a criação da compra
(services/parcelamento.py) — só ainda não chegou a vez delas.

DESPESA FIXA ANTECIPADA vs. "REAL" (29/08/2026, pedido do Lucas) — o passe 2
de `despesas_fixas.py::lancar_despesas_fixas_do_mes` cria o gasto do MÊS
SEGUINTE com antecedência (dia 18/07/2026: "quero igual compra parcelada",
pra virar linha editável em vez de "previsto" sintético). Isso resolveu o
problema de EDIÇÃO, mas criou um novo: a linha passa a existir em `gastos`
com `data` no futuro (ainda não chegou o dia de cobrança), e a soma bruta
por competência abaixo não distinguia "já é dia de cobrar" de "só existe
adiantado" — o valor entrava direto na fatura ATUAL (real), inflando ela
antes da hora, e nunca aparecia na estimativa (`projetar_despesas_fixas`
não projeta o que já tem gasto real, então o item ficava invisível ali).

Fix: pra despesa fixa (`despesa_fixa_id IS NOT NULL`), só conta como fatura
ATUAL quando `data <= hoje` — chegou o dia de cobrança de verdade. Uma
compra avulsa ou parcela (`despesa_fixa_id IS NULL`) continua contando
inteira pela competência, sem esse filtro — isso NÃO muda (parcela futura
já é "certeza que vou pagar" desde a criação, é exatamente o modelo que a
antecipação de despesa fixa tentou copiar). A fatura ESTIMADA volta a
enxergar a despesa fixa antecipada mas ainda não vencida — soma TUDO da
competência (sem o filtro de data), então ela nunca fica "invisível": some
da fatura atual e reaparece na estimada até o dia de cobrança chegar.
"""

from datetime import date

from db import get_conn, _get_grupo_id
from services.competencia import calcular_competencia, mes_vencimento, somar_meses
from services.gastos import projetar_despesas_fixas


def _forma_pertence_ao_usuario(conn, usuario_id: int, forma_id: int) -> bool:
    gid = _get_grupo_id(conn, usuario_id)
    with conn.cursor() as cur:
        if gid:
            cur.execute(
                "SELECT 1 FROM formas_pagamento WHERE id = %s AND grupo_id = %s",
                (forma_id, gid),
            )
        else:
            cur.execute(
                "SELECT 1 FROM formas_pagamento WHERE id = %s AND usuario_id = %s AND grupo_id IS NULL",
                (forma_id, usuario_id),
            )
        return cur.fetchone() is not None


def _get_ajuste(cur, forma_id: int, competencia: date) -> tuple[float, str | None]:
    cur.execute(
        "SELECT valor_ajuste, motivo FROM ajustes_fatura "
        "WHERE forma_pagamento_id = %s AND competencia = %s",
        (forma_id, competencia),
    )
    row = cur.fetchone()
    return (float(row["valor_ajuste"]), row["motivo"]) if row else (0.0, None)


def status_cartao(usuario_id: int, forma_id: int) -> dict | None:
    """
    Status da forma tipo cartão:

    - fatura_atual: soma dos gastos da competência que ainda aceita compras
      hoje, + ajuste manual (ver docstring do módulo) — É O GASTO MENSAL DO
      CARTÃO, comparar com limite_mensal.
    - fatura_atual_estimada: fatura_atual + despesas fixas daquele cartão
      ainda não lançadas nessa competência — pra onde a fatura deve fechar.
    - fatura_anterior: a fatura fechada (+ ajuste), e em que mês ela vence
      (vencimento_fatura_anterior) — o valor que vai sair do caixa.

    Retorna None se a forma não existe/não pertence ao usuário.
    """
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        if not _forma_pertence_ao_usuario(conn, usuario_id, forma_id):
            return None

        with conn.cursor() as cur:
            cur.execute(
                "SELECT nome, limite_mensal, dia_fechamento, dia_vencimento "
                "FROM formas_pagamento WHERE id = %s",
                (forma_id,),
            )
            forma = cur.fetchone()
            if not forma:
                return None
            forma = dict(forma)

            hoje = date.today()
            comp_atual = calcular_competencia(hoje, forma.get("dia_fechamento"))
            comp_anterior = somar_meses(comp_atual, -1)

            cur.execute(
                """SELECT
                       COALESCE(SUM(valor) FILTER (
                           WHERE DATE_TRUNC('month', competencia) = %s
                             AND (despesa_fixa_id IS NULL OR data <= %s)
                       ), 0) AS fatura_atual,
                       COALESCE(SUM(valor) FILTER (
                           WHERE DATE_TRUNC('month', competencia) = %s
                       ), 0) AS fatura_atual_sem_filtro_data,
                       COALESCE(SUM(valor) FILTER (
                           WHERE DATE_TRUNC('month', competencia) = %s
                             AND (despesa_fixa_id IS NULL OR data <= %s)
                       ), 0) AS fatura_anterior,
                       COUNT(*) FILTER (
                           WHERE DATE_TRUNC('month', competencia) = %s
                             AND despesa_fixa_id IS NOT NULL
                             AND data > %s
                       ) AS fixas_antecipadas_pendentes_qtd
                   FROM gastos
                   WHERE forma_pagamento_id = %s""",
                (comp_atual, hoje, comp_atual, comp_anterior, hoje, comp_atual, hoje, forma_id),
            )
            row = dict(cur.fetchone())

            ajuste_atual, motivo_atual = _get_ajuste(cur, forma_id, comp_atual)
            ajuste_anterior, motivo_anterior = _get_ajuste(cur, forma_id, comp_anterior)

            # fatura_anterior_paga (25/08/2026, achado via bot: "fatura
            # anterior a pagar" continuava aparecendo pro Lucas mesmo depois
            # de ele já ter marcado a fatura como paga no board de /contas —
            # mesma tabela que o board usa, faturas_pagamentos migração 027).
            cur.execute(
                "SELECT 1 FROM faturas_pagamentos "
                "WHERE forma_pagamento_id = %s AND competencia = %s",
                (forma_id, comp_anterior),
            )
            fatura_anterior_paga = cur.fetchone() is not None

        # Fora do `with conn.cursor()` de cima (projetar_despesas_fixas abre
        # cursores próprios), mas ainda dentro da conexão — mesma decisão de
        # services/contas_mes.py::_projecoes (reusar 1 conexão em vez de
        # abrir outra).
        previstas_cartao = [
            p for p in projetar_despesas_fixas(conn, gid, usuario_id, comp_atual.strftime("%Y-%m"))
            if p.get("forma_pagamento_id") == forma_id
        ]

    limite_mensal = float(forma["limite_mensal"]) if forma["limite_mensal"] else None
    fatura_atual_bruta = float(row["fatura_atual"])  # já com "chegou o dia" aplicado
    fatura_atual_bruta_sem_filtro = float(row["fatura_atual_sem_filtro_data"])
    fatura_anterior_bruta = float(row["fatura_anterior"])
    fatura_atual = fatura_atual_bruta + ajuste_atual
    fatura_anterior = fatura_anterior_bruta + ajuste_anterior
    total_previsto = sum(float(p["valor"]) for p in previstas_cartao)
    # Estimada = TUDO da competência (inclui despesa fixa antecipada que
    # ainda não chegou o dia de cobrar — por isso NÃO usa `fatura_atual`,
    # que já filtrou essas) + o que nem foi lançado ainda (total_previsto).
    fatura_atual_estimada = fatura_atual_bruta_sem_filtro + ajuste_atual + total_previsto
    venc_anterior = mes_vencimento(comp_anterior, forma.get("dia_fechamento"),
                                    forma.get("dia_vencimento"))

    # "Pendente" pro texto da tela (formas/page.jsx) cobre os DOIS jeitos de
    # uma despesa fixa ainda não pesar na fatura atual: nunca foi lançada
    # (previstas_cartao, projeção pura) OU já foi lançada antecipadamente
    # (passe 2 de despesas_fixas.py) mas o dia de cobrança ainda não chegou
    # (fixas_antecipadas_pendentes_qtd, linha real em `gastos`, só não conta
    # em fatura_atual ainda). Sem somar os dois, a 2ª categoria ficaria
    # invisível de novo — exatamente o bug original.
    fixas_pendentes_qtd = len(previstas_cartao) + int(row["fixas_antecipadas_pendentes_qtd"])

    return {
        "forma_id": forma_id,
        "nome": forma["nome"],
        "limite_mensal": limite_mensal,
        "fatura_atual": fatura_atual,
        "fatura_atual_bruta": fatura_atual_bruta,
        "fatura_atual_estimada": fatura_atual_estimada,
        "fixas_previstas_qtd": fixas_pendentes_qtd,
        "ajuste_fatura_atual": ajuste_atual,
        "ajuste_motivo_atual": motivo_atual,
        "limite_disponivel": (limite_mensal - fatura_atual) if limite_mensal is not None else None,
        "fatura_anterior": fatura_anterior,
        "fatura_anterior_bruta": fatura_anterior_bruta,
        "fatura_anterior_paga": fatura_anterior_paga,
        "ajuste_fatura_anterior": ajuste_anterior,
        "ajuste_motivo_anterior": motivo_anterior,
        "competencia_atual": comp_atual.isoformat(),
        "competencia_anterior": comp_anterior.isoformat(),
        "vencimento_fatura_anterior": venc_anterior.isoformat(),
    }


def definir_ajuste_fatura(usuario_id: int, forma_id: int, competencia: date,
                           valor_ajuste: float, motivo: str = None) -> dict | None:
    """
    Grava/atualiza o ajuste manual de uma fatura (competência específica —
    normalmente a atual, mas nada impede corrigir uma passada). Positivo
    soma, negativo desconta. Retorna None se a forma não é do usuário.
    """
    with get_conn() as conn:
        if not _forma_pertence_ao_usuario(conn, usuario_id, forma_id):
            return None
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO ajustes_fatura (forma_pagamento_id, competencia, valor_ajuste, motivo)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (forma_pagamento_id, competencia)
                   DO UPDATE SET valor_ajuste = EXCLUDED.valor_ajuste, motivo = EXCLUDED.motivo
                   RETURNING *""",
                (forma_id, competencia, valor_ajuste, motivo),
            )
            ajuste = dict(cur.fetchone())
            conn.commit()
            return ajuste


def remover_ajuste_fatura(usuario_id: int, forma_id: int, competencia: date) -> bool:
    with get_conn() as conn:
        if not _forma_pertence_ao_usuario(conn, usuario_id, forma_id):
            return False
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM ajustes_fatura WHERE forma_pagamento_id = %s AND competencia = %s "
                "RETURNING id",
                (forma_id, competencia),
            )
            deleted = cur.fetchone()
            conn.commit()
            return deleted is not None


def status_todos_cartoes(usuario_id: int) -> list[dict]:
    """status_cartao para toda forma com dia_fechamento (as sem — pix/
    débito/Custo Fixo — não têm fatura; ficam no saldo simples)."""
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    "SELECT id FROM formas_pagamento WHERE grupo_id = %s AND dia_fechamento IS NOT NULL "
                    "ORDER BY nome",
                    (gid,),
                )
            else:
                cur.execute(
                    "SELECT id FROM formas_pagamento WHERE usuario_id = %s AND grupo_id IS NULL "
                    "AND dia_fechamento IS NOT NULL ORDER BY nome",
                    (usuario_id,),
                )
            ids = [r["id"] for r in cur.fetchall()]

    return [status_cartao(usuario_id, fid) for fid in ids]
