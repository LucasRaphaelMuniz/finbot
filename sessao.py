import json
from db import get_conn


def get_sessao_ativa(usuario_id: int):
    """Retorna a sessão ativa (não expirada) mais recente ou None."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT *
                   FROM sessoes
                   WHERE usuario_id = %s
                     AND expira_em > NOW()
                   ORDER BY criado_em DESC
                   LIMIT 1""",
                (usuario_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def get_dados_temp(sessao: dict) -> dict:
    """Deserializa dados_temp da sessão (JSON) para dict."""
    raw = sessao.get("dados_temp") if sessao else None
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def criar_sessao(usuario_id: int, etapa: str,
                 valor_temp=None, categoria_temp=None, forma_temp=None,
                 dados_temp: dict = None, timeout_minutos: int = 5):
    """Deleta sessão existente e cria nova."""
    deletar_sessao(usuario_id)
    dados_json = json.dumps(dados_temp) if dados_temp else None
    with get_conn() as conn:
        with conn.cursor() as cur:
            # make_interval(mins => %s) em vez de INTERVAL '{timeout_minutos}
            # minutes' via f-string (Fase D4 do AUDITORIA_E_PLANO_CADASTRO.md,
            # ponto menor da auditoria) — timeout_minutos hoje só vem de
            # constantes internas do código (nunca de input do usuário), então
            # não era exploravel, mas passar como parâmetro em vez de montar a
            # string do SQL é o padrão idiomático do psycopg, evita o hábito
            # de interpolar SQL "porque nesse caso é seguro".
            cur.execute(
                """INSERT INTO sessoes
                       (usuario_id, etapa, valor_temp, categoria_temp, forma_temp,
                        dados_temp, expira_em)
                   VALUES (%s, %s, %s, %s, %s, %s,
                           NOW() + make_interval(mins => %s))""",
                (usuario_id, etapa, valor_temp, categoria_temp, forma_temp, dados_json, timeout_minutos),
            )
            conn.commit()


def atualizar_sessao(usuario_id: int, etapa: str = None,
                     categoria_temp=None, forma_temp=None,
                     dados_temp: dict = None, timeout_minutos: int = 5):
    """Atualiza campos da sessão ativa e renova o timeout."""
    sets = ["expira_em = NOW() + make_interval(mins => %s)"]
    params = [timeout_minutos]

    if etapa is not None:
        sets.append("etapa = %s")
        params.append(etapa)
    if categoria_temp is not None:
        sets.append("categoria_temp = %s")
        params.append(categoria_temp)
    if forma_temp is not None:
        sets.append("forma_temp = %s")
        params.append(forma_temp)
    if dados_temp is not None:
        sets.append("dados_temp = %s")
        params.append(json.dumps(dados_temp))

    params.append(usuario_id)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE sessoes SET {', '.join(sets)} "
                f"WHERE usuario_id = %s AND expira_em > NOW()",
                params,
            )
            conn.commit()


def deletar_sessao(usuario_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sessoes WHERE usuario_id = %s", (usuario_id,))
            conn.commit()


def verificar_sessao_expirada(usuario_id: int) -> bool:
    """Retorna True (e deleta) se e