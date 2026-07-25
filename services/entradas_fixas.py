"""
services/entradas_fixas.py — entradas recorrentes (salário etc.), migração
023. Pedido do Lucas em 18/07/2026: "salário já é fixo e todo mês vai cair".

Espelho enxuto de services/despesas_fixas.py: tabela-modelo + lançador
mensal idempotente (índice único uq_entrada_fixa_mes como segunda camada,
mesma dupla proteção do lançador de despesas). Sem competência — entrada
usa `data` direto (salário não tem fatura), então o lançador é mais simples
que o de despesas: não há calcular_competencia envolvido.

O lançador roda no MESMO ciclo diário que já lança despesas fixas
(app.py::_loop_lancar_fixas_diario) — não é um segundo cron.

"Remover" é soft-delete (ativa = FALSE), pela mesma razão de
despesas_fixas: entradas.entrada_fixa_id referencia o modelo sem ON DELETE,
apagar de verdade quebraria FK assim que houvesse histórico lançado.
"""

import calendar
from datetime import date

import psycopg
from db import get_conn, _get_grupo_id
from services.competencia import somar_meses


def _dia_efetivo(dia_lancamento: int, ano: int, mes: int) -> int:
    """Capa o dia no último dia do mês (dia 31 em fevereiro → 28/29),
    mesma regra de despesas_fixas._dia_efetivo."""
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    return min(dia_lancamento, ultimo_dia)


def get_entradas_fixas(usuario_id: int, apenas_ativas: bool = True) -> list[dict]:
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            filtro_ativa = "AND ativa = TRUE" if apenas_ativas else ""
            if gid:
                cur.execute(
                    f"SELECT * FROM entradas_fixas WHERE grupo_id = %s {filtro_ativa} "
                    "ORDER BY dia_lancamento, descricao",
                    (gid,),
                )
            else:
                cur.execute(
                    f"SELECT * FROM entradas_fixas WHERE usuario_id = %s AND grupo_id IS NULL "
                    f"{filtro_ativa} ORDER BY dia_lancamento, descricao",
                    (usuario_id,),
                )
            return [dict(r) for r in cur.fetchall()]


