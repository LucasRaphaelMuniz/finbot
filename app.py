"""
app.py — Webhook Flask para Evolution API v2.

Tipos de mensagem tratados:
  - conversation / extendedTextMessage → texto puro → handler.py
  - imageMessage                       → comprovante → ai.py (Vision) → handler.py
  - audioMessage (PTT)                 → voz        → ai.py (Whisper) → handler.py
"""

import os
import threading
import time
from datetime import date, datetime, timedelta, timezone
from flask import Flask, request, jsonify
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from dotenv import load_dotenv

load_dotenv()

from handler import processar_mensagem
from ai import analisar_comprovante, transcrever_audio, baixar_midia
from db import get_or_create_usuario
from services.categorias import get_categorias as get_categorias_usuario
from services.despesas_fixas import lancar_despesas_fixas_do_mes
from services.entradas_fixas import lancar_entradas_fixas_do_mes
from services.webhook_seguranca import validar_apikey, verificar_e_marcar_duplicata, passou_rate_limit
from parser import parece_ruido
from utils.app_error import AppError
from utils.logging_config import obter_logger
from utils.telefone import normalizar as _normalizar_jid
from providers.evolution import enviar_mensagem
from routes import register_routes

logger = obter_logger("finbot.app")


class _ISODateJSONProvider(DefaultJSONProvider):
    """
    Datas/horas em ISO 8601 (ex: "2026-07-06") nas respostas JSON da API.

    O DefaultJSONProvider do Flask (nunca mudou nisso entre versões — não é
    regressão) serializa `datetime.date`/`datetime.datetime` com
    `http_date()`, formato RFC 2822 tipo "Mon, 06 Jul 2026 00:00:00 GMT".
    Todo o resto do sistema sempre assumiu ISO: o frontend
    (finbot-web/src/utils/format.js::formatarDataBR/formatarCompetencia faz
    `.slice(0,10).split("-")`) e o parser web do bot. Esse descompasso
    quebrava silenciosamente qualquer campo `data`/`competencia`/timestamp
    que saísse cru de uma query (ex: routes/gastos.py devolve o dict do
    banco direto, sem passar por serialização manual) — a coluna Data em
    Lançamentos aparecia como "undefined/undefined/Mon, 06 Ju...".

    Centralizado aqui (1 lugar) em vez de `.isoformat()` espalhado em cada
    services/*.py que faz `dict(cur.fetchone())` — mesmo raciocínio do
    AppError/errorhandler logo abaixo: um ponto único pra uma preocupação
    que atravessa toda a API, não uma correção por endpoint (fácil esquecer
    um e reintroduzir o mesmo bug depois).
    """

    def default(self, o):
        if isinstance(o, date):
            return o.isoformat()
        return super().default(o)


app = Flask(__name__)
app.json = _ISODateJSONProvider(app)

# CORS restrito ao domínio do finbot-web (Fase 4.3, §4.3 do PLANO_EXECUCAO.md).
# Webhook do WhatsApp (/webhook) não precisa de CORS — só a API sob /api/*
# é chamada por um browser.
CORS(app, resources={r"/api/*": {"origins": os.getenv("FINBOT_WEB_ORIGIN", "http://localhost:3000")}})

register_routes(app)


# ---------------------------------------------------------------------------
# Error handler central da API (padrão CLAUDE.md: rotas/services dão
# `raise AppError(...)`, nunca `return jsonify(erro), status` espalhado).
# Não afeta o webhook do WhatsApp (/webhook sempre responde "", 200 pro
# Evolution API, mesmo em erro — ver bloco try/except dentro de webhook()).
# ---------------------------------------------------------------------------

@app.errorhandler(AppError)
def _handle_app_error(err: AppError):
    return jsonify(err.to_dict()), err.status_code


@app.errorhandler(Exception)
def _handle_unexpected_error(err: Exception):
    # Erro não previsto na API web (não confundir com o try/except do
    # webhook do WhatsApp, que é outro caminho de código). Flask já despacha
    # AppError pro @app.errorhandler(AppError) acima antes de chegar aqui —
    # o isinstance(err, AppError) que existia aqui era inalcançável (D4 do
    # AUDITORIA_E_PLANO_CADASTRO.md), removido.
    if isinstance(err, HTTPException):
        # 404 de rota inexistente, 405 método errado, etc. — preserva o
        # código HTTP real do Flask/Werkzeug em vez de mascarar tudo como 500.
        return jsonify({"erro": "erro_http", "mensagem": err.description}), err.code
    # Só chega aqui erro de verdade não previsto — loga e devolve 500
    # genérico, nunca vaza detalhe de exceção interna pro cliente HTTP.
    logger.exception(f"Erro não previsto na API: {err}")
    return jsonify({"erro": "erro_interno", "mensagem": "Ocorreu um erro interno."}), 500


