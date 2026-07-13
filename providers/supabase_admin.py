"""
providers/supabase_admin.py — Fase 7.5 revisada: exclusão de conta "de
verdade" pedida pelo Lucas exige apagar o usuário no Supabase Auth também,
não só os dados financeiros no Postgres do finbot. Isso só é possível via
Admin API do Supabase, usando a service_role key.

ATENÇÃO DE SEGURANÇA: SUPABASE_SERVICE_ROLE_KEY dá acesso TOTAL ao projeto
Supabase (ignora RLS, lê/escreve/apaga qualquer coisa). Different da
SUPABASE_JWKS_URL (Fase 4.3), que é só uma chave pública de verificação.
Regras:
- Só existe como variável de ambiente do servidor (Railway).
- Nunca vai pro finbot-web (frontend) nem é logada.
- Se não estiver configurada, `deletar_usuario_auth` retorna False e NÃO
  derruba o resto da exclusão de conta — dev/staging sem essa chave ainda
  funciona pra apagar os dados financeiros, só não apaga o login.
"""

import os
import httpx

from utils.logging_config import obter_logger

logger = obter_logger("finbot.supabase_admin")

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


def deletar_usuario_auth(auth_user_id: str) -> bool:
    """
    Apaga o usuário no Supabase Auth via Admin API.

    Retorna True se apagou (ou já não existia — 404 tratado como sucesso,
    idempotente). Retorna False se a chave não estiver configurada ou se a
    chamada falhar — nesse caso quem chama (services/conta.py) já apagou os
    dados financeiros de qualquer forma; o login órfão fica pra limpeza
    manual depois, não é motivo pra reverter a exclusão de dados.
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        logger.warning(
            "SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY não configurados — "
            "login do Supabase Auth NÃO foi apagado, só os dados financeiros."
        )
        return False

    try:
        resp = httpx.delete(
            f"{SUPABASE_URL}/auth/v1/admin/users/{auth_user_id}",
            headers={
                "apikey": SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            },
            timeout=15,
        )
        if resp.status_code in (200, 204, 404):
            return True
        logger.error(f"Falha ao apagar usuário no Supabase Auth: {resp.status_code} {resp.text}")
        return False
    except Exception as exc:
        logger.error(f"Erro ao chamar Supabase Admin API: {exc}")
        return False
