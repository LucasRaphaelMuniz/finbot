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
from services.competencia import calcular_competencia, somar_meses


def get_despesas_fixas(usuario_id: int, apenas_ativas: bool = True) -> list[dict]:
    # `lancadas` (subquery em gastos) alimenta o "12/48" das fixas com
    # prazo (parcelas_total, migração 025) na tela de Despesas fixas.
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            filtro_ativa = "AND ativa = TRUE" if apenas_ativas else ""
            if gid:
                cur.execute(
                    f"""SELECT f.*,
                               (SELECT COUNT(*) FROM gastos g WHERE g.despesa_fixa_id = f.id)
                                   AS lancadas
                        FROM despesas_fixas f WHERE grupo_id = %s {filtro_ativa}
                        ORDER BY dia_lancamento, descricao""",
                    (gid,),
                )
            else:
                cur.execute(
                    f"""SELECT f.*,
                               (SELECT COUNT(*) FROM gastos g WHERE g.despesa_fixa_id = f.id)
                                   AS lancadas
                        FROM despesas_fixas f WHERE usuario_id = %s AND grupo_id IS NULL
                        {filtro_ativa} ORDER BY dia_lancamento, descricao""",
                    (usuario_id,),
                )
            return [dict(r) for r in cur.fetchall()]


def criar_despesa_fixa(usuario_id: int, descricao: str, valor: float, dia_lancamento: int,
                        categoria_id: int = None, forma_pagamento_id: int = None,
                        parcelas_total: int = None) -> dict:
    """parcelas_total (migração 025): fixa com prazo — financiamento,
    consórcio. NULL = sem fim (aluguel, internet)."""
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO despesas_fixas
                       (grupo_id, usuario_id, categoria_id, forma_pagamento_id,
                        descricao, valor, dia_lancamento, parcelas_total)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING *""",
                (gid, usuario_id, categoria_id, forma_pagamento_id, descricao, valor,
                 dia_lancamento, parcelas_total),
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


def buscar_supressoes(conn, a_partir_de: date) -> set:
    """
    (despesa_fixa_id, competência-1º-do-mês) que o usuário excluiu de
    propósito (migração 026, ver comentário lá). Usada pelo lançador (não
    recriar o que foi excluído) e pela projeção em services/gastos.py (não
    voltar a mostrar como "previsto" o que foi excluído).
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT despesa_fixa_id, competencia FROM despesas_fixas_supressoes "
            "WHERE competencia >= %s",
            (a_partir_de,),
        )
        return {(r["despesa_fixa_id"], r["competencia"]) for r in cur.fetchall()}


def _inserir_lancamento(conn, fixa: dict, data_devida: date, competencia: date,
                         valor: float) -> dict | None:
    """
    INSERT de um lançamento de fixa — usado pelos dois passes do lançador.
    Retorna o gasto criado, ou None se a competência já tem lançamento (ou
    outro worker gunicorn ganhou a corrida — uq_despesa_fixa_mes).

    `data` explícita = dia devido (antes ficava no DEFAULT NOW()): pro
    lançamento antecipado é obrigatório (a linha de agosto tem que exibir a
    data de agosto, não o dia em que o cron rodou em julho) e pro catch-up
    é mais honesto (fixa do dia 5 lançada dia 20 por atraso do processo
    aparece datada do dia 5, coerente com a competência que já era
    calculada a partir do dia devido).
    """
    with conn.cursor() as cur:
        cur.execute(
            """SELECT 1 FROM gastos
               WHERE despesa_fixa_id = %s
                 AND DATE_TRUNC('month', competencia) = DATE_TRUNC('month', %s::date)""",
            (fixa["id"], competencia),
        )
        if cur.fetchone():
            return None
        try:
            cur.execute(
                """INSERT INTO gastos
                       (usuario_id, forma_pagamento_id, categoria_id, valor, descricao,
                        grupo_id, competencia, despesa_fixa_id, data)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING *""",
                (fixa["usuario_id"], fixa["forma_pagamento_id"], fixa["categoria_id"],
                 valor, fixa["descricao"], fixa["grupo_id"], competencia, fixa["id"],
                 data_devida),
            )
            gasto = dict(cur.fetchone())
            conn.commit()
            return gasto
        except psycopg.errors.UniqueViolation:
            conn.rollback()
            return None


