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


def lancar_entradas_fixas_do_mes(hoje: date = None) -> list[dict]:
    """
    Lança como entrada normal toda entrada fixa ativa cujo dia efetivo JÁ
    CHEGOU neste mês (catch-up, mesma regra 18/07/2026 do lançador de
    despesas fixas: >= em vez de dia exato — processo fora do ar no dia não
    pode segurar o salário) e que ainda não foi lançada neste mês.
    Idempotente: checagem prévia + índice único uq_entrada_fixa_mes contra
    corrida (mesma dupla proteção de lancar_despesas_fixas_do_mes).
    """
    hoje = hoje or date.today()
    lancadas = []

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM entradas_fixas WHERE ativa = TRUE")
            fixas = [dict(r) for r in cur.fetchall()]

        for fixa in fixas:
            if hoje.day < _dia_efetivo(fixa["dia_lancamento"], hoje.year, hoje.month):
                continue

            with conn.cursor() as cur:
                cur.execute(
                    """SELECT 1 FROM entradas
                       WHERE entrada_fixa_id = %s
                         AND DATE_TRUNC('month', data) = DATE_TRUNC('month', %s::date)""",
                    (fixa["id"], hoje),
                )
                if cur.fetchone():
                    continue  # já lançada este mês

                try:
                    # data = dia DEVIDO, não o dia em que o catch-up rodou —
                    # o extrato deve mostrar o salário no dia em que ele cai.
                    data_devida = date(hoje.year, hoje.month,
                                        _dia_efetivo(fixa["dia_lancamento"], hoje.year, hoje.month))
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
                    lancadas.append(entrada)
                except psycopg.errors.UniqueViolation:
                    conn.rollback()
                    continue

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
