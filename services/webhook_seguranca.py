"""
services/webhook_seguranca.py — Fase 7 do PLANO_EXECUCAO.md (hardening).

Três preocupações que hoje vivem soltas em app.py, todas relacionadas a
"o webhook aceita tráfego não confiável do mundo externo":

1. `validar_apikey` (7.1) — o endpoint /webhook aceita qualquer POST hoje,
   sem checar se veio mesmo da Evolution API. Pura, sem banco: só compara
   o header recebido contra o segredo configurado.
2. `verificar_e_marcar_duplicata` (7.2) — sucessor do `_cupons_recentes`
   em memória do app.py: não sobrevive a restart nem a múltiplos workers
   gunicorn (cada worker tinha sua própria cópia do dict). Persistido em
   `comprovantes_processados` (migração 009).
3. `passou_rate_limit` (7.3) — limite simples por telefone, janela fixa de
   1 minuto, persistido em `rate_limit_webhook` (mesma razão de não usar
   memória — múltiplos workers).
"""

import hmac
import os
from datetime import datetime, timedelta, timezone

from db import get_conn

_JANELA_DUPLICATA_MINUTOS = 10
_JANELA_RATE_LIMIT_SEGUNDOS = 60
_LIMITE_MENSAGENS_POR_JANELA = 20  # generoso: uso normal não chega perto disso


def validar_apikey(header_recebido: str | None) -> bool:
    """
    Compara o header recebido contra EVOLUTION_WEBHOOK_SECRET (comparação
    em tempo constante — hmac.compare_digest — pra não vazar o segredo por
    timing attack).

    Sem EVOLUTION_WEBHOOK_SECRET configurado, o endpoint fica aberto (mesmo
    comportamento de antes desta fase) — decisão deliberada pra não quebrar
    quem ainda não configurou o secret na Evolution API; log de warning
    fica a cargo de quem chama (app.py), não deste módulo.
    """
    segredo = os.getenv("EVOLUTION_WEBHOOK_SECRET", "")
    if not segredo:
        return True
    return hmac.compare_digest((header_recebido or "").strip(), segredo)


def verificar_e_marcar_duplicata(telefone: str, valor: float, numero_cupom: str | None) -> bool:
    """
    Retorna True se este comprovante JÁ foi processado nos últimos 10 min
    (não marca de novo). Retorna False e MARCA como processado se for a
    1ª vez — mesma semântica de app.py:_e_duplicata original, só que
    persistida (INSERT idempotente via ON CONFLICT, sem race condition
    entre workers concorrentes: o segundo INSERT simplesmente não insere
    nada e a query de checagem por tempo decide).
    """
    chave = f"{telefone}:{numero_cupom}" if numero_cupom else f"{telefone}:{valor}"
    limite = datetime.now(timezone.utc) - timedelta(minutes=_JANELA_DUPLICATA_MINUTOS)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM comprovantes_processados WHERE chave = %s AND processado_em > %s",
                (chave, limite),
            )
            if cur.fetchone():
                return True

            cur.execute(
                "INSERT INTO comprovantes_processados (chave, processado_em) "
                "VALUES (%s, NOW()) ON CONFLICT (chave) DO UPDATE SET processado_em = NOW()",
                (chave,),
            )
            conn.commit()
            return False


def passou_rate_limit(telefone: str) -> bool:
    """
    True = pode processar. False = telefone excedeu o limite nesta janela
    (chamador deve ignorar a mensagem silenciosamente — não vale a pena
    responder "você excedeu o limite" pra um possível abuso automatizado).
    """
    agora = datetime.now(timezone.utc)
    limite_janela = agora - timedelta(seconds=_JANELA_RATE_LIMIT_SEGUNDOS)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT janela_inicio, contagem FROM rate_limit_webhook WHERE telefone = %s",
                (telefone,),
            )
            row = cur.fetchone()

            if not row or row["janela_inicio"] < limite_janela:
                cur.execute(
                    """INSERT INTO rate_limit_webhook (telefone, janela_inicio, contagem)
                       VALUES (%s, NOW(), 1)
                       ON CONFLICT (telefone) DO UPDATE SET janela_inicio = NOW(), contagem = 1""",
                    (telefone,),
                )
                conn.commit()
                return True

            if row["contagem"] >= _LIMITE_MENSAGENS_POR_JANELA:
                return False

            cur.execute(
                "UPDATE rate_limit_webhook SET contagem = contagem + 1 WHERE telefone = %s",
                (telefone,),
            )
            conn.commit()
            return True