def lancar_despesas_fixas_do_mes(hoje: date = None) -> list[dict]:
    """
    Dois passes por despesa fixa ativa:

    PASSE 1 — mês corrente: lança a fixa cujo dia efetivo JÁ CHEGOU
    (hoje.day >= dia_efetivo) e ainda não tem lançamento na competência.

    CATCH-UP (18/07/2026, pedido do Lucas: "não quero confirmar custos
    fixos — se são fixos, serão fixos TODOS os meses"): antes a condição
    era dia EXATO (hoje.day == dia_efetivo) — se o processo estivesse fora
    do ar naquele dia, a fixa ficava "previsto" pra sempre esperando o
    botão Confirmar (que existia como muleta pra esse gap e foi removido
    junto com esta mudança). Com >=, qualquer execução posterior no mês
    lança o que ficou pra trás; a idempotência (checagem prévia + índice
    único uq_despesa_fixa_mes) já impedia duplicar. O lançador também roda
    na subida do processo (app.py), não só às 6h.

    PASSE 2 — LANÇAMENTO ANTECIPADO (18/07/2026, pedido do Lucas: "não
    quero os lançamentos futuros como previsto — é certeza que vou pagar,
    quero igual compra parcelada"): garante que a competência do MÊS
    SEGUINTE já exista como gasto real, sem esperar o dia. A linha vira
    normal na web (editável/excluível) em vez da sintética "fixa
    (previsto)"; a projeção (services/gastos.py) segue cobrindo meses além
    desse horizonte de 1 mês. A data de lançamento é escolhida pela MESMA
    regra de candidatos da projeção: a data cuja calcular_competencia cai
    na competência-alvo (fixa em cartão com dia_lancamento após o
    fechamento tem data no mês anterior ao da competência).

    Exclusão manual de um lançamento (deste mês ou do antecipado) NÃO é
    recriada: services/gastos.py::remover_gasto grava a supressão
    (migração 026) e os dois passes pulam a combinação fixa+competência.

    Fixa com prazo (parcelas_total, migração 025): desativa sozinha ao
    atingir o total. A contagem sai de `gastos` — parcela excluída SEM
    supressão de mês (caso raro: exclusão de mês passado) reabre a vaga.
    O passe 2 não antecipa a ÚLTIMA parcela se a competência corrente
    ainda estiver pendente — senão a parcela final pularia um mês.

    valor_pendente (reajuste "a partir do próximo mês", migração 017): o
    passe 2 usa o valor pendente quando a data devida antecipada passa da
    data protegida, mas NÃO promove (promover cedo demais contaminaria o
    lançamento protegido do mês corrente); a promoção é do passe 1 e
    acontece mesmo quando o gasto já existe (com o antecipado, o INSERT do
    mês corrente quase sempre já aconteceu um mês antes — se a promoção
    continuasse presa ao INSERT, o pendente nunca seria promovido).
    """
    hoje = hoje or date.today()
    mes_corrente = hoje.replace(day=1)
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
                """SELECT f.*, fp.dia_fechamento, fp.dia_vencimento,
                          (SELECT COUNT(*) FROM gastos g WHERE g.despesa_fixa_id = f.id)
                              AS lancadas
                   FROM despesas_fixas f
                   LEFT JOIN formas_pagamento fp ON fp.id = f.forma_pagamento_id
                   WHERE f.ativa = TRUE"""
            )
            fixas = [dict(r) for r in cur.fetchall()]

        suprimidas = buscar_supressoes(conn, mes_corrente)

        for fixa in fixas:
            # Prazo já cumprido (fixa parcelada tipo financiamento) — não
            # lança mais e garante a desativação (cinto e suspensório: o
            # normal é já ter sido desativada no lançamento da última).
            if fixa.get("parcelas_total") and fixa["lancadas"] >= fixa["parcelas_total"]:
                with conn.cursor() as cur:
                    cur.execute("UPDATE despesas_fixas SET ativa = FALSE WHERE id = %s", (fixa["id"],))
                    conn.commit()
                continue

            dia_efetivo = _dia_efetivo(fixa["dia_lancamento"], hoje.year, hoje.month)
            # Competência calculada a partir do DIA DEVIDO, não do dia em
            # que o catch-up rodou — lançar dia 20 uma fixa do dia 5 num
            # cartão que fecha dia 10 tem que cair na fatura que fecharia
            # pro dia 5, senão o atraso do processo mudaria a fatura.
            data_devida = date(hoje.year, hoje.month, dia_efetivo)
            competencia_corrente = calcular_competencia(data_devida, fixa.get("dia_fechamento"))

            # ---- Passe 1: mês corrente (dia chegou) --------------------
            if hoje.day >= dia_efetivo:
                valor_lancado, usar_pendente = _valor_efetivo(fixa, hoje)

                gasto = None
                if (fixa["id"], competencia_corrente) not in suprimidas:
                    gasto = _inserir_lancamento(
                        conn, fixa, data_devida, competencia_corrente, valor_lancado
                    )

                if usar_pendente or gasto:
                    with conn.cursor() as cur:
                        if usar_pendente:
                            cur.execute(
                                "UPDATE despesas_fixas SET valor = %s, valor_pendente = NULL, "
                                "valor_pendente_a_partir = NULL WHERE id = %s",
                                (valor_lancado, fixa["id"]),
                            )
                            fixa["valor"] = valor_lancado
                            fixa["valor_pendente"] = None
                            fixa["valor_pendente_a_partir"] = None
                        if gasto:
                            fixa["lancadas"] += 1
                            lancados.append(gasto)
                            if fixa.get("parcelas_total") and fixa["lancadas"] >= fixa["parcelas_total"]:
                                cur.execute(
                                    "UPDATE despesas_fixas SET ativa = FALSE WHERE id = %s",
                                    (fixa["id"],),
                                )
                                fixa["ativa"] = False
                        conn.commit()

            # ---- Passe 2: competência do mês seguinte, antecipada ------
            if not fixa["ativa"]:
                continue
            prox_competencia = somar_meses(mes_corrente, 1)

            if fixa.get("parcelas_total"):
                restantes = fixa["parcelas_total"] - fixa["lancadas"]
                if restantes <= 0:
                    continue
                if restantes == 1 and competencia_corrente != prox_competencia:
                    # Última parcela: se a competência corrente ainda não foi
                    # lançada nem suprimida, o slot final é dela — antecipar
                    # faria a última parcela pular um mês. (Quando a
                    # competência do dia devido deste mês JÁ É a do mês
                    # seguinte — cartão com lançamento após o fechamento —
                    # antecipar é o mesmo slot, sem conflito.)
                    if (fixa["id"], competencia_corrente) not in suprimidas:
                        with conn.cursor() as cur:
                            cur.execute(
                                """SELECT 1 FROM gastos
                                   WHERE despesa_fixa_id = %s
                                     AND DATE_TRUNC('month', competencia) = DATE_TRUNC('month', %s::date)""",
                                (fixa["id"], competencia_corrente),
                            )
                            if not cur.fetchone():
                                continue

            if (fixa["id"], prox_competencia) in suprimidas:
                continue

            # Mesma regra de candidatos da projeção: acha a data de
            # lançamento cuja competência cai no mês-alvo.
            data_antecipada = None
            for ano_c, mes_c in ((prox_competencia.year, prox_competencia.month),
                                 (hoje.year, hoje.month)):
                dia_c = _dia_efetivo(fixa["dia_lancamento"], ano_c, mes_c)
                candidata = date(ano_c, mes_c, dia_c)
                if calcular_competencia(candidata, fixa.get("dia_fechamento")) == prox_competencia:
                    data_antecipada = candidata
                    break
            if not data_antecipada:
                continue

            # Reajuste "próximo mês": usa o pendente se a data devida passa
            # da protegida, mas quem promove é só o passe 1 (ver docstring).
            valor_antecipado, _ = _valor_efetivo(fixa, data_antecipada)
            gasto = _inserir_lancamento(
                conn, fixa, data_antecipada, prox_competencia, valor_antecipado
            )
            if gasto:
                fixa["lancadas"] += 1
                lancados.append(gasto)
                if fixa.get("parcelas_total") and fixa["lancadas"] >= fixa["parcelas_total"]:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE despesas_fixas SET ativa = FALSE WHERE id = %s", (fixa["id"],)
                        )
                        conn.commit()

    return lancados



