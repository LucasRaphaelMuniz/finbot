import os
from datetime import date
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

from services.competencia import calcular_competencia, dia_regra

load_dotenv()

# ---------------------------------------------------------------------------
# Conexão
# ---------------------------------------------------------------------------

def get_conn():
    return psycopg.connect(os.getenv("DATABASE_URL"), row_factory=dict_row)


FORMAS_PADRAO = [
    ("Cartão",       3000.00),
    ("Pix/Dinheiro", 1500.00),
    ("Ticket",        600.00),
]

# ---------------------------------------------------------------------------
# Helper interno
# ---------------------------------------------------------------------------

def _get_grupo_id(conn, usuario_id: int):
    with conn.cursor() as cur:
        cur.execute("SELECT grupo_id FROM usuarios WHERE id = %s", (usuario_id,))
        row = cur.fetchone()
        return row["grupo_id"] if row else None


def _get_dia_corte(conn, usuario_id: int) -> int | None:
    """dia_corte (migração 028) — "dia do pagamento" do usuário, usado como
    fallback de calcular_competencia pra tudo que não é cartão (ver
    services/competencia.py::dia_regra). DEFAULT 25 na coluna, então isto só
    volta None se o usuário não existir."""
    with conn.cursor() as cur:
        cur.execute("SELECT dia_corte FROM usuarios WHERE id = %s", (usuario_id,))
        row = cur.fetchone()
        return row["dia_corte"] if row else None


# ---------------------------------------------------------------------------
# Usuários
# ---------------------------------------------------------------------------

