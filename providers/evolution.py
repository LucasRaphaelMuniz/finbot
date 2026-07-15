"""
providers/evolution.py — integração com a Evolution API para ENVIO
proativo de mensagens WhatsApp.

Movido de app.py nesta fase (Fase B do AUDITORIA_E_PLANO_CADASTRO.md) porque
é integração externa e pertence a `providers/` conforme a convenção do
próprio CLAUDE.md do projeto — app.py deveria só montar a app Flask e
registrar rotas/handlers, não conter lógica de chamada HTTP pra terceiros.
Recebimento de mensagem (webhook) continua em app.py, que é a parte
específica de Flask (rota); só o envio (client HTTP puro) mudou de lugar.

Usado por: app.py (resposta a mensagem recebida) e services/verificacao.py
(envio do código OTP, Fase B).
"""

import os
import httpx

from utils.logging_config import obter_logger

logger = obter_logger("finbot.evolution")

EVOLUTION_URL      = os.getenv("EVOLUTION_API_URL", "").rstrip("/")
EVOLUTION_KEY      = os.getenv("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "")


def enviar_mensagem(jid: str, texto: str) -> bool:
    """
    Envia mensagem de texto via Evolution API.

    Retorna True/False (sucesso) — diferente da versão anterior (dentro de
    app.py), que não retornava nada porque só era usada no fluxo webhook,
    onde uma falha de envio já era só logada e esquecida (a resposta ao
    usuário simplesmente não chegava). services/verificacao.py (Fase B)
    PRECISA saber se o envio falhou, pra decidir se deve recusar o cadastro
    (Evolution fora do ar = não dá pra confirmar posse do número = fail-closed
    por design, ver AUDITORIA_E_PLANO_CADASTRO.md, tabela de riscos).
    """
    # Envia só os dígitos, nunca o JID completo: nosso formato canônico de
    # armazenamento inclui o 9º dígito por heurística (utils/telefone.py),
    # mas contas antigas do WhatsApp têm JID SEM o 9 — se mandarmos
    # '5544999...@s.whatsapp.net' pronto, a Evolution confia no formato e
    # devolve 400 exists:false. Com dígitos puros ela resolve a variante
    # com/sem 9 sozinha e entrega no JID certo. Grupos (@g.us) passam
    # intactos: o id do grupo não é telefone.
    numero = jid.split("@")[0] if jid.endswith("@s.whatsapp.net") else jid
    try:
        resp = httpx.post(
            f"{EVOLUTION_URL}/message/sendText/{EVOLUTION_INSTANCE}",
            json={"number": numero, "text": texto},
            headers={"apikey": EVOLUTION_KEY},
            timeout=45,
        )
        resp.raise_for_status()
        return True
    except httpx.HTTPStatusError as e:
        # Corpo da resposta incluído no log: a Evolution devolve o motivo
        # real do 4xx no body (ex: instância desconectada, número inválido),
        # e só o status não permite diagnosticar nada.
        logger.error(
            f"Falha ao enviar mensagem via Evolution API: {e} — corpo: {e.response.text[:500]}"
        )
        return False
    except Exception as e:
        logger.error(f"Falha ao enviar mensagem via Evolution API: {e}")
        return False