def criar_entrada_fixa(usuario_id: int, descricao: str, valor: float,
                        dia_lancamento: int) -> dict:
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO entradas_fixas
                       (grupo_id, usuario_id, descricao, valor, dia_lancamento)
                   VALUES (%s, %s, %s, %s, %s)
                   RETURNING *""",
                (gid, usuario_id, descricao, valor, dia_lancamento),
            )
            conn.commit()
            return dict(cur.fetchone())


def desativar_entrada_fixa_por_id(usuario_id: int, fixa_id: int) -> bool:
    """Soft-delete (ver docstring do módulo)."""
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    "UPDATE entradas_fixas SET ativa = FALSE "
                    "WHERE id = %s AND grupo_id = %s AND ativa = TRUE RETURNING id",
                    (fixa_id, gid),
                )
            else:
                cur.execute(
                    "UPDATE entradas_fixas SET ativa = FALSE "
                    "WHERE id = %s AND usuario_id = %s AND grupo_id IS NULL AND ativa = TRUE "
                    "RETURNING id",
                    (fixa_id, usuario_id),
                )
            updated = cur.fetchone()
            conn.commit()
            return updated is not None


def definir_recorrencia_entrada(usuario_id: int, entrada_id: int, recorrente: bool,
                                  dia_lancamento: int = None) -> dict | None:
    """
    Liga/desliga a recorrência a partir de uma entrada existente (tela de
    editar — pedido do Lucas em 18/07/2026: o flag só existia no "novo
    lançamento").

    - recorrente=True, entrada sem modelo: cria o modelo em entradas_fixas
      com os dados ATUAIS da entrada (valor/descricao) e vincula
      (entrada_fixa_id) — o índice único impede o lançador de duplicar
      ainda este mês. Dia padrão: o dia da própria entrada.
    - recorrente=True, entrada já com modelo: reativa (se estava
      desativado) e sincroniza valor/descricao/dia com a entrada — editar o
      salário deste mês reajusta os próximos também; é o comportamento
      esperado pra "meu salário mudou". (Se um dia surgir demanda de "só a
      partir do mês que vem", copiar o padrão valor_pendente da migração
      017 — decidido NÃO fazer agora pra não repetir o over-engineering do
      limite rotativo.)
    - recorrente=False, entrada com modelo: desativa o modelo (soft-delete;
      a entrada continua vinculada pro histórico). Meses futuros param de
      cair.

    Retorna a entrada atualizada (com recorrente_ativa) ou None se ela não
    existe/não pertence ao usuário.
    """
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    "SELECT * FROM entradas WHERE id = %s AND grupo_id = %s",
                    (entrada_id, gid),
                )
            else:
                cur.execute(
                    "SELECT * FROM entradas WHERE id = %s AND usuario_id = %s AND grupo_id IS NULL",
                    (entrada_id, usuario_id),
                )
            entrada = cur.fetchone()
            if not entrada:
                return None
            entrada = dict(entrada)

            fixa_id = entrada.get("entrada_fixa_id")
            dia = dia_lancamento or (entrada["data"].day if entrada.get("data") else date.today().day)

            if recorrente and not fixa_id:
                cur.execute(
                    """INSERT INTO entradas_fixas
                           (grupo_id, usuario_id, descricao, valor, dia_lancamento)
                       VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                    (entrada["grupo_id"], entrada["usuario_id"],
                     entrada.get("descricao") or "", entrada["valor"], dia),
                )
                fixa_id = cur.fetchone()["id"]
                cur.execute(
                    "UPDATE entradas SET entrada_fixa_id = %s WHERE id = %s",
                    (fixa_id, entrada_id),
                )
            elif recorrente and fixa_id:
                cur.execute(
                    """UPDATE entradas_fixas
                       SET ativa = TRUE, valor = %s, descricao = %s, dia_lancamento = %s
                       WHERE id = %s""",
                    (entrada["valor"], entrada.get("descricao") or "", dia, fixa_id),
                )
            elif not recorrente and fixa_id:
                cur.execute(
                    "UPDATE entradas_fixas SET ativa = FALSE WHERE id = %s", (fixa_id,)
                )

            conn.commit()
            entrada["entrada_fixa_id"] = fixa_id if recorrente else entrada.get("entrada_fixa_id")
            entrada["recorrente_ativa"] = bool(recorrente and fixa_id)
            return entrada


def _inserir_lancamento(conn, fixa: dict, ano: int, mes: int) -> dict | None:
    """
    INSERT de 1 entrada fixa num mês específico — usado pelos dois passes
    do lançador. Retorna a entrada criada, ou None se aquele mês já tem
    lançamento (ou outro worker gunicorn ganhou a corrida —
    uq_entrada_fixa_mes, mesma dupla proteção de
    despesas_fixas.py::_inserir_lancamento: checagem prévia +
    try/except UniqueViolation).
    """
    data_devida = date(ano, mes, _dia_efetivo(fixa["dia_lancamento"], ano, mes))

    with conn.cursor() as cur:
        cur.execute(
            """SELECT 1 FROM entradas
               WHERE entrada_fixa_id = %s
                 AND DATE_TRUNC('month', data) = DATE_TRUNC('month', %s::date)""",
            (fixa["id"], data_devida),
        )
        if cur.fetchone():
            return None
        try:
            cur.execute(
                """INSERT INTO entradas
                       (usuario_id, grupo_id, descricao, valor, data, entrada_fixa_id)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   RETURNING *""",
                (fixa["usuario_id"], fixa["grupo_id"], fixa["descricao"],
                 fixa["valor"], data_devida, fixa["id"]),
            )
            entrada = dict(cur.fetchone())
            conn.commit()
            return entrada
        except psycopg.errors.UniqueViolation:
            conn.rollback()
            return None