def get_or_create_usuario(telefone: str):
    """Retorna (usuario_dict, is_new). Cria formas de pagamento padrão no 1.º acesso.

    Sentido inverso web->bot (Fase B5 do AUDITORIA_E_PLANO_CADASTRO.md): se
    a pessoa criou conta pelo web primeiro e só depois manda mensagem no
    WhatsApp, este SELECT já encontra o registro criado pela web — não
    precisou de nenhum código novo pra esse caminho, só da normalização
    única de telefone (Fase A). Antes da Fase A isso não funcionava: a web
    salvava telefone cru e o `telefone` recebido aqui (vindo de
    app.py:_normalizar_jid) já era sempre JID — nunca batiam."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM usuarios WHERE telefone = %s", (telefone,))
            usuario = cur.fetchone()
            if usuario:
                return dict(usuario), False

            cur.execute(
                "INSERT INTO usuarios (nome, telefone) VALUES (%s, %s) RETURNING *",
                (telefone, telefone),
            )
            novo = dict(cur.fetchone())
            uid = novo["id"]

            for nome, limite in FORMAS_PADRAO:
                cur.execute(
                    "INSERT INTO formas_pagamento (usuario_id, nome, limite_mensal) "
                    "VALUES (%s, %s, %s)",
                    (uid, nome, limite),
                )

            conn.commit()
            return novo, True


def get_usuario(usuario_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM usuarios WHERE id = %s", (usuario_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def set_nome_usuario(usuario_id: int, nome: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE usuarios SET nome = %s WHERE id = %s", (nome, usuario_id))
            conn.commit()


def set_parceiro_telefone(usuario_id: int, telefone: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE usuarios SET parceiro_telefone = %s WHERE id = %s",
                (telefone, usuario_id),
            )
            conn.commit()


# ---------------------------------------------------------------------------
# Formas de pagamento
# (categorias por grupo migraram para services/categorias.py — Fase 3.1)
# ---------------------------------------------------------------------------

def get_formas_pagamento(usuario_id: int):
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    "SELECT * FROM formas_pagamento WHERE grupo_id = %s ORDER BY nome",
                    (gid,),
                )
            else:
                cur.execute(
                    "SELECT * FROM formas_pagamento WHERE usuario_id = %s AND grupo_id IS NULL ORDER BY nome",
                    (usuario_id,),
                )
            return [dict(r) for r in cur.fetchall()]


def adicionar_forma_pagamento(usuario_id: int, nome: str, limite: float = None):
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO formas_pagamento (usuario_id, grupo_id, nome, limite_mensal) VALUES (%s, %s, %s, %s)",
                (usuario_id, gid, nome, limite),
            )
            conn.commit()


def remover_forma_pagamento(usuario_id: int, nome_forma: str) -> bool:
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    "DELETE FROM formas_pagamento WHERE grupo_id = %s AND LOWER(nome) LIKE %s RETURNING id",
                    (gid, f"%{nome_forma.lower()}%"),
                )
            else:
                cur.execute(
                    "DELETE FROM formas_pagamento WHERE usuario_id = %s AND grupo_id IS NULL AND LOWER(nome) LIKE %s RETURNING id",
                    (usuario_id, f"%{nome_forma.lower()}%"),
                )
            deleted = cur.fetchone()
            conn.commit()
            return deleted is not None


# ---------------------------------------------------------------------------
# Gastos
# ---------------------------------------------------------------------------

def registrar_gasto(usuario_id: int, forma_id: int, categoria_id: int,
                    valor: float, descricao: str, grupo_id: int = None,
                    dia_fechamento: int = None, data: date = None):
    """
    dia_fechamento: dia de fechamento da forma de pagamento usada (Fase 3.2),
    usado para calcular a competência (mês da fatura) do gasto — ver
    services/competencia.py. Sem dia_fechamento (pix/dinheiro/ticket), a
    competência é o mês corrente. O mês de PAGAMENTO da fatura
    (dia_vencimento, migração 019) não entra aqui — é assunto do caixa
    (services/resumo.py), não do gasto individual (decisão revista em
    17-18/07/2026, ver nota em services/competencia.py).

    data: data de referência do gasto (03/08/2026, pedido do Lucas — "...
    01-08" no fim da mensagem registra com data 01/08, não hoje, ver
    parser.extrair_data). Default hoje. Usada tanto na coluna `data` quanto
    no cálculo da competência — sem isso, corrigir a data na hora de
    registrar não moveria a fatura a que o gasto pertence (mesmo raciocínio
    de services/gastos.py::atualizar_gasto ao editar depois).

    Sem dia_fechamento (não é cartão), a competência cai pro dia_corte do
    usuário em vez do mês calendário puro — migração 028, pedido do Lucas em
    25/08/2026 ("recebo dia 25, não é mês fechado, é 25/08 até 25/09"). Ver
    services/competencia.py::dia_regra.
    """
    data = data or date.today()
    with get_conn() as conn:
        with conn.cursor() as cur:
            dia_corte = _get_dia_corte(conn, usuario_id)
            competencia = calcular_competencia(data, dia_regra(dia_fechamento, dia_corte))
            cur.execute(
                """INSERT INTO gastos
                       (usuario_id, forma_pagamento_id, categoria_id, valor, descricao,
                        grupo_id, competencia, data)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING *""",
                (usuario_id, forma_id, categoria_id, valor, descricao, grupo_id, competencia, data),
            )
            conn.commit()
            return dict(cur.fetchone())


# "Último gasto" (este get, get_ultimos_gastos, excluir_ultimo_gasto e
# editar_ultimo_gasto_valor) ordena por id DESC, não mais data DESC
# (18/07/2026): com o lançamento antecipado de fixas (passe 2 do lançador),
# existe gasto com DATA FUTURA no banco — por data, "apagar último" no
# WhatsApp apagaria o custo fixo do mês que vem em vez do gasto que a pessoa
# acabou de registrar. id serial = ordem de criação, que é o que "último"
# sempre quis dizer nesses fluxos de correção do bot.
def get_ultimo_gasto(usuario_id: int):
    """
    Peek (sem excluir) do último gasto — usado por 'excluir ultimo' para decidir
    se precisa perguntar 'só esta parcela x compra inteira' (D3, Fase 3.2) antes
    de excluir de fato.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT g.id, g.valor, g.compra_parcelada_id, g.parcela_num,
                          c.nome  AS categoria_nome,
                          fp.nome AS forma_nome,
                          cp.parcelas AS total_parcelas
                   FROM gastos g
                   LEFT JOIN categorias c          ON c.id  = g.categoria_id
                   LEFT JOIN formas_pagamento fp   ON fp.id = g.forma_pagamento_id
                   LEFT JOIN compras_parceladas cp ON cp.id = g.compra_parcelada_id
                   WHERE g.usuario_id = %s
                   ORDER BY g.id DESC
                   LIMIT 1""",
                (usuario_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def _suprimir_relancamento_se_fixa(cur, gasto: dict):
    """
    Gasto vindo de despesa fixa com competência do mês atual pra frente:
    grava a supressão (migração 026) na mesma transação da exclusão — sem
    isso o lançador (catch-up diário + lançamento antecipado do mês
    seguinte) recriaria a linha na rodada seguinte e a exclusão feita pelo
    bot seria desfeita em silêncio. Mesma regra do caminho web
    (services/gastos.py::remover_gasto) — exclusão tem que valer igual não
    importa por onde entrou.
    """
    if gasto.get("despesa_fixa_id") and gasto.get("competencia") \
            and gasto["competencia"] >= date.today().replace(day=1):
        cur.execute(
            """INSERT INTO despesas_fixas_supressoes (despesa_fixa_id, competencia)
               VALUES (%s, DATE_TRUNC('month', %s::date)::date)
               ON CONFLICT DO NOTHING""",
            (gasto["despesa_fixa_id"], gasto["competencia"]),
        )


def excluir_gasto_por_id(gasto_id: int):
    """Exclui um gasto específico pelo id — usado para excluir só 1 parcela (D3)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT g.id, g.valor, g.despesa_fixa_id, g.competencia,
                          c.nome  AS categoria_nome,
                          fp.nome AS forma_nome
                   FROM gastos g
                   LEFT JOIN categorias c        ON c.id  = g.categoria_id
                   LEFT JOIN formas_pagamento fp ON fp.id = g.forma_pagamento_id
                   WHERE g.id = %s""",
                (gasto_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            gasto = dict(row)
            cur.execute("DELETE FROM gastos WHERE id = %s", (gasto_id,))
            _suprimir_relancamento_se_fixa(cur, gasto)
            conn.commit()
            return gasto


def get_ultimos_gastos(usuario_id: int, limit: int = 5):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT g.id, g.valor, g.data,
                          c.nome  AS categoria_nome,
                          fp.nome AS forma_nome
                   FROM gastos g
                   LEFT JOIN categorias c        ON c.id  = g.categoria_id
                   LEFT JOIN formas_pagamento fp ON fp.id = g.forma_pagamento_id
                   WHERE g.usuario_id = %s
                   ORDER BY g.id DESC
                   LIMIT %s""",
                (usuario_id, limit),
            )
            return [dict(r) for r in cur.fetchall()]