# ---------------------------------------------------------------------------
# Operações por id (Fase 4.3 — API web, PUT/DELETE /api/fixas/:id)
# Mesmo raciocínio de services/categorias.py: bot busca por descrição
# (fuzzy), web já tem o id exato.
# ---------------------------------------------------------------------------

def atualizar_despesa_fixa(usuario_id: int, fixa_id: int, descricao: str = None,
                            valor: float = None, dia_lancamento: int = None,
                            categoria_id: int = None, forma_pagamento_id: int = None,
                            parcelas_total: int = None,
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

    PROPAGAÇÃO (18/07/2026, junto com o lançamento antecipado): com o
    passe 2 do lançador, o gasto do mês seguinte já existe de verdade
    quando o reajuste chega — sem propagar, "a partir do próximo mês"
    viraria "a partir do mês seguinte ao que já foi materializado". Então,
    ao mudar `valor`, os lançamentos FUTUROS dessa fixa (data > hoje no
    "imediato"; data > data protegida no "proximo_mes") são atualizados
    junto. Efeito colateral assumido: se o usuário tinha editado à mão o
    valor de um desses gastos futuros, o reajuste da fixa sobrescreve — o
    cadastro da fixa é a fonte de verdade do que ainda não venceu.
    """
    propagar_valor_apos = None  # data a partir da qual gastos futuros recebem o valor novo
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        sets, params = [], []
        for campo, valor_campo in (
            ("descricao", descricao), ("dia_lancamento", dia_lancamento),
            ("categoria_id", categoria_id), ("forma_pagamento_id", forma_pagamento_id),
            ("parcelas_total", parcelas_total),
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
                propagar_valor_apos = protegido_ate
            else:
                sets.append("valor = %s")
                params.append(valor)
                # Reajuste imediato cancela qualquer reajuste "pra depois"
                # que estivesse na fila — evita 2 mudanças de valor
                # disputando o mesmo lançamento futuro.
                sets.append("valor_pendente = NULL")
                sets.append("valor_pendente_a_partir = NULL")
                propagar_valor_apos = date.today()

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
            if row and propagar_valor_apos is not None:
                # Ver "PROPAGAÇÃO" na docstring. O WHERE por data (> hoje /
                # > protegida) em vez de competência é proposital: no
                # "proximo_mes", o lançamento antecipado de fixa em cartão
                # pode ter competência futura mas data DENTRO da janela
                # protegida — esse tem que manter o valor antigo.
                cur.execute(
                    "UPDATE gastos SET valor = %s WHERE despesa_fixa_id = %s AND data > %s",
                    (valor, fixa_id, propagar_valor_apos),
                )
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