def lancar_entradas_fixas_do_mes(hoje: date = None) -> list[dict]:
    """
    Dois passes por entrada fixa ativa — mesma estrutura de
    despesas_fixas.py::lancar_despesas_fixas_do_mes, adaptada (entrada não
    tem fatura/competência de cartão, só `data`).

    PASSE 1 — mês corrente: lança a entrada cujo dia efetivo JÁ CHEGOU
    (catch-up, hoje.day >= dia_efetivo — processo fora do ar no dia não pode
    segurar o salário) e ainda não foi lançada no mês.

    PASSE 2 — LANÇAMENTO ANTECIPADO (24/07/2026, achado ao investigar por
    que o board de /contas mostrava "Entradas: R$ 0,00" e "Sobra do mês"
    catastroficamente negativa ao navegar pro mês seguinte): garante que a
    entrada do MÊS SEGUINTE já exista como lançamento real, mesmo raciocínio
    do passe 2 de despesas_fixas ("já é certeza que vou pagar" vira, do lado
    da receita, "já é certeza que vou receber" — salário/VA recorrente não é
    uma previsão). Sem este passe, despesas fixas do mês seguinte já
    aparecem materializadas (graças ao passe 2 delas) mas entradas não —
    o board via só um lado antecipado e o outro não, fazendo "Sobra do mês"
    de um mês futuro parecer um rombo que não existe.

    Idempotente nos dois passes: checagem prévia + índice único
    uq_entrada_fixa_mes contra corrida (services/entradas_fixas
    ::_inserir_lancamento).
    """
    hoje = hoje or date.today()
    lancadas = []

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM entradas_fixas WHERE ativa = TRUE")
            fixas = [dict(r) for r in cur.fetchall()]

        for fixa in fixas:
            # ---- Passe 1: mês corrente (dia chegou) --------------------
            if hoje.day >= _dia_efetivo(fixa["dia_lancamento"], hoje.year, hoje.month):
                lancada = _inserir_lancamento(conn, fixa, hoje.year, hoje.month)
                if lancada:
                    lancadas.append(lancada)

            # ---- Passe 2: mês seguinte, antecipado ----------------------
            proximo = somar_meses(hoje.replace(day=1), 1)
            lancada = _inserir_lancamento(conn, fixa, proximo.year, proximo.month)
            if lancada:
                lancadas.append(lancada)

    return lancadas


def total_entradas_fixas_previstas(conn, gid: int | None, usuario_id: int,
                                     competencia_alvo: date) -> float:
    """
    Soma das entradas fixas ativas ainda NÃO lançadas no mês alvo — usada
    pelo resumo (previsão do mês, par do fixas_previstas de gastos).
    Retorna 0 pra mês passado: mês fechado nunca mistura previsto com real.
    Recebe conn aberta (chamada de dentro do resumo, 1 conexão só).
    """
    if competencia_alvo < date.today().replace(day=1):
        return 0.0

    with conn.cursor() as cur:
        if gid:
            cur.execute(
                """SELECT COALESCE(SUM(ef.valor), 0) AS total
                   FROM entradas_fixas ef
                   WHERE ef.grupo_id = %s AND ef.ativa = TRUE
                     AND NOT EXISTS (
                         SELECT 1 FROM entradas e
                         WHERE e.entrada_fixa_id = ef.id
                           AND DATE_TRUNC('month', e.data) = DATE_TRUNC('month', %s::date)
                     )""",
                (gid, competencia_alvo),
            )
        else:
            cur.execute(
                """SELECT COALESCE(SUM(ef.valor), 0) AS total
                   FROM entradas_fixas ef
                   WHERE ef.usuario_id = %s AND ef.grupo_id IS NULL AND ef.ativa = TRUE
                     AND NOT EXISTS (
                         SELECT 1 FROM entradas e
                         WHERE e.entrada_fixa_id = ef.id
                           AND DATE_TRUNC('month', e.data) = DATE_TRUNC('month', %s::date)
                     )""",
                (usuario_id, competencia_alvo),
            )
        return float(cur.fetchone()["total"])