# ---------------------------------------------------------------------------
# Fail-closed do webhook em produção sem segredo configurado (Fase D2 do
# AUDITORIA_E_PLANO_CADASTRO.md, corrige F7).
#
# services/webhook_seguranca.py:validar_apikey é fail-OPEN de propósito
# quando EVOLUTION_WEBHOOK_SECRET não está setado — decisão deliberada pra
# não travar quem ainda está configurando localmente. Mas em produção
# (Railway) isso deixaria o webhook aceitando qualquer POST não autenticado.
# RAILWAY_ENVIRONMENT é injetada automaticamente pela plataforma — não
# existe em dev local, então esse check não atrapalha `python app.py` na
# sua máquina.
# ---------------------------------------------------------------------------

_PRODUCAO_SEM_SECRET = bool(os.getenv("RAILWAY_ENVIRONMENT")) and not os.getenv("EVOLUTION_WEBHOOK_SECRET")
if _PRODUCAO_SEM_SECRET:
    logger.error(
        "EVOLUTION_WEBHOOK_SECRET não configurado em produção (RAILWAY_ENVIRONMENT "
        "presente) — /webhook vai recusar TODO tráfego até isso ser corrigido."
    )


# ---------------------------------------------------------------------------
# Lançador diário de despesas fixas — thread em processo, substituindo o
# Cron Job separado do Railway que a decisão D4 original (PLANO_EXECUCAO.md)
# pedia (pedido do Lucas em 16/07/2026: evitar um segundo serviço no Railway
# só pra isso).
#
# D4 rejeitava scheduler in-process explicitamente por causa de múltiplos
# workers gunicorn: com N workers, cada um é um processo próprio e cada um
# sobe essa mesma thread — todos tentam lançar por volta do mesmo horário.
# Sendo honesto sobre isso em vez de fingir que não existe: na prática isso
# não duplica gasto nenhum, porque lancar_despesas_fixas_do_mes() já tem
# duas camadas de proteção contra corrida (services/despesas_fixas.py) —
# o índice único uq_despesa_fixa_mes (migração 004) e o
# try/except UniqueViolation em volta do INSERT — pensadas originalmente pra
# "2 execuções do cron sobrepostas", mas é exatamente a mesma categoria de
# corrida que N workers tentando ao mesmo tempo. Só o primeiro grava; os
# outros caem no except e seguem sem erro visível.
#
# Trade-off real que essa proteção NÃO cobre: se o processo web ficar fora
# do ar o dia inteiro (deploy quebrado, downtime), nenhuma despesa fixa
# lança naquele dia — não tem catch-up automático pra dias já passados. Pra
# isso existe o botão "Confirmar" nas linhas "previsto" de Lançamentos
# (routes/fixas.py: POST /api/fixas/:id/confirmar). Se downtime virar
# problema recorrente, aí sim vale reconsiderar um Cron Job de verdade.
# ---------------------------------------------------------------------------

def _rodar_lancadores():
    """Despesas fixas + entradas fixas, cada um com try próprio — falha num
    não pode engolir o outro. Idempotentes e com catch-up (>= dia devido),
    então rodar quantas vezes for não duplica nada."""
    try:
        lancados = lancar_despesas_fixas_do_mes()
        if lancados:
            logger.info(f"Lançador: {len(lancados)} despesa(s) fixa(s) lançada(s).")
    except Exception:
        logger.exception("Lançador de despesas fixas falhou.")
    try:
        entradas = lancar_entradas_fixas_do_mes()
        if entradas:
            logger.info(f"Lançador: {len(entradas)} entrada(s) fixa(s) lançada(s).")
    except Exception:
        logger.exception("Lançador de entradas fixas falhou.")


