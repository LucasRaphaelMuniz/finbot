"""
middlewares/ensure_authenticated.py — valida o JWT do Supabase Auth via JWKS
(chave assimétrica, decisão já registrada no §4.3 do PLANO_EXECUCAO.md) e
resolve o `usuario`/`grupo_id` correspondente no banco do finbot.

Dois decorators, de propósito separados:

- `@ensure_authenticated`: só exige um JWT válido. NÃO exige que o usuário já
  tenha `usuario`/`grupo_id` no banco — isso é esperado logo após o cadastro,
  antes de `POST /api/onboarding` ou `/api/convites/aceitar` rodarem. `g.usuario`
  fica None nesse caso; a rota decide o que fazer.
- `@requer_grupo`: além do JWT válido, exige `g.grupo_id` resolvido — usado
  por todas as rotas de dado (gastos, entradas, fixas, etc.) que não fazem
  sentido sem grupo. Levanta AppError 404 "sem_grupo" (contrato consumido
  pelo finbot-web em (app)/layout.jsx).

Duas exceções no meio do caminho — usuário confirmou e-mail mas nunca chega
a ter `grupo_id`, ou tem `usuario` mas sem grupo (conta individual, nunca
criou grupo) — ambas caem no mesmo "sem_grupo": do ponto de vista da API,
"sem usuario" e "usuario sem grupo" são a mesma situação (nada pra mostrar).
"""

import os
from functools import wraps

import jwt
from jwt import PyJWKClient
from flask import request, g

from db import get_conn
from utils.app_error import AppError

SUPABASE_JWKS_URL = os.getenv("SUPABASE_JWKS_URL", "")
SUPABASE_JWT_AUDIENCE = os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated")

_jwks_client = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        if not SUPABASE_JWKS_URL:
            # Falha de configuração do servidor, não do usuário — 500, não 401.
            raise AppError(
                "SUPABASE_JWKS_URL não configurado no servidor.", 500, "config_ausente"
            )
        _jwks_client = PyJWKClient(SUPABASE_JWKS_URL)
    return _jwks_client


def _decodificar_token(token: str) -> dict:
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            # Supabase Auth hoje assina com chaves assimétricas ES256
            # (curva elíptica P-256), não RS256 (RSA) — confirmado direto no
            # JWKS do projeto (GET /auth/v1/.well-known/jwks.json, campo
            # "alg"). O código original assumiu RS256 sem checar; com a
            # allowlist errada o PyJWT rejeita QUALQUER token válido
            # (InvalidAlgorithmError -> 401 aqui embaixo), o que causava um
            # loop infinito dashboard->login no frontend (401 aqui deriva
            # pro /login via interceptor do axios, mas a sessão Supabase no
            # navegador continua válida e manda de volta pro dashboard).
            algorithms=["ES256"],
            audience=SUPABASE_JWT_AUDIENCE,
        )
    except AppError:
        raise
    except Exception as exc:
        raise AppError("Token inválido ou expirado.", 401, "token_invalido") from exc


def get_usuario_por_auth_id(auth_user_id: str) -> dict | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM usuarios WHERE auth_user_id = %s", (auth_user_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def ensure_authenticated(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise AppError("Token de autenticação ausente.", 401, "token_ausente")

        token = auth_header.split(" ", 1)[1].strip()
        payload = _decodificar_token(token)

        auth_user_id = payload.get("sub")
        if not auth_user_id:
            raise AppError("Token inválido: claim 'sub' ausente.", 401, "token_invalido")

        usuario = get_usuario_por_auth_id(auth_user_id)

        g.auth_user_id = auth_user_id
        g.auth_email = payload.get("email")
        g.usuario = usuario
        g.usuario_id = usuario["id"] if usuario else None
        g.grupo_id = usuario.get("grupo_id") if usuario else None

        return f(*args, **kwargs)

    return wrapper


def requer_grupo(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not getattr(g, "grupo_id", None):
            raise AppError(
                "Cadastro ainda não concluído — grupo não encontrado.", 404, "sem_grupo"
            )
        return f(*args, **kwargs)

    return wrapper
