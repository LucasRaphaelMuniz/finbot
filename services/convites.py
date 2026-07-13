"""
services/convites.py — convites de grupo (Fase 4.3 do PLANO_EXECUCAO.md,
migração 006). Convidado ganha conta web OPCIONAL via código; vínculo por
telefone via bot (comando `vincular`) continua funcionando independente
disso (P4/adicional de 11/07/2026 no plano).
"""

import secrets
import string
from datetime import datetime, timedelta, timezone

from db import get_conn, _get_grupo_id
from services.verificacao import esta_verificado
from utils.app_error import AppError
from utils.telefone import normalizar as normalizar_telefone

_ALFABETO = string.ascii_uppercase + string.digits


def _gerar_codigo() -> str:
    sufixo = "".join(secrets.choice(_ALFABETO) for _ in range(6))
    return f"FIN-{sufixo}"


def gerar_convite(usuario_id: int, telefone: str = None) -> dict:
    """
    `telefone` (opcional) pré-vincula o convite a um número — dono já sabe
    quem vai usar o código. Normalizado aqui pra já entrar no formato JID
    (Fase A do AUDITORIA_E_PLANO_CADASTRO.md); se vier algo não-vazio mas
    inválido, recusa em vez de salvar lixo que nunca vai bater com nada.
    """
    if telefone:
        telefone = normalizar_telefone(telefone)
        if not telefone:
            raise AppError("Telefone inválido — use DDD + número.", 400, "telefone_invalido")

    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        if not gid:
            raise AppError("Você precisa estar em um grupo para gerar convites.", 400, "sem_grupo")
        with conn.cursor() as cur:
            # Colisão de código é praticamente impossível (36^6 combinações),
            # mas o retry evita um erro feio de UNIQUE violation no ar raro caso aconteça.
            for _ in range(5):
                codigo = _gerar_codigo()
                cur.execute("SELECT 1 FROM convites WHERE codigo = %s", (codigo,))
                if not cur.fetchone():
                    break
            expira_em = datetime.now(timezone.utc) + timedelta(days=7)
            cur.execute(
                """INSERT INTO convites (grupo_id, codigo, criado_por, telefone, expira_em)
                   VALUES (%s, %s, %s, %s, %s) RETURNING *""",
                (gid, codigo, usuario_id, telefone, expira_em),
            )
            conn.commit()
            return dict(cur.fetchone())


def listar_convites(usuario_id: int) -> list[dict]:
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        if not gid:
            return []
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM convites WHERE grupo_id = %s ORDER BY id DESC",
                (gid,),
            )
            return [dict(r) for r in cur.fetchall()]


def aceitar_convite(auth_user_id: str, nome: str, codigo: str, telefone: str = None) -> dict:
    """
    Vincula o usuário autenticado (via auth_user_id) ao grupo do convite —
    NÃO cria grupo novo, ao contrário de completar_onboarding (P1 revisado
    do plano: convidado com conta web entra no grupo EXISTENTE).

    `telefone` é obrigatório pra quem ainda não existe no banco (ver abaixo),
    correção de 11/07/2026: o modelo inteiro de "grupo" do finbot é
    identificar quem manda mensagem pelo número de WhatsApp — deixar entrar
    sem telefone (versão anterior, usava um placeholder `web:<id>`) criava
    membro que nunca consegue usar o bot, quebrando a própria razão de ser
    do grupo. Só não é obrigatório se o convite já veio com um telefone
    pré-vinculado pelo dono (ex: ele rodou `grupo add <numero>` no bot antes
    de gerar o convite) — nesse caso o vínculo já existe, não tem o que pedir de novo.

    Fase B (corrige F2): quando o telefone vem do FORMULÁRIO (não
    pré-vinculado), exige verificação de posse (services/verificacao.py)
    antes de usá-lo — sem isso, o convidado poderia digitar o número de
    outra pessoa e herdar o histórico dela caso já exista um usuario com
    esse telefone (mesmo bug do onboarding normal). Quando pré-vinculado
    pelo dono do grupo, dispensa OTP — o dono já atestou aquele número ao
    rodar `grupo add`/gerar o convite com telefone, não faz sentido pedir
    confirmação de novo pro convidado.
    """
    codigo = (codigo or "").strip().upper()
    if not codigo:
        raise AppError("Código de convite ausente.", 400, "campos_obrigatorios")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM convites WHERE codigo = %s", (codigo,))
            convite = cur.fetchone()
            if not convite:
                raise AppError("Código de convite inválido.", 404, "convite_invalido")
            convite = dict(convite)

            if convite.get("usado_em"):
                raise AppError("Este convite já foi utilizado.", 400, "convite_usado")
            if convite.get("expira_em") and convite["expira_em"] < datetime.now(timezone.utc):
                raise AppError("Este convite expirou.", 400, "convite_expirado")

            gid = convite["grupo_id"]

            cur.execute("SELECT * FROM usuarios WHERE auth_user_id = %s", (auth_user_id,))
            usuario = cur.fetchone()

            if usuario:
                cur.execute(
                    "UPDATE usuarios SET grupo_id = %s WHERE id = %s RETURNING *",
                    (