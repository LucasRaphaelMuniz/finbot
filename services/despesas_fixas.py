"""
services/despesas_fixas.py — despesas fixas recorrentes (Fase 3.3 do PLANO_EXECUCAO.md).

Uma despesa fixa é lançada automaticamente como um gasto normal todo mês, no
dia configurado (dia_lancamento), por `lancar_despesas_fixas_do_mes()` —
chamada pelo cron diário do Railway (jobs/lancar_fixas.py, decisão D4).

Ao contrário de categorias (Fase 3.1), `despesas_fixas` tem `usuario_id` além
de `grupo_id` (migração 004) — funciona tanto pra quem tem grupo quanto pra
conta individual, sem o gap que apareceu em categorias.

Decisão que vale destacar: "remover" é soft-delete (`ativa = FALSE`), não
DELETE. Motivo: uma vez que uma despesa fixa já lançou pelo menos um gasto,
`gastos.despesa_fixa_id` referencia essa linha sem ON DELETE CASCADE/SET NULL
(migração 004) — um DELETE de verdade quebraria com violação de FK assim que
houvesse histórico. A coluna `ativa` já existe no schema aprovado justamente
para isso; o lançador só considera `ativa = TRUE`.

Decisão que vale destacar: a competência do gasto lançado usa
`calcular_competencia()` (mesma função de compra avulsa e parcelamento —
Fase 3.2), não simplesmente o mês em que o lançador rodou. Isso importa pra
despesa fixa em cartão de crédito: uma assinatura com dia_lancamento depois
do dia_fechamento do cartão precisa cair na fatura do mês seguinte, senão o
gasto aparece atribuído a uma competência que já fechou. `dia_lancamento`
(quando o job CRIA o gasto) e `dia_fechamento` (em qual fatura/competência
esse gasto entra) são independentes — o primeiro vem de despesas_fixas, o
segundo da forma de pagamento vinculada, buscado via LEFT JOIN pra não
gerar 1 query extra por despesa fixa a cada rodada do cron.
"""

import calendar
from datetime import date

import psycopg
from db import get_conn, _get_grupo_id
from services.competencia import calcular_competencia


def get_despesas_fixas(usuario_id: int, apenas_ativas: bool = True) -> list[dict]:
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            filtro_ativa = "AND ativa = TRUE" if apenas_ativas else ""
            if gid:
                cur.execute(
                    f"SELECT * FROM despesas_fixas WHERE grupo_id = %s {filtro_ativa} "
                    "ORDER BY dia_lancamento, descricao",
                    (gid,),
                )
            else:
                cur.execute(
                    f"SELECT * FROM despesas_fixas WHERE usuario_id = %s AND grupo_id IS NULL "
                    f"{filtro_ativa} ORDER BY dia_lancamento, descricao",
                    (usuario_id,),
                )
            return [dict(r) for r in cur.fetchall()]