def get_ultimo_gasto_por_categoria(usuario_id: int, categoria_id: int):
    """
    Peek do gasto mais recente numa categoria específica — 29/08/2026, pedido
    do Lucas: responder perguntas tipo "qual foi o último dia que abasteci o
    carro?" (categoria Combustível) com o dado real, não um "não entendi".

    Mesmo escopo de `get_ultimos_gastos`: filtra só por `usuario_id`, não por
    `grupo_id` — cada membro do grupo vê o PRÓPRIO histórico nessa consulta,
    igual ao comando *gastos* já faz. Não é uma omissão nova, é manter a
    mesma decisão de escopo já tomada ali.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT g.id, g.valor, g.data,
                          c.nome  AS categoria_nome,
                          fp.nome AS forma_nome
                   FROM gastos g
                   LEFT JOIN categorias c        ON c.id  = g.categoria_id
                   LEFT JOIN formas_pagamento fp ON fp.id = g.forma_pagamento_id
                   WHERE g.usuario_id = %s AND g.categoria_id = %s
                   ORDER BY g.data DESC, g.id DESC
                   LIMIT 1""",
                (usuario_id, categoria_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def get_soma_gastos_categoria_periodo(usuario_id: int, categoria_id: int, dias: int) -> dict:
    """
    Soma de gastos numa categoria nos últimos `dias` dias (incluindo hoje) —
    29/08/2026, pedido do Lucas: "quanto gastei de combustível nos últimos
    30 dias?". Antes disso só existia `get_ultimo_gasto_por_categoria`
    (data do último gasto); essa pergunta de SOMA POR PERÍODO era
    explicitamente fora do escopo (ver ai.py::_montar_prompt_fallback) e
    caía errada em cima daquela função — respondia a data do último gasto
    pra uma pergunta de soma, que é outra coisa.

    Filtra por `g.data`, não `g.competencia`: "últimos 30 dias" é uma janela
    de calendário (quando a compra aconteceu), não de fatura — mesma lógica
    de escopo de `get_ultimo_gasto_por_categoria` (só `usuario_id`, sem
    `grupo_id`, cada membro vê o próprio histórico).
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COALESCE(SUM(g.valor), 0) AS total, COUNT(*) AS quantidade
                   FROM gastos g
                   WHERE g.usuario_id = %s AND g.categoria_id = %s
                     AND g.data >= CURRENT_DATE - (%s || ' days')::interval""",
                (usuario_id, categoria_id, dias),
            )
            row = cur.fetchone()
            return {"total": float(row["total"]), "quantidade": int(row["quantidade"])}


