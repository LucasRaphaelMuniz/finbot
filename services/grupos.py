"""
services/grupos.py — CRUD de grupo para a API web (Fase 4.3). O bot já tem
sua própria lógica em handler.py (_cmd_grupo) porque parte do fluxo lá é
conversacional (perguntar número, confirmar). Aqui é REST puro: o front já
manda os dados prontos, sem pergunta-resposta.

`adicionar_membro` (Fase 6.2) é o ÚNICO ponto que checa o limite de
membros do plano — handler.py (bot) foi ajustado pra chamar esta função em
vez de db.adicionar_membro_grupo direto, exatamente pra não duplicar essa
regra em dois lugares (§Fase 6 do PLANO_EXECUCAO.md: "Enforcement do limite
de membros num único ponto ... usado por bot e web"). A única exceção é o
onboarding (handler.py:_processar_onboarding) — lá o grupo acabou de ser
criado e ainda não tem plano/assinatura associado, então checar limite
nesse momento não faz sentido.
"""

import psycopg

from db import get_conn, _get_grupo_id, get_membros_grupo, adicionar_membro_grupo, sair_grupo
from utils.app_error import AppError
from utils.telefone import normalizar as normalizar_telefone


def _limite_membros(grupo_id: int) -> int | None:
    """
    None = sem limite (grupo sem assinatura/plano associado ainda — ver P6
    do plano: preços/planos são "definição futura", nenhum grupo existente
    tem uma linha em `assinaturas` até a Fase 6 de billing entrar de
    verdade). Enforcement só passa a valer quando o grupo tiver uma
    assinatura de fato — não trava retroativamente quem já usa o finbot.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT p.max_membros FROM assinaturas a
                   JOIN planos p ON p.id = a.plano_id
                   WHERE a.grupo_id = %s""",
                (grupo_id,),
            )
            row = cur.fetchone()
            return row["max_membros"] if row else None


def get_grupo_completo(usuario_id: int) -> dict | None:
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        if not gid:
            return None
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM grupos WHERE id = %s", (gid,))
            grupo = dict(cur.fetchone())
            cur.execute(
                "SELECT id, nome, telefone, auth_user_id FROM usuarios "
                "WHERE grupo_id = %s ORDER BY id",
                (gid,),
            )
            grupo["membros"] = [dict(r) for r in cur.fetchall()]
            return grupo


def atualizar_nome_grupo(usuario_id: int, novo_nome: str) -> dict | None:
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        if not gid:
            return None
        with conn.cursor() as cur:
            cur.execute("UPDATE grupos SET nome = %s WHERE id = %s RETURNING *", (novo_nome, gid))
            conn.commit()
            return dict(cur.fetchone())


def adicionar_membro(usuario_id: int, telefone: str):
    """
    Retorna (usuario, ja_em_outro_grupo) — mesma semântica de
    db.adicionar_membro_grupo. Levanta AppError 400 "limite_plano_excedido"
    se o grupo já estiver no teto de membros do plano contratado, ou
    "telefone_invalido" se o número não normalizar (Fase A do
    AUDITORIA_E_PLANO_CADASTRO.md — corrige F1: sem isso, membro adicionado
    pela web ficava com telefone cru, e o bot nunca reconhecia as mensagens dele).
    """
    telefone = normalizar_telefone(telefone)
    if not telefone:
        raise AppError("Telefone inválido — use DDD + número.", 400, "telefone_invalido")

    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
    if not gid:
        return None, False

    limite = _limite_membros(gid)
    if limite is not None and len(get_membros_grupo(gid)) >= limite:
        raise AppError(
            f"Seu plano atual permite até {limite} membro(s) no grupo. "
            "Remova alguém ou faça upgrade de plano para adicionar mais.",
            400, "limite_plano_excedido",
        )

    return adicionar_membro_grupo(gid, telefone)


def atualizar_membro(usuario_id: int, membro_id: int, nome: str = None, telefone: str = None) -> dict | None:
    """
    Só edita membro do MESMO grupo do usuário autenticado (isolamento multi-tenant —
    sem essa checagem, qualquer usuario_id autenticado poderia editar QUALQUER usuário
    do banco só sabendo o id).

    Telefone normalizado (Fase A, corrige F4: antes salvava cru e podia
    colidir com o UNIQUE de usuarios.telefone, estourando erro 500 genérico
    em vez de uma mensagem clara).
    """
    if telefone is not None:
        telefone = normalizar_telefone(telefone)
        if not telefone:
            raise AppError("Telefone inválido — use DDD + número.", 400, "telefone_invalido")

    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        if not gid:
            return None
        sets, params = [], []
        if nome is not None:
            sets.append("nome = %s")
            params.append(nome)
        if telefone is not None:
            sets.append("telefone = %s")
            params.append(telefone)
        if not sets:
            return None
        params += [membro_id, gid]
        with conn.cursor() as cur:
            try:
                cur.execute(
                    f"UPDATE usuarios SET {', '.join(sets)} WHERE id = %s AND grupo_id = %s RETURNING *",
                    params,
                )
            except psycopg.errors.UniqueViolation:
                conn.rollback()
                raise AppError(
                    "Esse número já está vinculado a outra conta.",
                    400, "telefone_em_uso",
                )
            row = cur.fetchone()
            conn.commit()
            return dict(row) if row else None


def remover_membro(usuario_id: int, membro_id: int) -> bool:
    """Remove membro do grupo (mesma regra de sair_grupo do bot: volta a
    conta individual com formas de pagamento próprias) — só que iniciado por
    OUTRO membro do grupo, não pelo próprio."""
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        if not gid:
            return False
        with conn.cursor() as cur:
            cur.execute(
                "SELECT grupo_id FROM usuarios WHERE id = %s",
                (membro_id,),
            )
            row = cur.fetchone()
            if not row or row["grupo_id"] != gid:
                return False
    sair_grupo(membro_id)
    return True