def _loop_lancar_fixas_diario():
    # Roda JÁ na subida do processo (18/07/2026): com o catch-up nos
    # lançadores (dia devido <= hoje), um deploy/restart em qualquer hora do
    # dia lança imediatamente o que estiver pendente no mês — antes, o
    # processo esperava as 6h do dia seguinte e o gap era coberto por um
    # botão "Confirmar" manual (removido; custo fixo tem que ser automático).
    _rodar_lancadores()
    while True:
        agora = datetime.now()
        proxima_execucao = agora.replace(hour=6, minute=0, second=0, microsecond=0)
        if proxima_execucao <= agora:
            proxima_execucao += timedelta(days=1)
        time.sleep((proxima_execucao - agora).total_seconds())
        _rodar_lancadores()


threading.Thread(target=_loop_lancar_fixas_diario, daemon=True).start()


# ---------------------------------------------------------------------------
# Formatação de valor para o texto sintético do comprovante
# ---------------------------------------------------------------------------

def _valor_para_texto_br(valor) -> str:
    """
    Formata o valor numérico vindo do Vision (float) como string em formato
    BR (vírgula decimal) antes de embuti-lo no texto_sintetico.

    Por quê: `str(float)` usa ponto decimal e nem sempre com 2 casas
    (ex.: 50.0 -> '50.0', só 1 dígito após o ponto). O parser trata '.' como
    decimal apenas quando seguido de exatamente 2 dígitos (D1); fora disso
    interpreta como separador de milhar, e '50.0' virava 500 nesse caminho.
    Formatar sempre com vírgula remove a ambiguidade na origem, em vez de
    empurrar mais heurística para o parser.
    """
    return f"{float(valor):.2f}".replace(".", ",")


# ---------------------------------------------------------------------------
# Extração de metadados do payload Evolution
# ---------------------------------------------------------------------------

def obter_telefone_e_jid(data: dict) -> tuple[str | None, str]:
    """
    Retorna (telefone_normalizado, jid_para_resposta).

    Evolution API v2 com multi-device usa @lid em participant, mas disponibiliza
    participantAlt (dentro de key) com o número real no formato @s.whatsapp.net.

    Corrigido em 29/08/2026 (print do Lucas: mensagem de grupo mandada pela
    "Amor" nunca gerava resposta nenhuma — nem erro, nem "não entendi",
    silêncio total, sem log nenhum). Causa: quando a Evolution API NÃO
    populava participantAlt pra esse contato (comportamento visto antes só
    pro remoteJid de mensagem direta, mas que também acontece com
    participant em grupo), `participant` sozinho é um @lid — e
    `utils.telefone.normalizar` descarta qualquer string com "@lid" de
    propósito (não representa uma pessoa identificável). Telefone virava
    None e a mensagem morria na checagem `if not telefone` do webhook, sem
    nenhum log — impossível de diagnosticar depois.
    Fix: mesmo fallback que a mensagem direta já tinha pra esse cenário —
    tenta `data.get("sender")` antes de desistir.
    """
    key    = data.get("key", {})
    remote = key.get("remoteJid", "")

    if remote.endswith("@g.us"):
        # Mensagem de grupo: prefere participantAlt (número real) sobre
        # participant (@lid); se nenhum dos dois normalizar, tenta "sender"
        # (mesmo campo que já resolvia esse caso em mensagem direta).
        participant = key.get("participantAlt") or key.get("participant", "")
        telefone = _normalizar_jid(participant)
        if not telefone:
            telefone = _normalizar_jid(data.get("sender", ""))
        if not telefone:
            logger.warning(
                "Webhook de grupo sem telefone identificável — "
                f"participant={participant!r} sender={data.get('sender')!r} "
                f"pushName={data.get('pushName')!r}"
            )
        return telefone, remote

    # Mensagem direta
    telefone = _normalizar_jid(remote)
    if not telefone:
        # remoteJid é @lid: usa sender (campo no data, não no key)
        sender   = data.get("sender", "")
        telefone = _normalizar_jid(sender)
    if not telefone:
        logger.warning(
            f"Webhook direto sem telefone identificável — remoteJid={remote!r} "
            f"sender={data.get('sender')!r} pushName={data.get('pushName')!r}"
        )
    return telefone, (telefone or remote)


def obter_texto(msg: dict) -> str | None:
    if "conversation" in msg:
        return msg["conversation"]
    if "extendedTextMessage" in msg:
        return msg["extendedTextMessage"].get("text", "")
    return None


# ---------------------------------------------------------------------------
# Webhook principal
# ---------------------------------------------------------------------------