def excluir_ultimo_gasto(usuario_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT g.id, g.valor, g.despesa_fixa_id, g.competencia,
                          c.nome  AS categoria_nome,
                          fp.nome AS forma_nome
                   FROM gastos g
                   LEFT JOIN categorias c        ON c.id  = g.categoria_id
                   LEFT JOIN formas_pagamento fp ON fp.id = g.forma_pagamento_id
                   WHERE g.usuario_id = %s
                   ORDER BY g.id DESC
                   LIMIT 1""",
                (usuario_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            gasto = dict(row)
            cur.execute("DELETE FROM gastos WHERE id = %s", (gasto["id"],))
            _suprimir_relancamento_se_fixa(cur, gasto)
            conn.commit()
            return gasto


def editar_ultimo_gasto_valor(usuario_id: int, novo_valor: float) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM gastos WHERE usuario_id = %s ORDER BY id DESC LIMIT 1",
                (usuario_id,),
            )
            row = cur.fetchone()
            if not row:
                return False
            cur.execute("UPDATE gastos SET valor = %s WHERE id = %s", (novo_valor, row["id"]))
            conn.commit()
            return True


# ---------------------------------------------------------------------------
# Saldo
#
# Fase 3.2 (P2, aceito pelo Lucas em 11/07/2026): saldo e resumo passaram a
# filtrar por g.competencia em vez de g.data. Isso muda o resultado para
# gastos de cartão perto do fechamento — um gasto feito em 28/07 num cartão
# com dia_fechamento=25 agora conta na competência de agosto, não julho.
# Histórico existente foi backfillado (migração 003: competencia = mês da
# própria data), então gastos antigos continuam batendo com o que já
# apareciam antes dessa mudança.
#
# "Mês atual" (migração 028, 25/08/2026): NOW() sozinho não basta mais —
# NO PRÓPRIO dia_corte do usuário, "mês atual" já é o mês seguinte pra tudo
# que não é cartão (cartão continua pelo dia_fechamento da própria forma,
# já gravado em g.competencia). O CASE abaixo refaz a mesma conta de
# calcular_competencia em SQL, forma por forma (COALESCE pega o
# dia_fechamento quando existe, senão o dia_corte do parâmetro) — não dá
# pra usar calcular_competencia() aqui porque a query soma várias formas de
# uma vez, cada uma com seu próprio "dia que manda".
#
# NULLIF(%s - 1, 0): dia_corte usa regra INVERSA de dia_fechamento — "fecha
# dia 25" ainda conta o dia 25 no mês que está fechando, mas dia_corte=25
# ("recebo dia 25") já é o 1º dia do ciclo NOVO (bug real de 25/08/2026: VA/VR
# não tinham "renovado" no saldo do bot no próprio dia do pagamento). O -1
# converte pro formato que o CASE abaixo entende (dia_fechamento — mesma
# lógica de services/competencia.py::dia_corte_como_fechamento, só que em
# SQL). NULLIF trata dia_corte=1 como "sem deslocamento" (0 não é um
# dia_fechamento válido) — ciclo que começa no dia 1 é o mês calendário puro.
# ---------------------------------------------------------------------------

_SQL_COMPETENCIA_ATUAL = """DATE_TRUNC('month',
        CASE WHEN EXTRACT(DAY FROM CURRENT_DATE) > COALESCE(fp.dia_fechamento, NULLIF(%s - 1, 0))
             THEN CURRENT_DATE + INTERVAL '1 month'
             ELSE CURRENT_DATE END)"""


def get_saldo_forma(usuario_id: int, forma_id: int):
    """Retorna dict com gasto_mes, limite_mensal, nome. Soma todos os gastos da forma."""
    with get_conn() as conn:
        dia_corte = _get_dia_corte(conn, usuario_id)
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT fp.nome,
                          fp.limite_mensal,
                          COALESCE(SUM(g.valor), 0) AS gasto_mes
                   FROM formas_pagamento fp
                   LEFT JOIN gastos g
                     ON g.forma_pagamento_id = fp.id
                    AND DATE_TRUNC('month', g.competencia) = {_SQL_COMPETENCIA_ATUAL}
                   WHERE fp.id = %s
                   GROUP BY fp.id, fp.nome, fp.limite_mensal""",
                (dia_corte, forma_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def get_saldo_todas_formas(usuario_id: int):
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        dia_corte = _get_dia_corte(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    f"""SELECT fp.id, fp.nome, fp.limite_mensal,
                              COALESCE(SUM(g.valor), 0) AS gasto_mes
                       FROM formas_pagamento fp
                       LEFT JOIN gastos g
                         ON g.forma_pagamento_id = fp.id
                        AND DATE_TRUNC('month', g.competencia) = {_SQL_COMPETENCIA_ATUAL}
                       WHERE fp.grupo_id = %s
                       GROUP BY fp.id, fp.nome, fp.limite_mensal
                       ORDER BY fp.nome""",
                    (dia_corte, gid),
                )
            else:
                cur.execute(
                    f"""SELECT fp.id, fp.nome, fp.limite_mensal,
                              COALESCE(SUM(g.valor), 0) AS gasto_mes
                       FROM formas_pagamento fp
                       LEFT JOIN gastos g
                         ON g.forma_pagamento_id = fp.id
                        AND DATE_TRUNC('month', g.competencia) = {_SQL_COMPETENCIA_ATUAL}
                       WHERE fp.usuario_id = %s AND fp.grupo_id IS NULL
                       GROUP BY fp.id, fp.nome, fp.limite_mensal
                       ORDER BY fp.nome""",
                    (dia_corte, usuario_id),
                )
            return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Resumo mensal
# ---------------------------------------------------------------------------

def get_resumo_mes(usuario_id: int):
    """"Mês atual" aqui já é sob o dia_corte pra tudo que não é cartão
    (migração 028) — ver _SQL_COMPETENCIA_ATUAL logo acima."""
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        dia_corte = _get_dia_corte(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    f"""SELECT c.nome AS categoria, fp.nome AS forma, SUM(g.valor) AS total
                       FROM gastos g
                       JOIN categorias c        ON c.id  = g.categoria_id
                       JOIN formas_pagamento fp ON fp.id = g.forma_pagamento_id
                       WHERE fp.grupo_id = %s
                         AND DATE_TRUNC('month', g.competencia) = {_SQL_COMPETENCIA_ATUAL}
                       GROUP BY c.nome, fp.nome
                       ORDER BY total DESC""",
                    (gid, dia_corte),
                )
            else:
                cur.execute(
                    f"""SELECT c.nome AS categoria, fp.nome AS forma, SUM(g.valor) AS total
                       FROM gastos g
                       JOIN categorias c        ON c.id  = g.categoria_id
                       JOIN formas_pagamento fp ON fp.id = g.forma_pagamento_id
                       WHERE g.usuario_id = %s
                         AND g.grupo_id IS NULL
                         AND DATE_TRUNC('month', g.competencia) = {_SQL_COMPETENCIA_ATUAL}
                       GROUP BY c.nome, fp.nome
                       ORDER BY total DESC""",
                    (usuario_id, dia_corte),
                )
            return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Limite
# ---------------------------------------------------------------------------

def atualizar_limite(usuario_id: int, forma_nome: str, novo_limite: float) -> bool:
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        with conn.cursor() as cur:
            if gid:
                cur.execute(
                    """UPDATE formas_pagamento SET limite_mensal = %s
                       WHERE grupo_id = %s AND LOWER(nome) LIKE %s RETURNING id""",
                    (novo_limite, gid, f"%{forma_nome.lower()}%"),
                )
            else:
                cur.execute(
                    """UPDATE formas_pagamento SET limite_mensal = %s
                       WHERE usuario_id = %s AND grupo_id IS NULL AND LOWER(nome) LIKE %s RETURNING id""",
                    (novo_limite, usuario_id, f"%{forma_nome.lower()}%"),
                )
            updated = cur.fetchone()
            conn.commit()
            return updated is not None


# ---------------------------------------------------------------------------
# Grupos (contas compartilhadas)
# ---------------------------------------------------------------------------

def get_grupo(grupo_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM grupos WHERE id = %s", (grupo_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def get_membros_grupo(grupo_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM usuarios WHERE grupo_id = %s ORDER BY id", (grupo_id,))
            return [dict(r) for r in cur.fetchall()]


def criar_grupo(usuario_id: int, nome: str):
    """Cria grupo com formas de pagamento padrão zeradas (sem herdar histórico pessoal).
    Quem cria vira criador_id (migração 010) — único que pode apagar o grupo
    inteiro depois, ver services/conta.py."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO grupos (nome, criador_id) VALUES (%s, %s) RETURNING *",
                (nome, usuario_id),
            )
            grupo = dict(cur.fetchone())
            gid = grupo["id"]
            cur.execute("UPDATE usuarios SET grupo_id = %s WHERE id = %s", (gid, usuario_id))
            # Cria formas padrão novas para o grupo (tudo zerado)
            for nome_forma, limite in FORMAS_PADRAO:
                cur.execute(
                    "INSERT INTO formas_pagamento (usuario_id, grupo_id, nome, limite_mensal) VALUES (%s, %s, %s, %s)",
                    (usuario_id, gid, nome_forma, limite),
                )
            conn.commit()
            return grupo


def adicionar_membro_grupo(grupo_id: int, telefone: str):
    """Retorna (usuario, ja_em_outro_grupo)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM usuarios WHERE telefone = %s", (telefone,))
            row = cur.fetchone()
            if row:
                usuario = dict(row)
                if usuario.get("grupo_id"):
                    return usuario, True
                cur.execute("UPDATE usuarios SET grupo_id = %s WHERE id = %s", (grupo_id, usuario["id"]))
                conn.commit()
                return usuario, False

            cur.execute(
                "INSERT INTO usuarios (nome, telefone, grupo_id) VALUES (%s, %s, %s) RETURNING *",
                (telefone, telefone, grupo_id),
            )
            usuario = dict(cur.fetchone())
            conn.commit()
            return usuario, False


def limpar_formas_grupo(grupo_id: int):
    """Remove todas as formas de pagamento do grupo (para onboarding personalizado)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM formas_pagamento WHERE grupo_id = %s", (grupo_id,))
            conn.commit()


def restaurar_formas_padrao_grupo(usuario_id: int, grupo_id: int):
    """Adiciona as formas padrão ao grupo (usado quando o usuário não cadastra nenhuma)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            for nome, limite in FORMAS_PADRAO:
                cur.execute(
                    "INSERT INTO formas_pagamento (usuario_id, grupo_id, nome, limite_mensal) "
                    "VALUES (%s, %s, %s, %s)",
                    (usuario_id, grupo_id, nome, limite),
                )
            conn.commit()


def sair_grupo(usuario_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE usuarios SET grupo_id = NULL WHERE id = %s", (usuario_id,))
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM formas_pagamento WHERE usuario_id = %s AND grupo_id IS NULL",
                (usuario_id,),
            )
            cnt = cur.fetchone()["cnt"]
            if cnt == 0:
                for nome, limite in FORMAS_PADRAO:
                    cur.execute(
                        "INSERT INTO formas_pagamento (usuario_id, nome, limite_mensal) VALUES (%s, %s, %s)",
                        (usuario_id, nome, limite),
                    )
            conn.commit()
