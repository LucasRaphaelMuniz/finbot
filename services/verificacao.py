"""
services/verificacao.py — OTP de posse de telefone via WhatsApp (Fase B do
AUDITORIA_E_PLANO_CADASTRO.md, corrige F2).

Por quê: sem provar que a pessoa realmente tem acesso àquele WhatsApp, o
merge de conta web -> registro existente do bot (services/onboarding.py)
seria uma porta aberta pra sequestrar o histórico financeiro de terceiros —
bastaria digitar o número de outra pessoa no cadastro. Este módulo resolve
isso: manda um código de 6 dígitos pro número via bot (Evolution API),
guarda em `verificacoes_telefone` (migração 012), e só marca `verificado_em`
quando o código bate. `completar_onboarding` (services/onboarding.py) passa
a exigir essa verificação antes de fazer qualquer merge.
"""

import secrets
from datetime import datetime, timedelta, timezone

from db import get_conn
from providers.evolution import enviar_mensagem
from utils.app_error import AppError
from utils.telefone import normalizar as normalizar_telefone

_EXPIRA_MINUTOS = 10
_MAX_TENTATIVAS = 5
_LIMITE_ENVIOS_POR_HORA = 3


def _gerar_codigo() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def enviar_codigo(auth_user_id: str, telefone: str) -> dict:
    """
    Normaliza o telefone, aplica rate limit (3 envios/número/hora — evita
    que alguém floode OTP pro WhatsApp de um terceiro só de digitar o
    número dele repetidamente), gera o código, grava e manda via Evolution
    API. Fail-closed por design (ver tabela de riscos do plano): se o envio
    falhar (Evolution fora do ar), levanta erro em vez de fingir sucesso —
    prosseguir sem confirmar que a mensagem chegou anularia a proteção
    inteira do F2.
    """
    jid = normalizar_telefone(telefone)
    if not jid:
        raise AppError("Telefone inválido — use DDD + número.", 400, "telefone_invalido")

    agora = datetime.now(timezone.utc)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM verificacoes_telefone "
                "WHERE telefone = %s AND criado_em > %s",
                (jid, agora - timedelta(hours=1)),
            )
            if cur.fetchone()["n"] >= _LIMITE_ENVIOS_POR_HORA:
                raise AppError(
                    "Muitos códigos enviados pra esse número. Tente novamente em 1 hora.",
                    429, "limite_envio_excedido",
                )

            codigo = _gerar_codigo()
            expira_em = agora + timedelta(minutes=_EXPIRA_MINUTOS)
            cur.execute(
                """INSERT INTO verificacoes_telefone
                       (auth_user_id, telefone, codigo, expira_em)
                   VALUES (%s, %s, %s, %s)""",
                (auth_user_id, jid, codigo, expira_em),
            )
            conn.commit()

    enviado = enviar_mensagem(
        jid,
        f"🔐 Seu código de verificação do Finbot é: *{codigo}*\n\n"
        f"Válido por {_EXPIRA_MINUTOS} minutos. Não compartilhe com ninguém.",
    )
    if not enviado:
        raise AppError(
            "Não conseguimos enviar o código pelo WhatsApp agora. Tente novamente em instantes.",
            502, "envio_falhou",
        )
    return {"enviado": True, "telefone": jid}


def confirmar_codigo(auth_user_id: str, telefone: str, codigo: str) -> dict:
    """
    Valida o código mais recente pro par (auth_user_id, telefone).

    Retorna {"ja_existia": bool, "tem_grupo": bool, "telefone": jid} — dados
    que o front usa pra decidir o passo seguinte do cadastro (Fase B3):
    revelar "esse telefone já tem histórico" só depois do código bater é
    seguro, porque nesse ponto a pessoa já provou posse do número.

    Levanta AppError 409 "telefone_ja_vinculado" se o telefone já pertence a
    OUTRA conta de login (auth_user_id diferente) — não é o caso de merge
    (puxar histórico do bot), é duas contas de login disputando o mesmo
    número; a saída correta é recuperar senha, não criar conta nova.
    """
    jid = normalizar_telefone(telefone)
    if not jid:
        raise AppError("Telefone inválido.", 400, "telefone_invalido")

    agora = datetime.now(timezone.utc)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT * FROM verificacoes_telefone
                   WHERE auth_user_id = %s AND telefone = %s
                   ORDER BY criado_em DESC LIMIT 1""",
                (auth_user_id, jid),
            )
            row = cur.fetchone()
            if not row:
                raise AppError("Nenhum código pendente para este número.", 400, "codigo_nao_encontrado")
            verificacao = dict(row)

            if verificacao["verificado_em"]:
                pass  # Reenvio da mesma tela após já ter confirmado — idempotente.
            elif verificacao["expira_em"] < agora:
                raise AppError("Código expirado. Peça um novo.", 400, "codigo_expirado")
            elif verificacao["tentativas"] >= _MAX_TENTATIVAS:
                raise AppError("Muitas tentativas erradas. Peça um novo código.", 400, "tentativas_excedidas")
            elif verificacao["codigo"] != (codigo or "").strip():
                cur.execute(
                    "UPDATE verificacoes_telefone SET tentativas = tentativas + 1 WHERE id = %s",
                    (verificacao["id"],),
                )
                conn.commit()
                raise AppError("Código incorreto.", 400, "codigo_incorreto")
            else:
                cur.execute(
                    "UPDATE verificacoes_telefone SET verificado_em = NOW() WHERE id = %s",
                    (verificacao["id"],),
                )
                conn.commit()

            cur.execute("SELECT * FROM usuarios WHERE telefone = %s", (jid,))
            usuario_existente = cur.fetchone()

    if usuario_existente and usuario_existente.get("auth_user_id") and \
            str(usuario_existente["auth_user_id"]) != str(auth_user_id):
        raise AppError(
            "Esse número já está vinculado a outra conta. "
            "Se for sua, recupere a senha dela em vez de criar uma nova.",
            409, "telefone_ja_vinculado",
        )

    ja_existia = usuario_existente is not None
    tem_grupo = bool(usuario_existente and usuario_existente.get("grupo_id"))

    return {"ja_existia": ja_existia, "tem_grupo": tem_grupo, "telefone": jid}


def esta_verificado(auth_user_id: str, telefone_jid: str) -> bool:
    """
    Usado por services/onboarding.py:completar_onboarding e
    services/convites.py:aceitar_convite antes de permitir merge/vínculo.
    Reconsulta o banco em vez de confiar num campo mandado pelo front — o
    front pode mentir dizendo "já verifiquei"; a query, não.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT 1 FROM verificacoes_telefone
                   WHERE auth_user_id = %s AND telefone = %s AND verificado_em IS NOT NULL
                   LIMIT 1""",
                (auth_user_id, telefone_jid),
            )
            return cur.fetchone() is not None