@app.route("/webhook", methods=["POST"])
@app.route("/webhook/<path:event_path>", methods=["POST"])
def webhook(event_path=None):
    # Fase D2 — produção sem EVOLUTION_WEBHOOK_SECRET configurado: recusa
    # tudo (fail-closed), em vez de aceitar por engano (ver checagem no
    # startup do módulo, acima).
    if _PRODUCAO_SEM_SECRET:
        return "", 401

    # Fase 7.1 — antes disso, qualquer POST era aceito e processado. Com
    # EVOLUTION_WEBHOOK_SECRET configurado, exige o header 'apikey' batendo
    # com o segredo (comparação em tempo constante, ver services/webhook_seguranca.py).
    if not validar_apikey(request.headers.get("apikey")):
        logger.warning("Webhook rejeitado: apikey ausente ou inválida.")
        return "", 401

    payload = request.get_json(silent=True)
    if not payload:
        return "", 200

    # Evolution v2 envelopa em "data" para events messages.upsert
    event = payload.get("event", "")
    if event != "messages.upsert":
        return "", 200

    data = payload.get("data", {})
    key  = data.get("key", {})

    # Ignora mensagens próprias e de status
    if key.get("fromMe", False):
        return "", 200
    if key.get("remoteJid") == "status@broadcast":
        return "", 200

    msg = data.get("message", {})
    if not msg:
        return "", 200

    telefone, jid = obter_telefone_e_jid(data)
    if not telefone:
        # @lid (linked device) ou formato desconhecido — ignora silenciosamente
        return "", 200

    # Fase 7.3 — limite simples por telefone (20 msg/min); protege contra
    # abuso/loop antes de gastar processamento (e possivelmente chamada de
    # IA) em qualquer mensagem.
    if not passou_rate_limit(telefone):
        logger.warning(f"Rate limit excedido para {telefone} — mensagem ignorada.")
        return "", 200

    eh_grupo_whatsapp = key.get("remoteJid", "").endswith("@g.us")
    resposta = None

    # ── Texto puro ──────────────────────────────────────────────────────────
    texto = obter_texto(msg)
    if texto:
        texto = texto.strip()
        # Fase 7.4, revisada em 29/08/2026 — em grupo real do WhatsApp (P4:
        # grupo continua suportado), evita gastar 1 chamada de IA em
        # chit-chat que não é dirigido ao bot ("kkkk", "❤️", "ok").
        #
        # Até aqui o filtro era o oposto: só deixava passar quem começasse
        # com um prefixo de comando fixo (_COMANDOS_CONHECIDOS, uma 3ª cópia
        # da mesma lista que já existia em handler.py e services/ai_fallback.py,
        # e que tinha ficado pra trás — nem tinha "contas", "limite" etc).
        # Bug real (29/08/2026, print do Lucas): "Paguei a fatura do cartão"
        # mandado no grupo não bate em nenhum prefixo nem tem valor, então
        # nunca chegava a chamar processar_mensagem — nem a IA, nem o "não
        # entendi" do handler rodavam, silêncio total ANTES de qualquer
        # lógica de resposta.
        #
        # Mesma regra já usada dentro do handler pra sessão pendente (pedido
        # do Lucas: "não deve existir possibilidade de ficar sem resposta"):
        # inverte o filtro — só ignora ruído ÓBVIO (parser.parece_ruido),
        # deixa a IA decidir tudo o mais. Mensagem direta (1:1) sempre
        # processava e continua processando, sem passar por este filtro.
        if eh_grupo_whatsapp and parece_ruido(texto):
            return "", 200
        resposta = processar_mensagem(telefone, texto)

    # ── Imagem (comprovante) ────────────────────────────────────────────────
    elif "imageMessage" in msg:
        caption  = msg["imageMessage"].get("caption", "")
        mimetype = msg["imageMessage"].get("mimetype", "image/jpeg")

        # Fase 7.4 original: em grupo, só chamava a Vision se a foto viesse
        # com legenda — economiza IA quando a imagem solta é papo/meme.
        # Revisado (24/07/2026, pedido do Lucas: mandou foto de nota fiscal
        # sem legenda no grupo "Despesas Casa" e o bot ficou mudo — o filtro
        # engolia a imagem ANTES de sequer chamar a Vision). Premissa
        # original não vale pra um grupo dedicado a despesas — a foto solta
        # aqui é o caso comum, não a exceção. Troca: sempre chama a Vision;
        # o que muda é só quando FICAR CALADO se não achar valor (provável
        # meme/papo) em vez de responder "não consegui ler" pro grupo
        # inteiro toda vez que alguém manda uma foto qualquer sem intenção
        # de registrar gasto. Com legenda, sempre responde — legenda é
        # sinal explícito de intenção. Trade-off consciente: mais chamadas
        # de Vision (custo) em troca de não perder comprovante nenhum.
        sem_legenda_em_grupo = eh_grupo_whatsapp and not caption.strip()

        try:
            imagem_bytes = baixar_midia(data)
            # Resolve o usuário aqui (idempotente — get_or_create_usuario já
            # existe/é chamado de novo em processar_mensagem mais abaixo) só
            # para buscar as categorias do grupo antes de acionar a Vision (Fase 3.1).
            usuario_atual, _ = get_or_create_usuario(telefone)
            nomes_categorias = [c["nome"] for c in get_categorias_usuario(usuario_atual["id"])]
            dados = analisar_comprovante(imagem_bytes, mimetype, categorias=nomes_categorias)

            valor        = dados.get("valor")
            numero_cupom = dados.get("numero_cupom")

            if not valor:
                # Foto solta sem legenda que a Vision não reconheceu como
                # comprovante: fica calado (provável meme/papo do grupo).
                # Com legenda ou em 1:1, a intenção era clara — avisa.
                if not sem_legenda_em_grupo:
                    resposta = (
                        "🔍 Não consegui identificar o valor total no comprovante.\n"
                        "Digite o valor manualmente (ex: *50 mercado cartão*)."
                    )
            elif verificar_e_marcar_duplicata(telefone, valor, numero_cupom):
                resposta = (
                    f"⚠️ Este comprovante de *R$ {str(valor).replace('.', ',')}* "
                    "parece já ter sido registrado.\n"
                    "Se for um gasto diferente, digite manualmente (ex: *50 mercado cartão*)."
                )
            else:
                partes = [
                    _valor_para_texto_br(valor),
                    dados.get("descricao", ""),
                    dados.get("categoria_sugerida", ""),
                    dados.get("forma_pagamento") or "",
                    caption,
                ]
                texto_sintetico = " ".join(p for p in partes if p).strip()
                resultado = processar_mensagem(telefone, texto_sintetico)
                # resultado vazio = handler decidiu ficar em silêncio (ex:
                # havia uma pergunta em aberto e isto não a respondia, ver
                # handler._fora_do_esperado). Mandar só o cabeçalho
                # "Comprovante lido pela IA" sem o resultado seria pior que
                # não mandar nada.
                resposta = f"📄 _Comprovante lido pela IA_\n\n{resultado}" if resultado else None

        except Exception as e:
            logger.error(f"Erro ao processar comprovante (Vision): {e}")
            # Mesma lógica: erro numa foto solta sem legenda em grupo não
            # vira alarde pro grupo inteiro — só quando havia sinal de
            # intenção (legenda ou 1:1).
            if not sem_legenda_em_grupo:
                resposta = "😕 Erro ao ler o comprovante. Tente digitar o gasto manualmente."

    # ── Áudio PTT (voz) ─────────────────────────────────────────────────────
    elif "audioMessage" in msg:
        # Sem filtro barato aqui, diferente de texto/imagem: áudio não tem
        # nenhum sinal textual (nem legenda) disponível ANTES de já ter
        # pago o custo da transcrição — não tem como aplicar um filtro
        # barato de verdade sem primeiro transcrever. Decisão consciente,
        # não descuido: se o volume de áudio em grupos virar problema de
        # custo real, a mitigação certa é desabilitar áudio em @g.us por
        # completo, não tentar adivinhar antes de ouvir.
        mimetype = msg["audioMessage"].get("mimetype", "audio/ogg; codecs=opus")
        try:
            audio_bytes  = baixar_midia(data)
            transcricao  = transcrever_audio(audio_bytes, mimetype)
            resultado    = processar_mensagem(telefone, transcricao)
            # Mesmo motivo do bloco de imagem: sem resultado, não manda só
            # o "Ouvi: ..." solto.
            resposta = f"🎤 _Ouvi: \"{transcricao}\"_\n\n{resultado}" if resultado else None

        except Exception as e:
            logger.error(f"Erro ao processar áudio (Whisper): {e}")
            resposta = "😕 Não consegui entender o áudio. Tente digitar o gasto."

    # ── Tipo não suportado ───────────────────────────────────────────────────
    else:
        # Documentos, stickers, etc. — ignora silenciosamente
        return "", 200

    if resposta:
        enviar_mensagem(jid, resposta)

    return "", 200


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