def criar_despesa_fixa(usuario_id: int, descricao: str, valor: float, dia_lancamento: int,
                        categoria_id: int = None, forma_pagamento_id: int = None) -> dict:
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO despesas_fixas
                       (grupo_id, usuario_id, categoria_id, forma_pagamento_id,
                        descricao, valor, dia_lancamento)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   RETURNING *""",
                (gid, usuario_id, categoria_id, forma_pagamento_id, descricao, valor, dia_lancamento),
            )
            conn.commit()
            return dict(cur.fetchone())


def desativar_despesa_fixa(usuario_id: int, descricao: str) -> bool:
    """Soft-delete: marca ativa=False. Não lança mais, mas preserva o histórico já lançado."""
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    "UPDATE despesas_fixas SET ativa = FALSE "
                    "WHERE grupo_id = %s AND ativa = TRUE AND LOWER(descricao) LIKE %s RETURNING id",
                    (gid, f"%{descricao.lower()}%"),
                )
            else:
                cur.execute(
                    "UPDATE despesas_fixas SET ativa = FALSE "
                    "WHERE usuario_id = %s AND grupo_id IS NULL AND ativa = TRUE "
                    "AND LOWER(descricao) LIKE %s RETURNING id",
                    (usuario_id, f"%{descricao.lower()}%"),
                )
            updated = cur.fetchone()
            conn.commit()
            return updated is not None


def _dia_efetivo(dia_lancamento: int, ano: int, mes: int) -> int:
    """
    Capa o dia de lançamento no último dia do mês — ex.: dia_lancamento=31 em
    fevereiro lança no dia 28 (ou 29 em ano bissexto), em vez de nunca lançar
    naquele mês porque ele não tem dia 31.
    """
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    return min(dia_lancamento, ultimo_dia)


def _valor_efetivo(fixa: dict, hoje: date) -> tuple[float, bool]:
    """
    Resolve o valor que deve ser lançado pra essa fixa hoje, considerando
    reajuste "só a partir do próximo mês" (valor_pendente, migração 017).
    Retorna (valor, usar_pendente) — usar_pendente=True sinaliza que quem
    chamar precisa promover valor_pendente -> valor depois do INSERT
    (ver lancar_despesas_fixas_do_mes e confirmar_lancamento_fixa, os dois
    usam essa mesma função pra não divergir a regra em dois lugares).
    """
    valor_pendente = fixa.get("valor_pendente")
    protegido_ate = fixa.get("valor_pendente_a_partir")
    usar_pendente = (
        valor_pendente is not None and protegido_ate is not None and hoje > protegido_ate
    )
    return (valor_pendente if usar_pendente else fixa["valor"]), usar_pendente


def confirmar_lancamento_fixa(usuario_id: int, fixa_id: int, competencia_str: str) -> dict | None:
    """
    Lançamento MANUAL de uma despesa fixa pra uma competência específica —
    botão "Confirmar" nas linhas "previsto" de Lançamentos (front). Existe
    porque `lancar_despesas_fixas_do_mes` só lança no dia exato do mês
    (`hoje.day == dia_efetivo`) — se o cron ficou dias/semanas sem rodar
    (ex: nunca foi configurado no Railway, caso real do Lucas em 16/07/2026),
    não tem catch-up automático pros dias que já passaram; a pessoa fica
    vendo "previsto" pra sempre até confirmar na mão. Reaproveita a mesma
    checagem de idempotência (índice único uq_despesa_fixa_mes) e a mesma
    regra de valor_pendente que o cron usa (`_valor_efetivo`), pra não ter
    duas fontes de verdade pro "quanto lançar".

    `data` do gasto criado é hoje (quando a pessoa efetivamente confirmou),
    não o dia_lancamento original — a competência (o mês que ele conta pro
    orçamento) é a que foi pedida, essas duas coisas são independentes desde
    sempre no resto do sistema (ver services/competencia.py).
    """
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    """SELECT f.*, fp.dia_fechamento, fp.dia_vencimento
                       FROM despesas_fixas f
                       LEFT JOIN formas_pagamento fp ON fp.id = f.forma_pagamento_id
                       WHERE f.id = %s AND f.grupo_id = %s AND f.ativa = TRUE""",
                    (fixa_id, gid),
                )
            else:
                cur.execute(
                    """SELECT f.*, fp.dia_fechamento, fp.dia_vencimento
                       FROM despesas_fixas f
                       LEFT JOIN formas_pagamento fp ON fp.id = f.forma_pagamento_id
                       WHERE f.id = %s AND f.usuario_id = %s AND f.grupo_id IS NULL AND f.ativa = TRUE""",
                    (fixa_id, usuario_id),
                )
            fixa = cur.fetchone()
            if not fixa:
                return None
            fixa = dict(fixa)

            competencia = date(*(int(p) for p in competencia_str.split("-")[:2]), 1)
            hoje = date.today()
            valor_lancado, usar_pendente = _valor_efetivo(fixa, hoje)

            cur.execute(
                """SELECT 1 FROM gastos
                   WHERE despesa_fixa_id = %s
                     AND DATE_TRUNC('month', competencia) = DATE_TRUNC('month', %s::date)""",
                (fixa_id, competencia),
            )
            if cur.fetchone():
                return None  # já foi lançada (por confirmação anterior ou pelo cron) — nada a fazer

            try:
                cur.execute(
                    """INSERT INTO gastos
                           (usuario_id, forma_pagamento_id, categoria_id, valor, descricao,
                            grupo_id, competencia, despesa_fixa_id, data)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING *""",
                    (fixa["usuario_id"], fixa["forma_pagamento_id"], fixa["categoria_id"],
                     valor_lancado, fixa["descricao"], fixa["grupo_id"], competencia, fixa_id, hoje),
                )
                gasto = dict(cur.fetchone())
                if usar_pendente:
                    cur.execute(
                        "UPDATE despesas_fixas SET valor = %s, valor_pendente = NULL, "
                        "valor_pendente_a_partir = NULL WHERE id = %s",
                        (fixa["valor_pendente"], fixa_id),
                    )
                conn.commit()
                return gasto
            except psycopg.errors.UniqueViolation:
                conn.rollback()
                return None


def lancar_despesas_fixas_do_mes(hoje: date = None) -> list[dict]:
    """
    Lança como gasto normal toda despesa fixa ativa cujo dia efetivo de
    lançamento é hoje, e que ainda não foi lançada nessa competência.

    Idempotente: chamar de novo no mesmo dia não duplica — checagem prévia
    (SELECT) mais o índice único uq_despesa_fixa_mes como segunda camada de
    proteção contra corrida (2 execuções do cron sobrepostas, por exemplo).
    Pensada pra rodar 1x/dia via cron (jobs/lancar_fixas.py, decisão D4).
    """
    hoje = hoje or date.today()
    lancados = []

    with get_conn() as conn:
        with conn.cursor() as cur:
            # LEFT JOIN pra trazer dia_fechamento/dia_vencimento da forma de
            # pagamento junto (evita 1 SELECT extra por despesa fixa dentro
            # do loop). Despesa fixa sem forma_pagamento_id, ou com forma
            # sem dia_fechamento (pix/débito/Custo Fixo), cai em
            # dia_fechamento NULL — calcular_competencia trata isso como
            # "sem cartão", mesma regra de compra avulsa.
            cur.execute(
                """SELECT f.*, fp.dia_fechamento, fp.dia_vencimento
                   FROM despesas_fixas f
                   LEFT JOIN formas_pagamento fp ON fp.id = f.forma_pagamento_id
                   WHERE f.ativa = TRUE"""
            )
            fixas = [dict(r) for r in cur.fetchall()]

        for fixa in fixas:
            dia_efetivo = _dia_efetivo(fixa["dia_lancamento"], hoje.year, hoje.month)
            if hoje.day != dia_efetivo:
                continue

            competencia = calcular_competencia(hoje, fixa.get("dia_fechamento"), fixa.get("dia_vencimento"))
            valor_lancado, usar_pendente = _valor_efetivo(fixa, hoje)

            with conn.cursor() as cur:
                cur.execute(
                    """SELECT 1 FROM gastos
                       WHERE despesa_fixa_id = %s
                         AND DATE_TRUNC('month', competencia) = DATE_TRUNC('month', %s::date)""",
                    (fixa["id"], competencia),
                )
                if cur.fetchone():
                    continue  # já lançada essa competência

                try:
                    cur.execute(
                        """INSERT INTO gastos
                               (usuario_id, forma_pagamento_id, categoria_id, valor, descricao,
                                grupo_id, competencia, despesa_fixa_id)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                           RETURNING *""",
                        (fixa["usuario_id"], fixa["forma_pagamento_id"], fixa["categoria_id"],
                         valor_lancado, fixa["descricao"], fixa["grupo_id"], competencia, fixa["id"]),
                    )
                    gasto = dict(cur.fetchone())
                    if usar_pendente:
                        cur.execute(
                            "UPDATE despesas_fixas SET valor = %s, valor_pendente = NULL, "
                            "valor_pendente_a_partir = NULL WHERE id = %s",
                            (valor_lancado, fixa["id"]),
                        )
                    conn.commit()
                    lancados.append(gasto)
                except psycopg.errors.UniqueViolation:
                    conn.rollback()
                    continue

    return lancados



# ---------------------------------------------------------------------------
# Operações por id (Fase 4.3 — API web, PUT/DELETE /api/fixas/:id)
# Mesmo raciocínio de services/categorias.py: bot busca por descrição
# (fuzzy), web já tem o id exato.
# ---------------------------------------------------------------------------

def atualizar_despesa_fixa(usuario_id: int, fixa_id: int, descricao: str = None,
                            valor: float = None, dia_lancamento: int = None,
                            categoria_id: int = None, forma_pagamento_id: int = None,
                            aplicar_a_partir: str = "imediato") -> dict | None:
    """
    `aplicar_a_partir` só importa quando `valor` está sendo alterado
    (migração 017):

    - "imediato" (padrão): grava valor direto, igual sempre fez. Se o
      dia_lancamento deste mês ainda não passou, o lançamento iminente
      também sai com o valor novo — mesmo comportamento de sempre.
    - "proximo_mes": NÃO toca em `valor` agora — o valor novo fica em
      valor_pendente até passar da data do lançamento iminente deste mês
      (protegido com o valor antigo). `lancar_despesas_fixas_do_mes()`
      promove valor_pendente -> valor assim que essa data passar. Só faz
      sentido pedir isso quando o dia_lancamento deste mês ainda não
      passou — depois disso "imediato" e "proximo_mes" dão no mesmo
      resultado (o front não oferece a escolha nesse caso).
    """
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        sets, params = [], []
        for campo, valor_campo in (
            ("descricao", descricao), ("dia_lancamento", dia_lancamento),
            ("categoria_id", categoria_id), ("forma_pagamento_id", forma_pagamento_id),
        ):
            if valor_campo is not None:
                sets.append(f"{campo} = %s")
                params.append(valor_campo)

        if valor is not None:
            if aplicar_a_partir == "proximo_mes":
                with conn.cursor() as cur:
                    if gid:
                        cur.execute(
                            "SELECT dia_lancamento FROM despesas_fixas WHERE id = %s AND grupo_id = %s",
                            (fixa_id, gid),
                        )
                    else:
                        cur.execute(
                            "SELECT dia_lancamento FROM despesas_fixas "
                            "WHERE id = %s AND usuario_id = %s AND grupo_id IS NULL",
                            (fixa_id, usuario_id),
                        )
                    row = cur.fetchone()
                if not row:
                    return None
                dia_base = dia_lancamento if dia_lancamento is not None else row["dia_lancamento"]
                hoje = date.today()
                protegido_ate = date(hoje.year, hoje.month, _dia_efetivo(dia_base, hoje.year, hoje.month))
                sets.append("valor_pendente = %s")
                params.append(valor)
                sets.append("valor_pendente_a_partir = %s")
                params.append(protegido_ate)
            else:
                sets.append("valor = %s")
                params.append(valor)
                # Reajuste imediato cancela qualquer reajuste "pra depois"
                # que estivesse na fila — evita 2 mudanças de valor
                # disputando o mesmo lançamento futuro.
                sets.append("valor_pendente = NULL")
                sets.append("valor_pendente_a_partir = NULL")

        if not sets:
            return None

        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    f"UPDATE despesas_fixas SET {', '.join(sets)} "
                    "WHERE id = %s AND grupo_id = %s RETURNING *",
                    params + [fixa_id, gid],
                )
            else:
                cur.execute(
                    f"UPDATE despesas_fixas SET {', '.join(sets)} "
                    "WHERE id = %s AND usuario_id = %s AND grupo_id IS NULL RETURNING *",
                    params + [fixa_id, usuario_id],
                )
            row = cur.fetchone()
            conn.commit()
            return dict(row) if row else None


def desativar_despesa_fixa_por_id(usuario_id: int, fixa_id: int) -> bool:
    """Soft-delete por id (mesma razão da versão por descrição usada pelo
    bot: gastos.despesa_fixa_id não tem ON DELETE CASCADE/SET NULL)."""
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    "UPDATE despesas_fixas SET ativa = FALSE "
                    "WHERE id = %s AND grupo_id = %s AND ativa = TRUE RETURNING id",
                    (fixa_id, gid),
                )
            else:
                cur.execute(
                    "UPDATE despesas_fixas SET ativa = FALSE "
                    "WHERE id = %s AND usuario_id = %s AND grupo_id IS NULL AND ativa = TRUE RETURNING id",
                    (fixa_id, usuario_id),
                )
            updated = cur.fetchone()
            conn.commit()
            return updated is not None
