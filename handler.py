"""
handler.py — lógica principal de processamento de mensagens do Finbot.
"""

import re
from datetime import date
from difflib import SequenceMatcher

from utils.logging_config import obter_logger

logger = obter_logger("finbot.handler")

from db import (
    get_or_create_usuario,
    get_usuario,
    get_formas_pagamento,
    registrar_gasto,
    get_saldo_forma,
    set_nome_usuario,
    adicionar_forma_pagamento,
    remover_forma_pagamento,
    excluir_ultimo_gasto,
    get_ultimo_gasto,
    get_ultimo_gasto_por_categoria,
    excluir_gasto_por_id,
    editar_ultimo_gasto_valor,
    get_grupo,
    get_membros_grupo,
    criar_grupo,
    adicionar_membro_grupo,
    sair_grupo,
    limpar_formas_grupo,
    restaurar_formas_padrao_grupo,
)
from services.categorias import (
    get_categorias,
    adicionar_categoria,
    remover_categoria,
)
from services.parcelamento import (
    criar_compra_parcelada,
    excluir_compra_parcelada,
    formatar_competencia,
)
from services.despesas_fixas import (
    get_despesas_fixas,
    criar_despesa_fixa,
    desativar_despesa_fixa,
)
from services.entradas import (
    registrar_entrada,
    get_total_entradas_mes,
)
from services.ai_fallback import (
    interpretar_mensagem,
    completar_categoria_forma,
    interpretar_correcao_comando,
)
from services.grupos import adicionar_membro as adicionar_membro_com_limite
from utils.app_error import AppError
from utils.respostas import eh_afirmativo, eh_negativo
from utils.telefone import normalizar as _normalizar_telefone
from sessao import (
    get_sessao_ativa,
    get_dados_temp,
    criar_sessao,
    atualizar_sessao,
    deletar_sessao,
    verificar_sessao_expirada,
)
from parser import (
    extrair_valor,
    extrair_categoria,
    extrair_forma_pagamento,
    extrair_parcelas,
    eh_entrada,
    parece_comando_natural,
    parece_correcao,
    parece_ruido,
    limpar_descricao,
    extrair_data,
)
from comandos import cmd_saldo, cmd_resumo, cmd_limite, cmd_ajuda, cmd_gastos, cmd_contas
from services.contas_mes import buscar_contas_abertas, listar_contas_mes, marcar_conta


def _brl(valor: float) -> str:
    s = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


_FIXA_ADD_RE = re.compile(
    r"^fixa\s+(?:add|adicionar)\s+(.+?)\s+(\d+(?:[.,]\d{1,2})?)\s+dia\s+(\d{1,2})$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Ponto de entrada público
# ---------------------------------------------------------------------------

def processar_mensagem(telefone: str, mensagem: str) -> str:
    try:
        usuario, novo = get_or_create_usuario(telefone)
        uid = usuario["id"]

        # ── Usuário novo: inicia onboarding ────────────────────────────────
        if novo:
            criar_sessao(uid, etapa="onboarding_nome", timeout_minutos=30)
            return (
                "👋 *Bem-vindo ao Finbot!*\n\n"
                "Vou te ajudar a configurar tudo em poucos passos.\n\n"
                "Qual é o seu nome?"
            )

        lower = mensagem.lower().strip()

        # ── Sessão ativa ────────────────────────────────────────────────────
        sessao = get_sessao_ativa(uid)
        if sessao:
            # Onboarding tem prioridade sobre qualquer comando
            if sessao["etapa"].startswith("onboarding_"):
                return _processar_onboarding(uid, sessao, mensagem)
            return _processar_sessao(uid, sessao, mensagem)

        # ── Usuário pré-adicionado (via vincular): primeira mensagem ───────────
        # Detecta: não é novo, nome nunca foi definido (nome == telefone), já tem grupo.
        # Nesse caso pede só o nome → mostra boas-vindas ao grupo.
        nome_u = usuario.get("nome", "")
        tel_u  = usuario.get("telefone", "")
        gid_u  = usuario.get("grupo_id")
        if nome_u == tel_u and gid_u:
            criar_sessao(uid, etapa="onboarding_welcome_nome", timeout_minutos=30)
            return (
                "👋 *Olá! Bem-vindo ao Finbot!*\n\n"
                "Qual é o seu nome?"
            )

        # ── Sessão expirada ─────────────────────────────────────────────────
        # Só limpa e SEGUE processando esta mensagem (24/07/2026). Antes,
        # consumia a mensagem inteira só pra avisar "cancelado por
        # inatividade — sua próxima mensagem será tratada como novo gasto",
        # obrigando a pessoa a reenviar. Aconteceu no print do Lucas: mandou
        # o mesmo comando 2h depois e ele foi engolido por esse aviso em vez
        # de executar. O aviso descrevia um comportamento pior do que
        # simplesmente fazer o que a pessoa pediu agora — a sessão pendente
        # já estava morta de qualquer jeito, não há o que preservar.
        verificar_sessao_expirada(uid)

        # ── Comandos normais ────────────────────────────────────────────────
        resultado_comando = _despachar_comando(uid, mensagem)
        if resultado_comando is not None:
            return resultado_comando

        # ── Input livre ─────────────────────────────────────────────────────
        return _processar_input_livre(uid, mensagem)

    except Exception as exc:
        logger.exception(f"Erro ao processar mensagem de {telefone}: {exc}")
        return "😕 Ocorreu um erro interno. Tente novamente em instantes."


def _despachar_comando(uid: int, mensagem: str) -> str | None:
    """
    Roteador de comandos com sintaxe exata (extraído de `processar_mensagem`
    em 24/07/2026 pra virar reutilizável). Retorna None se `mensagem` não
    bate em nenhum comando conhecido — quem chama decide o que fazer nesse
    caso (input livre em `processar_mensagem`, ou "não consegui executar" na
    confirmação de comando sugerido pela IA em `_processar_confirmacao_comando`).

    Motivo do extract: o fluxo de "IA entende comando em linguagem natural"
    (services/ai_fallback.py::interpretar_mensagem, intenção 'comando')
    precisa rodar EXATAMENTE este mesmo roteador depois que o usuário
    confirma — sem isso, ou duplicava o if/elif inteiro, ou a IA executava
    a ação direto sem passar pela mesma validação/parsing que um comando
    digitado manualmente já tem (ex: `_normalizar_telefone`, `_FIXA_ADD_RE`).
    """
    lower = mensagem.lower().strip()
    if lower == "ajuda":
        return cmd_ajuda()
    if lower.startswith("saldo"):
        return cmd_saldo(uid, lower)
    if lower == "resumo":
        return cmd_resumo(uid)
    if lower.startswith("limite "):
        return cmd_limite(uid, lower)
    if lower == "gastos":
        return cmd_gastos(uid)
    if lower == "contas":
        return cmd_contas(uid)
    # "desfazer" (29/08/2026, print do Lucas): sinônimo determinístico de
    # "excluir ultimo". Sem isso, "desfazer" não bate em nenhum prefixo
    # aqui, extrair_valor devolve None, e a mensagem cai inteira no
    # fallback de IA (_tentar_fallback_ia) — que precisaria classificar
    # "Desfazer" sozinho, sem nenhum contexto do que fazer, como intenção
    # 'comando' com comando_sugerido='excluir ultimo'. Na prática a IA não
    # reconheceu (respondeu "Não entendi essa" no print) — plausível: a
    # palavra sozinha não aparece na REFERÊNCIA DE COMANDOS (cmd_ajuda),
    # que só lista "excluir ultimo". Um alias direto aqui é o caminho
    # barato e confiável — sem depender de a IA "adivinhar" o sinônimo.
    if lower in ("desfazer", "desfaz", "desfazer ultimo", "desfazer o ultimo"):
        return _cmd_excluir(uid, "excluir ultimo")
    if lower.startswith("excluir"):
        return _cmd_excluir(uid, lower)
    if lower.startswith("editar ultimo"):
        return _cmd_editar_ultimo(uid, lower)
    if lower.startswith("forma "):
        return _cmd_forma(uid, lower)
    if lower.startswith("categoria "):
        return _cmd_categoria(uid, lower)
    if lower.startswith("fixa "):
        return _cmd_fixa(uid, lower)
    if lower.startswith("entrada "):
        return _cmd_entrada(uid, mensagem)
    if lower.startswith("apelido "):
        return _cmd_apelido(uid, lower)
    if lower.startswith("vincular "):
        return _cmd_vincular(uid, lower)
    if lower == "grupo" or lower.startswith("grupo "):
        return _cmd_grupo(uid, mensagem)
    return None


# ---------------------------------------------------------------------------
# Resposta que não responde a pergunta em aberto (24/07/2026)
#
# Pedido do Lucas: "se a próxima mensagem for diferente do solicitado (...)
# o bot deve apenas ignorar... quando solicitar sim ou não, se a pessoa
# responder outra coisa, o bot simplesmente ignora".
#
# Ignorar direto tem UM buraco, e foi o que apareceu no print dele: se a
# pessoa manda um COMANDO NOVO com uma sessão aberta, o silêncio a obriga a
# digitar de novo — sem nenhuma pista de por que a 1ª vez não funcionou.
# Então o silêncio vale só pra ruído de verdade; mensagem que claramente
# começa outra coisa abandona a pergunta pendente e é processada.
#
# O critério é deliberadamente CONSERVADOR: só prefixo de comando conhecido
# ou frase com estrutura de ordem (parser.parece_comando_natural). "tem um
# número" NÃO entra — dentro de um menu numerado ("1. CRÉDITO"), um número
# solto é resposta ao menu, não gasto novo.
# ---------------------------------------------------------------------------

_PREFIXOS_NOVA_INTENCAO = (
    "saldo", "resumo", "gastos", "contas", "ajuda", "excluir", "editar ultimo",
    "forma ", "categoria ", "fixa ", "entrada ", "apelido ",
    "vincular ", "grupo", "limite ", "desfazer", "desfaz",
)


def _parece_nova_intencao(mensagem: str) -> bool:
    lower = (mensagem or "").strip().lower()
    if not lower:
        return False
    if any(lower.startswith(p) for p in _PREFIXOS_NOVA_INTENCAO):
        return True
    return parece_comando_natural(mensagem)


def _fora_do_esperado(uid: int, mensagem: str) -> str:
    """
    Chamado quando a resposta não serve pra pergunta em aberto.

    29/08/2026 (pedido do Lucas, revendo a decisão de 24/07 abaixo): NUNCA
    mais devolve "" de verdade, exceto pro único caso em que vale a pena
    economizar 1 chamada de LLM — ruído óbvio (`parser.parece_ruido`: "kkkk",
    emoji solto, "ok" sem mais nada). Qualquer outra coisa passa pela IA
    (mesmo classificador de `_tentar_fallback_ia`) e SEMPRE volta com uma
    resposta: se a IA reconhecer uma intenção de verdade, processa; se não
    reconhecer nada (indefinido), devolve um lembrete em vez de silêncio.

    Histórico da decisão original (24/07/2026, mantido por contexto): "se a
    próxima mensagem for diferente do solicitado... o bot deve apenas
    ignorar... quando solicitar sim ou não, se a pessoa responder outra
    coisa, o bot simplesmente ignora". Isso cobria bem "kkkk", mas tinha um
    buraco maior do que o buraco original (COMANDO NOVO com sessão aberta,
    corrigido então com `_parece_nova_intencao`): qualquer mensagem com
    conteúdo real que não fosse um prefixo conhecido nem tivesse estrutura
    de ordem (ex: uma pergunta como "qual foi meu último abastecimento?")
    também caía no silêncio — o mesmo problema, só que mais raro. Chamar a
    IA em vez de aplicar um silêncio genérico resolve os dois de uma vez.
    """
    if _parece_nova_intencao(mensagem) or parece_correcao(mensagem):
        deletar_sessao(uid)
        resultado = _despachar_comando(uid, mensagem)
        if resultado is not None:
            return resultado
        return _processar_input_livre(uid, mensagem)

    if parece_ruido(mensagem):
        return ""

    categorias = get_categorias(uid)
    formas     = get_formas_pagamento(uid)
    resultado  = interpretar_mensagem(mensagem, categorias, formas)
    resposta   = _processar_resultado_classificacao(uid, resultado)

    if resposta is not None:
        # IA achou uma intenção de verdade — abandona a pergunta pendente,
        # mesmo raciocínio de `_parece_nova_intencao` acima.
        deletar_sessao(uid)
        return resposta

    # Indefinido de verdade (nem ruído, nem intenção reconhecível): nunca
    # muda, mas também não inventa dado — só lembra que há algo pendente. A
    # sessão continua viva (timeout de 5 min de `sessoes` é quem encerra).
    return (
        "🤔 Não entendi.\n\n"
        "Ainda estou esperando sua resposta pra continuar — ou mande "
        "*cancelar* pra encerrar."
    )


# ---------------------------------------------------------------------------
# Onboarding — setup guiado para novos usuários
# ---------------------------------------------------------------------------

# Mantido só como referência histórica do que era aceito antes — a checagem
# real agora é `eh_negativo` (utils/respostas.py), que cobre este conjunto e
# muito mais ("nem", "deixa", "depois", "👎"...). O onboarding é o primeiro
# contato da pessoa com o bot; travar num "pular" não reconhecido ali é o
# pior lugar possível pra ter atrito.
_NAO = {"nao", "não", "n", "no", "não quero", "nao quero", "pular", "skip"}


def _processar_onboarding(uid: int, sessao: dict, mensagem: str) -> str:
    etapa = sessao["etapa"]
    dados = get_dados_temp(sessao)
    txt   = mensagem.strip()
    lower = txt.lower()

    # ── Passo 1: nome do usuário ────────────────────────────────────────────
    if etapa == "onboarding_nome":
        nome = txt or "Usuário"
        set_nome_usuario(uid, nome)
        atualizar_sessao(uid, etapa="onboarding_grupo", timeout_minutos=30)
        return (
            f"Prazer, *{nome}*! 😊\n\n"
            "Qual o nome do seu grupo familiar?\n"
            "_Ex: Família Silva, Casal, Minha Conta_"
        )

    # ── Passo 2: nome do grupo ──────────────────────────────────────────────
    if etapa == "onboarding_grupo":
        nome_grupo = txt or "Família"
        criar_grupo(uid, nome_grupo)
        # Limpa as formas padrão criadas automaticamente — o usuário vai definir as suas
        usuario_atual = get_usuario(uid) or {}
        gid = usuario_atual.get("grupo_id")
        if gid:
            limpar_formas_grupo(gid)
        atualizar_sessao(
            uid, etapa="onboarding_membro",
            dados_temp={"grupo_id": gid, "membros": 0},
            timeout_minutos=30,
        )
        return (
            f"✅ Grupo *{nome_grupo}* criado!\n\n"
            "👥 Quer adicionar uma pessoa ao grupo?\n"
            "Digite o número com DDD _(ex: 44912345678)_ ou *não*"
        )

    # ── Passo 3: membros do grupo ───────────────────────────────────────────
    if etapa == "onboarding_membro":
        gid = dados.get("grupo_id")
        membros = dados.get("membros", 0)

        if eh_negativo(lower):
            # Avança para formas de pagamento
            atualizar_sessao(
                uid, etapa="onboarding_forma",
                dados_temp={"grupo_id": gid, "formas": 0},
                timeout_minutos=30,
            )
            return (
                "💳 *Formas de pagamento*\n\n"
                "Vamos cadastrar como vocês pagam. Digite nome + limite.\n"
                "_Ex: Cartão 3000 | Pix 1500 | Nubank_ (sem limite)\n\n"
                "Ou *não* para usar os padrão _(Cartão / Pix / Ticket)_"
            )

        jid = _normalizar_telefone(txt)
        if not jid:
            return (
                "❌ Número inválido.\n"
                "Digite com DDD _(ex: 44912345678)_ ou *não* para pular."
            )

        adicionar_membro_grupo(gid, jid)
        numero = "+" + jid.replace("@s.whatsapp.net", "")
        membros += 1
        atualizar_sessao(
            uid, etapa="onboarding_membro",
            dados_temp={"grupo_id": gid, "membros": membros},
            timeout_minutos=30,
        )
        return (
            f"✅ *{numero}* adicionado!\n\n"
            "Quer adicionar outro membro?\n"
            "Digite o número _(ex: 44912345678)_ ou *não*"
        )

    # ── Passo 4: formas de pagamento ────────────────────────────────────────
    if etapa == "onboarding_forma":
        gid   = dados.get("grupo_id")
        formas = dados.get("formas", 0)

        if eh_negativo(lower):
            if formas == 0:
                # Nenhuma forma adicionada → restaura padrão
                restaurar_formas_padrao_grupo(uid, gid)
            return _onboarding_resumo(uid)

        # Valida formato: deve começar com letra (rejeita "267 VR", "123", etc.)
        if not re.match(r"^[A-Za-zÀ-ÿ]", txt):
            return (
                "❌ Formato inválido.\n"
                "Use: *Nome* ou *Nome Valor*\n"
                "_Ex: Cartão 3000 | VA | Pix 1500_\n\n"
                "Ou *não* para usar formas padrão."
            )

        # Tenta parsear "Nome Valor" ou só "Nome"
        m = re.match(r"^(.+?)\s+(\d{1,6}(?:[.,]\d{1,2})?)$", txt)
        if m:
            nome_forma = m.group(1).strip()
            limite     = float(m.group(2).replace(",", "."))
        else:
            nome_forma = txt
            limite     = None

        adicionar_forma_pagamento(uid, nome_forma, limite)
        formas += 1
        limite_str = f" _(R$ {limite:,.0f})_" if limite else " _(sem limite)_"
        atualizar_sessao(
            uid, etapa="onboarding_forma",
            dados_temp={"grupo_id": gid, "formas": formas},
            timeout_minutos=30,
        )
        return (
            f"✅ *{nome_forma}*{limite_str} adicionada!\n\n"
            "Deseja adicionar outra forma de pagamento?\n"
            "Digite _Nome + Valor_ _(ex: Nubank 2000)_ ou *não* para finalizar."
        )

    # ── Boas-vindas: usuário pré-adicionado define nome ────────────────────
    if etapa == "onboarding_welcome_nome":
        nome = txt or "Usuário"
        set_nome_usuario(uid, nome)
        deletar_sessao(uid)
        usuario_atual = get_usuario(uid) or {}
        gid = usuario_atual.get("grupo_id")
        grupo   = get_grupo(gid) if gid else None
        membros = get_membros_grupo(gid) if gid else []
        grupo_nome    = grupo["nome"] if grupo else "seu grupo"
        outros        = [m for m in membros if m["id"] != uid]
        membros_str   = ", ".join(_fmt_membro(m) for m in outros) if outros else "nenhum ainda"
        return (
            f"Prazer, *{nome}*! 😊\n\n"
            f"Você já faz parte do grupo *{grupo_nome}*!\n"
            f"👥 Membros: {membros_str}\n\n"
            "💡 Para registrar um gasto, envie: _valor categoria forma_\n"
            "_Ex: 50 mercado cartão_\n\n"
            "📊 *saldo* · *gastos* · *resumo* · *ajuda*"
        )

    return "❓ Sessão inválida. Digite *ajuda* para ver os comandos."


def _fmt_membro(m: dict) -> str:
    """Retorna nome amigável do membro: nome real ou número formatado."""
    nome = m.get("nome", "")
    tel  = m.get("telefone", "")
    if nome and nome != tel:
        return nome
    # JID → "+55..." legível
    digits = tel.replace("@s.whatsapp.net", "").replace("@lid", "")
    return f"+{digits}" if digits else tel


def _bloco_tutorial_completo() -> str:
    """
    Tutorial completo pós-configuração (Fase 3.4, D5: manter o onboarding
    guiado e anexar o tutorial fixo no final, em vez dos dois convivendo
    redundantes). Reusado por `_onboarding_resumo` (fim do onboarding guiado)
    e `_tutorial_grupo` (fluxo `grupo criar`) — texto único, não duas cópias
    que divergem: o tutorial de `grupo criar` já estava desatualizado antes
    dessa mudança, sem nada das Fases 3.1–3.5 (categoria, fixa, entrada,
    parcelamento).
    """
    return (
        "─────────────────────────\n"
        "💸 *Registrar gastos:*\n\n"
        "💬 *Texto:*\n"
        "_50 mercado cartão_\n"
        "_gastei 120,90 no restaurante no pix_\n"
        "_notebook 1103,04 em 12x no cartão_ — parcelado\n\n"
        "🎤 *Áudio:* fale o gasto normalmente.\n"
        "Ex: _\"cinquenta reais no mercado no cartão\"_\n\n"
        "📸 *Foto de comprovante:* envie a foto — a IA lê o valor e registra automaticamente.\n\n"
        "─────────────────────────\n"
        "📈 *Registrar entrada/receita:*\n"
        "_recebi 2000 de salário_ ou *entrada 2000 salário*\n\n"
        "─────────────────────────\n"
        "📅 *Despesas fixas (lançam sozinhas todo mês):*\n"
        "• *fixa add Aluguel 1200 dia 5*\n"
        "• *fixa listar* · *fixa remover Nome*\n\n"
        "─────────────────────────\n"
        "📂 *Categorias personalizadas:*\n"
        "• *categoria add Nome* · *categoria remover Nome* · *categoria listar*\n\n"
        "─────────────────────────\n"
        "📊 *Consultas:*\n"
        "• *saldo* — saldo de cada forma\n"
        "• *gastos* — últimos 5 gastos\n"
        "• *resumo* — gastos, entradas e saldo do mês\n"
        "• *excluir ultimo* — remove o último gasto (parcela pergunta antes)\n"
        "• *editar ultimo 45,90* — corrige o valor do último\n\n"
        "ℹ️ *ajuda* — todos os comandos"
    )


def _onboarding_resumo(uid: int) -> str:
    """Finaliza onboarding e exibe resumo completo da configuração + tutorial (D5)."""
    deletar_sessao(uid)
    usuario = get_usuario(uid) or {}
    nome    = usuario.get("nome") or "você"
    gid     = usuario.get("grupo_id")
    grupo   = get_grupo(gid) if gid else None
    membros = get_membros_grupo(gid) if gid else []
    formas  = get_formas_pagamento(uid)

    linhas = [f"🎉 *Tudo pronto, {nome}!*\n"]

    if grupo:
        linhas.append(f"👨‍👩‍👧 *Grupo:* {grupo['nome']}")
    if membros:
        nomes_membros = [_fmt_membro(m) for m in membros]
        linhas.append(f"👥 *Membros:* {', '.join(nomes_membros)}")

    if formas:
        linhas.append("\n💳 *Formas de pagamento:*")
        for f in formas:
            lim = f" — R$ {float(f['limite_mensal']):,.0f}" if f.get("limite_mensal") else " — sem limite"
            linhas.append(f"• {f['nome']}{lim}")

    linhas.append("\n" + _bloco_tutorial_completo())

    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# Cenário 1 — input livre
# ---------------------------------------------------------------------------

def _processar_input_livre(uid: int, mensagem: str) -> str:
    valor = extrair_valor(mensagem)

    if valor is None:
        return _tentar_fallback_ia(uid, mensagem)

    # 24/07/2026 — a frase TEM número, mas tem cara de ordem sobre o bot
    # ("adiciona a forma de pgto teste com limite de 2999"). Sem este
    # desvio, qualquer número na frase sequestrava a mensagem pro fluxo de
    # gasto e a IA nunca era consultada (bug do print do Lucas: caiu no
    # menu "Qual a forma de pagamento?" em vez de criar a forma).
    #
    # Só desvia quando a IA CONFIRMA que é comando — se ela discordar,
    # segue o fluxo de gasto normal logo abaixo, com o valor que o regex
    # já extraiu (determinístico, não a suposição da IA). O custo de um
    # falso positivo do filtro é 1 chamada de LLM, não um registro errado.
    if parece_comando_natural(mensagem):
        resposta_comando = _tentar_comando_natural(uid, mensagem)
        if resposta_comando is not None:
            return resposta_comando

    # Entrada/receita (Fase 3.5) — checado antes do fluxo de gasto: entrada
    # não precisa de categoria/forma, então não faz sentido cair no menu
    # guiado de gasto por faltar uma delas.
    if eh_entrada(mensagem):
        return _registrar_entrada_e_confirmar(uid, valor, mensagem)

    categorias = get_categorias(uid)
    formas     = get_formas_pagamento(uid)
    categoria  = extrair_categoria(mensagem, categorias)
    forma      = extrair_forma_pagamento(mensagem, formas)
    parcelas   = extrair_parcelas(mensagem)

    # Data explícita no fim da mensagem (03/08/2026, pedido do Lucas: "...
    # 01-08" registra com data 01/08, não hoje — ver parser.extrair_data).
    # Tira o token da data ANTES de montar a descrição (limpar_descricao só
    # sabe tirar valor/categoria/forma, não data) — senão "01-08" sobrava
    # solto na Descrição. Só compra parcelada fica de fora por enquanto:
    # cada parcela já calcula sua própria competência mês a mês
    # (services/parcelamento.py), misturar com uma data manual da 1ª
    # parcela é conta pra outro dia, não pedida agora.
    data_gasto = extrair_data(mensagem)
    mensagem_para_descricao = mensagem
    if data_gasto and not parcelas:
        partes = mensagem.rsplit(None, 1)
        mensagem_para_descricao = partes[0] if len(partes) > 1 else ""

    if categoria and forma:
        descricao = limpar_descricao(mensagem_para_descricao, valor, categoria, forma)
        if parcelas:
            return _registrar_parcelado_e_confirmar(uid, forma, categoria, valor, parcelas, descricao)
        return _registrar_e_confirmar(uid, forma, categoria, valor, descricao, data=data_gasto)

    # Fase 3.6 estendida (24/07/2026, pedido do Lucas: "IA consiga também
    # alocar gastos pelo entendimento da mensagem") — palavra-chave não
    # achou categoria e/ou forma (ex: "50 remédio" não bate em nenhum
    # alias, mas é claramente Farmácia). Só chama IA pro que faltou —
    # completar_categoria_forma nunca chama se os dois já foram achados
    # (esse caso já retornou acima).
    categoria, forma = completar_categoria_forma(mensagem, categorias, formas, categoria, forma)

    # A IA fechou os dois campos que faltavam: registra DIRETO, sem pedir
    # confirmação (revisão de 24/07/2026 — pedido de fluidez do Lucas).
    #
    # A 1ª versão disto pedia "confirma? sim/não" aqui. Errado pelo critério
    # de REVERSIBILIDADE: gasto é a ação mais trivial de desfazer do bot
    # inteiro (*excluir ultimo* / *editar ultimo 45,90*), e o valor — a
    # única parte que dói errar — já veio de regex determinístico, não da
    # IA; ela só classificou categoria/forma. Cobrar uma ida-e-volta extra
    # no caminho MAIS comum do app pra proteger contra algo trivialmente
    # desfazível é justamente o atrito que o pedido de fluidez ataca.
    #
    # Confirmação continua obrigatória onde desfazer é caro ou impossível:
    # comando em linguagem natural (_propor_confirmacao_comando — mexe em
    # grupo/membros/formas) e gasto deduzido pela IA quando nem o VALOR era
    # certo (_propor_confirmacao_ia, via _tentar_fallback_ia).
    #
    # O que substitui a confirmação: a resposta de sucesso diz que a
    # classificação foi da IA e como corrigir — visível, sem bloquear.
    if categoria and forma:
        descricao = limpar_descricao(mensagem_para_descricao, valor, categoria, forma)
        if parcelas:
            return _registrar_parcelado_e_confirmar(
                uid, forma, categoria, valor, parcelas, descricao, deduzido_por_ia=True
            )
        return _registrar_e_confirmar(
            uid, forma, categoria, valor, descricao, deduzido_por_ia=True, data=data_gasto
        )

    etapa_inicial = "aguardando_categoria" if not categoria else "aguardando_pagamento"
    criar_sessao(
        uid,
        etapa=etapa_inicial,
        valor_temp=valor,
        categoria_temp=categoria["id"] if categoria else None,
        forma_temp=forma["id"] if forma else None,
        dados_temp={"parcelas": parcelas, "descricao": mensagem},
    )

    if not categoria:
        return _menu_categorias(categorias)
    return _menu_formas(formas)


# ---------------------------------------------------------------------------
# Fallback de IA (Fase 3.6) — mensagem sem comando reconhecido e sem valor
# extraído pelo parser regex.
# ---------------------------------------------------------------------------

def _tentar_comando_natural(uid: int, mensagem: str) -> str | None:
    """
    Consulta a IA especificamente pra "isso é um comando?", num caso onde o
    fluxo normal já teria decidido que é gasto (parser achou um número).

    Retorna None quando a IA NÃO reconhece um comando — sinal pra quem
    chama seguir com o fluxo de gasto original. Só a intenção 'comando'
    desvia: 'gasto' é deliberadamente ignorado aqui porque o caminho
    determinístico logo abaixo já extraiu o valor por regex e faz o
    trabalho melhor (a IA só seria consultada pra isso se o regex tivesse
    falhado, que é o caso de `_tentar_fallback_ia`).
    """
    categorias = get_categorias(uid)
    formas     = get_formas_pagamento(uid)
    resultado  = interpretar_mensagem(mensagem, categorias, formas)

    if resultado.get("intencao") == "comando":
        return _propor_confirmacao_comando(uid, resultado)

    # 'pergunta' também vale desviar: "como eu crio uma categoria?" tem
    # verbo + substantivo do domínio e pode ter número solto na frase.
    if resultado.get("intencao") == "pergunta":
        return f"💬 _Resposta da IA_\n\n{resultado['resposta']}"

    return None


def _processar_resultado_classificacao(uid: int, resultado: dict) -> str | None:
    """
    Despacha o dict que `services/ai_fallback.py::interpretar_mensagem`
    devolve pra ação correspondente. Extraído em 29/08/2026 pra ser
    compartilhado entre `_tentar_fallback_ia` (mensagem sem sessão) e
    `_fora_do_esperado` (mensagem com sessão pendente que não bateu em
    nenhum atalho barato) — sem isso, tratar "nunca ficar sem resposta" em
    `_fora_do_esperado` exigiria uma 2ª chamada de LLM pro mesmo texto só
    pra rotear de novo.

    Devolve None só pra intencao='indefinido' — sinal pra quem chama decidir
    o texto final (mensagem de exemplos em `_tentar_fallback_ia`, lembrete
    de pendência em `_fora_do_esperado`).
    """
    intencao = resultado.get("intencao")

    if intencao == "ajuda":
        return cmd_ajuda()

    if intencao == "cancelar":
        return "👍 Ok, nada foi registrado."

    if intencao == "gasto":
        return _propor_confirmacao_ia(uid, resultado)

    # 24/07/2026 — pergunta sobre o app ("como registro o pagamento?"): só
    # leitura, sem sessão nenhuma, a resposta já vem pronta (grounded na
    # referência de comandos, ver ai.py::_montar_prompt_fallback).
    if intencao == "pergunta":
        return f"💬 _Resposta da IA_\n\n{resultado['resposta']}"

    # 24/07/2026 — comando em linguagem natural ("adicione um membro..."):
    # NUNCA executa direto — pede confirmação, mesmo padrão de segurança do
    # fallback de gasto (ação pode alterar grupo/membros/formas/etc.).
    if intencao == "comando":
        return _propor_confirmacao_comando(uid, resultado)

    # 29/08/2026 — pergunta sobre o PRÓPRIO histórico ("qual foi o último
    # dia que abasteci o carro?"), diferente de 'pergunta' (que é sobre como
    # usar o bot). A IA só identificou a categoria (services/ai_fallback.py
    # já validou contra as categorias reais do usuário) — a resposta em si
    # vem de uma consulta determinística no banco, nunca inventada pela IA.
    # Sem sessão nenhuma: é leitura, não há nada pra confirmar ou desfazer.
    if intencao == "consulta_dados":
        return _responder_consulta_dados(uid, resultado["categoria"])

    # 29/08/2026 — "quais são as contas do mês?": mesma resposta do comando
    # digitado *contas*, só que reconhecida em linguagem natural. Leitura
    # pura, sem sessão.
    if intencao == "consulta_contas":
        return cmd_contas(uid)

    # 29/08/2026 — "paguei a fatura do cartão": NUNCA marca direto (mexe em
    # dinheiro já fechado) — sempre passa por _propor_marcar_conta_paga, que
    # pede confirmação (ou escolha, se ambíguo) antes de gravar.
    if intencao == "marcar_conta_paga":
        return _propor_marcar_conta_paga(uid, resultado["texto"])

    # 29/08/2026 — "todas as contas já foram pagas": diferente de
    # marcar_conta_paga (aponta 1 conta por nome), aqui não há nome nenhum
    # pra casar — busca a lista inteira de a_pagar e propõe marcar todas de
    # uma vez, sempre com confirmação (mesma trava de segurança).
    if intencao == "marcar_todas_pagas":
        return _propor_marcar_todas_pagas(uid)

    return None


def _tentar_fallback_ia(uid: int, mensagem: str) -> str:
    """
    services/ai_fallback.py já resolve os casos baratos ("ajuda"/"cancelar")
    sem chamar IA; só gasta 1 requisição de LLM quando vale a pena. Se a IA
    deduzir um gasto, NÃO insere direto — cria sessão de confirmação
    (D3-like: mesma lógica de "perguntar antes" já usada em exclusão de
    parcela), com o timeout de 5 min nativo de `sessoes` garantindo o
    cancelamento seguro se o usuário não responder.
    """
    categorias = get_categorias(uid)
    formas     = get_formas_pagamento(uid)
    resultado  = interpretar_mensagem(mensagem, categorias, formas)

    resposta = _processar_resultado_classificacao(uid, resultado)
    if resposta is not None:
        return resposta

    # Último recurso. Mostra exemplos CONCRETOS em vez de só nomear os
    # comandos (24/07/2026): quem cai aqui já demonstrou que não sabe a
    # sintaxe esperada — repetir "use *saldo*, *resumo*" não ensina o
    # formato de um gasto, que é o que a pessoa provavelmente queria.
    return (
        "🤔 Não entendi essa.\n\n"
        "💸 *Pra registrar um gasto:*\n"
        "_50 mercado cartão_\n"
        "_gastei 120,90 no restaurante no pix_\n\n"
        "📊 *Pra consultar:* *saldo* · *resumo* · *gastos*\n"
        "ℹ️ *ajuda* — lista tudo que dá pra fazer\n\n"
        "_Ou me pergunte direto, tipo: \"como adiciono alguém no grupo?\"_"
    )


def _responder_consulta_dados(uid: int, categoria: dict) -> str:
    """
    Resolve intencao='consulta_dados' (ver _tentar_fallback_ia): busca o
    gasto mais recente do usuário na categoria que a IA identificou e monta
    a resposta com o dado real do banco — a IA nunca inventa data nem valor
    aqui, só apontou QUAL categoria consultar.
    """
    gasto = get_ultimo_gasto_por_categoria(uid, categoria["id"])
    if not gasto:
        return f"📭 Nenhum gasto registrado em *{categoria['nome']}* ainda."

    val  = _brl(float(gasto["valor"]))
    data = gasto["data"]
    data_str = data.strftime("%d/%m/%Y") if hasattr(data, "strftime") else str(data)[:10]
    return (
        f"🗓 Último gasto em *{categoria['nome']}*: {data_str} — {val}\n"
        "_(*gastos* mostra os últimos 5 de todas as categorias)_"
    )


def _propor_confirmacao_ia(uid: int, resultado: dict, parcelas: int | None = None) -> str:
    valor     = resultado["valor"]
    categoria = resultado.get("categoria")
    forma     = resultado.get("forma")
    descricao = resultado.get("descricao") or ""

    criar_sessao(
        uid,
        etapa="aguardando_confirmacao_ia",
        valor_temp=valor,
        categoria_temp=categoria["id"] if categoria else None,
        forma_temp=forma["id"] if forma else None,
        dados_temp={"descricao": descricao, "parcelas": parcelas},
        timeout_minutos=5,
    )

    cat_txt      = categoria["nome"] if categoria else "categoria não identificada"
    forma_txt    = forma["nome"] if forma else "forma de pagamento não identificada"
    parcelas_txt = f" em {parcelas}x" if parcelas else ""
    return (
        f"🤔 Entendi que pode ser um gasto de {_brl(valor)}{parcelas_txt} — {cat_txt} ({forma_txt}).\n\n"
        "Confirma? Responda *sim* ou *não*."
    )


def _propor_confirmacao_comando(uid: int, resultado: dict) -> str:
    """
    Mesmo padrão de segurança de `_propor_confirmacao_ia`: a IA entendeu um
    comando em linguagem natural, mas só EXECUTA depois de "sim" — nunca
    direto (ver `_processar_confirmacao_comando`, que roteia pelo mesmo
    `_despachar_comando` usado por um comando digitado manualmente).
    """
    comando   = resultado["comando_sugerido"]
    descricao = resultado.get("descricao_acao") or comando

    criar_sessao(
        uid,
        etapa="aguardando_confirmacao_comando",
        dados_temp={"comando_sugerido": comando},
        timeout_minutos=5,
    )
    return (
        f"🤔 Entendi que você quer: *{descricao}*\n\n"
        f"Vou executar: `{comando}`\n\n"
        "Confirma? Responda *sim* ou *não*."
    )


def _propor_marcar_conta_paga(uid: int, texto: str) -> str:
    """
    Resolve intencao='marcar_conta_paga' (29/08/2026, "paguei a fatura do
    cartão"). services/contas_mes.py::buscar_contas_abertas casa o texto
    contra as contas em aberto e pode devolver:
    - 0 contas: nada bate, devolve direto sem criar sessão.
    - 1 conta: sem ambiguidade, pula pra confirmação.
    - 2+ contas: empate no placar de match (ex: dois cartões em aberto) —
      pede pra escolher por número antes de confirmar. Decisão do Lucas ao
      definir esta feature: nunca marcar a primeira que bateu, sempre
      perguntar quando não há certeza.
    """
    candidatas = buscar_contas_abertas(uid, texto)

    if not candidatas:
        return (
            f'🤔 Não achei nenhuma conta em aberto parecida com "{texto.strip()}".\n\n'
            "Veja o que está pendente com *contas*, ou descreva de outro jeito."
        )

    if len(candidatas) == 1:
        return _propor_confirmacao_conta_paga(uid, candidatas[0])

    criar_sessao(
        uid,
        etapa="aguardando_escolha_conta_paga",
        dados_temp={"opcoes": [
            {"chave": c["chave"], "descricao": c["descricao"], "valor": c["valor"]}
            for c in candidatas
        ]},
        timeout_minutos=5,
    )
    linhas = ["🤔 Achei mais de uma conta parecida — qual você pagou?", ""]
    for i, c in enumerate(candidatas, start=1):
        linhas.append(f"{i}. {c['descricao']} — {_brl(c['valor'])}")
    linhas.append("")
    linhas.append("_Responda com o número, ou *não* pra cancelar._")
    return "\n".join(linhas)


def _propor_confirmacao_conta_paga(uid: int, conta: dict) -> str:
    criar_sessao(
        uid,
        etapa="aguardando_confirmacao_conta_paga",
        dados_temp={"chave": conta["chave"], "descricao": conta["descricao"], "valor": conta["valor"]},
        timeout_minutos=5,
    )
    return (
        f"🤔 Marcar *{conta['descricao']}* ({_brl(conta['valor'])}) como paga?\n\n"
        "Responda *sim* ou *não*."
    )


def _processar_escolha_conta_paga(uid: int, sessao: dict, mensagem: str) -> str:
    if eh_negativo(mensagem):
        deletar_sessao(uid)
        return "👍 Ok, nada foi marcado."

    dados  = get_dados_temp(sessao)
    opcoes = dados.get("opcoes") or []
    txt    = mensagem.strip()

    if not txt.isdigit():
        return _fora_do_esperado(uid, mensagem)
    idx = int(txt) - 1
    if not (0 <= idx < len(opcoes)):
        return _fora_do_esperado(uid, mensagem)

    deletar_sessao(uid)
    return _propor_confirmacao_conta_paga(uid, opcoes[idx])


def _processar_confirmacao_conta_paga(uid: int, sessao: dict, mensagem: str) -> str:
    if not eh_afirmativo(mensagem):
        deletar_sessao(uid)
        return "👍 Ok, nada foi marcado."

    dados = get_dados_temp(sessao)
    deletar_sessao(uid)
    try:
        marcar_conta(uid, dados["chave"], pago=True)
    except AppError as exc:
        return f"❌ {exc.mensagem}"
    return f"✅ *{dados['descricao']}* ({_brl(dados['valor'])}) marcada como paga."


def _propor_marcar_todas_pagas(uid: int) -> str:
    """
    Resolve intencao='marcar_todas_pagas' (29/08/2026, "todas as contas já
    foram pagas"). Mesma trava de segurança de _propor_marcar_conta_paga —
    NUNCA marca direto: lista cada conta em aberto e pede UMA confirmação
    pra todas juntas (decisão do Lucas ao definir esta feature) — errar o
    "sim" aqui marca tudo de uma vez, mas confirmar 1 por 1 seria lento
    demais pra uso real.
    """
    a_pagar = listar_contas_mes(uid)["a_pagar"]
    if not a_pagar:
        return "✅ Já está tudo pago este mês — nenhuma conta em aberto."

    total = sum(c["valor"] for c in a_pagar)
    criar_sessao(
        uid,
        etapa="aguardando_confirmacao_todas_pagas",
        dados_temp={"contas": [
            {"chave": c["chave"], "descricao": c["descricao"], "valor": c["valor"]}
            for c in a_pagar
        ]},
        timeout_minutos=5,
    )
    linhas = [f"🤔 Marcar essas {len(a_pagar)} conta(s) como pagas?", ""]
    for c in a_pagar:
        linhas.append(f"• {c['descricao']} — {_brl(c['valor'])}")
    linhas.append("")
    linhas.append(f"Total: {_brl(total)}")
    linhas.append("")
    linhas.append("Responda *sim* ou *não*.")
    return "\n".join(linhas)


def _processar_confirmacao_todas_pagas(uid: int, sessao: dict, mensagem: str) -> str:
    if not eh_afirmativo(mensagem):
        deletar_sessao(uid)
        return "👍 Ok, nada foi marcado."

    dados  = get_dados_temp(sessao)
    contas = dados.get("contas") or []
    deletar_sessao(uid)

    marcadas, falhas = [], []
    for c in contas:
        try:
            marcar_conta(uid, c["chave"], pago=True)
            marcadas.append(c)
        except AppError as exc:
            falhas.append((c, exc.mensagem))

    linhas = [f"✅ {len(marcadas)} conta(s) marcada(s) como pagas."]
    if falhas:
        linhas.append("")
        linhas.append(f"⚠️ {len(falhas)} não deu pra marcar:")
        for c, erro in falhas:
            linhas.append(f"• {c['descricao']} — {erro}")
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# Cenário 2 — fluxo guiado
# ---------------------------------------------------------------------------

def _processar_sessao(uid: int, sessao: dict, mensagem: str) -> str:
    etapa = sessao["etapa"]

    if etapa == "aguardando_categoria":
        categorias = get_categorias(uid)
        cat = _selecionar_item(mensagem, categorias)
        if not cat:
            return _fora_do_esperado(uid, mensagem)

        # Bug real (17/07/2026): "VA atualizacao 264" já tinha a forma
        # detectada pelo parser (forma_temp) no input livre, mas esse passo
        # sempre pulava pro menu de forma perguntando de novo, descartando
        # o que já tinha sido reconhecido. Se forma_temp existe, registra
        # direto em vez de perguntar de novo.
        if sessao.get("forma_temp"):
            formas = get_formas_pagamento(uid)
            forma  = next((f for f in formas if f["id"] == sessao["forma_temp"]), None)
            dados    = get_dados_temp(sessao)
            parcelas = dados.get("parcelas")
            descricao = dados.get("descricao", "")
            deletar_sessao(uid)
            valor = float(sessao["valor_temp"])
            if not forma:
                # forma_temp apontava pra algo que sumiu entre a detecção e
                # agora (removida) — cai pro menu em vez de quebrar.
                criar_sessao(uid, etapa="aguardando_pagamento", valor_temp=valor,
                             categoria_temp=cat["id"], dados_temp=dados)
                return _menu_formas(get_formas_pagamento(uid))
            if parcelas:
                return _registrar_parcelado_e_confirmar(uid, forma, cat, valor, parcelas, descricao)
            return _registrar_e_confirmar(uid, forma, cat, valor, descricao)

        formas = get_formas_pagamento(uid)
        atualizar_sessao(uid, etapa="aguardando_pagamento", categoria_temp=cat["id"])
        return _menu_formas(formas)

    if etapa == "aguardando_pagamento":
        formas = get_formas_pagamento(uid)
        forma  = _selecionar_item(mensagem, formas)
        if not forma:
            return _fora_do_esperado(uid, mensagem)

        sessao_atual = get_sessao_ativa(uid)
        dados    = get_dados_temp(sessao_atual or sessao)
        parcelas = dados.get("parcelas")
        descricao = dados.get("descricao", "")
        deletar_sessao(uid)

        categorias = get_categorias(uid)
        cat_id = sessao_atual["categoria_temp"] if sessao_atual else sessao["categoria_temp"]
        cat    = next((c for c in categorias if c["id"] == cat_id), None)
        valor  = float(sessao_atual["valor_temp"] if sessao_atual else sessao["valor_temp"])

        if parcelas:
            return _registrar_parcelado_e_confirmar(uid, forma, cat, valor, parcelas, descricao)
        return _registrar_e_confirmar(uid, forma, cat, valor, descricao)

    if etapa == "aguardando_confirmacao_exclusao_parcela":
        return _processar_confirmacao_exclusao_parcela(uid, sessao, mensagem)

    if etapa == "aguardando_confirmacao_ia":
        return _processar_confirmacao_ia(uid, sessao, mensagem)

    if etapa == "aguardando_confirmacao_comando":
        return _processar_confirmacao_comando(uid, sessao, mensagem)

    if etapa == "aguardando_escolha_conta_paga":
        return _processar_escolha_conta_paga(uid, sessao, mensagem)

    if etapa == "aguardando_confirmacao_conta_paga":
        return _processar_confirmacao_conta_paga(uid, sessao, mensagem)

    if etapa == "aguardando_confirmacao_todas_pagas":
        return _processar_confirmacao_todas_pagas(uid, sessao, mensagem)

    return "❓ Sessão inválida. Envie um novo valor para começar."


def _processar_confirmacao_exclusao_parcela(uid: int, sessao: dict, mensagem: str) -> str:
    """D3 (Fase 3.2): 'excluir ultimo' numa parcela pergunta antes de excluir —
    só *esta* ou a compra *inteira*. Qualquer outra resposta mantém a sessão
    viva (retry), até o timeout de 5 min cancelar tudo com segurança."""
    dados    = get_dados_temp(sessao)
    resposta = mensagem.strip().lower()

    # "não"/"cancela" aqui é intenção clara de desistir da exclusão — antes
    # caía no retry genérico ("responda esta ou inteira") e a pessoa ficava
    # presa até o timeout de 5 min sem um jeito óbvio de sair (24/07/2026).
    if eh_negativo(mensagem):
        deletar_sessao(uid)
        return "👍 Ok, nada foi excluído."

    if resposta in ("esta", "essa", "só esta", "so esta", "somente esta", "1"):
        deletar_sessao(uid)
        gasto = excluir_gasto_por_id(dados["gasto_id"])
        if not gasto:
            return "❌ Gasto não encontrado (talvez já tenha sido excluído)."
        val   = _brl(float(gasto["valor"]))
        cat   = gasto.get("categoria_nome") or "?"
        forma = gasto.get("forma_nome") or "?"
        return f"🗑 *Parcela excluída:* {val} — {cat} — {forma}"

    if resposta in ("inteira", "compra inteira", "tudo", "todas", "2"):
        deletar_sessao(uid)
        compra = excluir_compra_parcelada(dados["compra_parcelada_id"])
        if not compra:
            return "❌ Compra parcelada não encontrada (talvez já tenha sido excluída)."
        val = _brl(float(compra["valor_total"]))
        return f"🗑 *Compra parcelada excluída inteira:* {val} — {compra.get('descricao') or '?'}"

    return _fora_do_esperado(uid, mensagem)


def _processar_confirmacao_ia(uid: int, sessao: dict, mensagem: str) -> str:
    """
    Fase 3.6 (D-fallback): só resposta afirmativa insere o gasto sugerido
    pela IA.

    Revisão de 24/07/2026 (fluidez): três estados em vez de dois. Antes,
    QUALQUER coisa fora de ("sim","s","confirma","confirmar") cancelava —
    "ok"/"pode"/"isso"/"👍" (respostas normais de WhatsApp) jogavam o
    registro fora sem a pessoa entender o motivo, e um cancelamento
    acidental era indistinguível de um "não" de verdade. Agora resposta
    ambígua NÃO cancela: mantém a sessão e pergunta de novo (o timeout de
    5 min de `sessoes` segue sendo a rede de segurança). Ver
    utils/respostas.py pro porquê de conjunto curado em vez de fuzzy.
    """
    if eh_negativo(mensagem):
        deletar_sessao(uid)
        return "👍 Ok, nada foi registrado."

    if not eh_afirmativo(mensagem):
        # Silêncio, não "❓ não entendi" (24/07/2026, pedido do Lucas).
        # Sessão preservada: a pessoa ainda pode responder *sim* depois.
        return _fora_do_esperado(uid, mensagem)

    deletar_sessao(uid)

    valor     = float(sessao["valor_temp"])
    dados     = get_dados_temp(sessao)
    descricao = dados.get("descricao", "")
    parcelas  = dados.get("parcelas")
    cat_id    = sessao.get("categoria_temp")
    forma_id  = sessao.get("forma_temp")

    # A IA não conseguiu deduzir categoria e/ou forma com confiança —
    # cai no mesmo fluxo guiado do input livre normal, sem perder o valor
    # já confirmado pelo usuário. dados_temp propagado (bug pré-existente:
    # antes descricao/parcelas se perdiam aqui, virando "" e sem parcelamento
    # no registro final caso o usuário ainda precisasse escolher categoria
    # ou forma manualmente depois de confirmar a dedução parcial da IA).
    if not cat_id or not forma_id:
        categorias = get_categorias(uid)
        formas     = get_formas_pagamento(uid)
        etapa_inicial = "aguardando_categoria" if not cat_id else "aguardando_pagamento"
        criar_sessao(
            uid, etapa=etapa_inicial, valor_temp=valor,
            categoria_temp=cat_id, forma_temp=forma_id,
            dados_temp={"parcelas": parcelas, "descricao": descricao},
        )
        return _menu_categorias(categorias) if not cat_id else _menu_formas(formas)

    categorias = get_categorias(uid)
    formas     = get_formas_pagamento(uid)
    categoria  = next((c for c in categorias if c["id"] == cat_id), None)
    forma      = next((f for f in formas if f["id"] == forma_id), None)

    if parcelas:
        return _registrar_parcelado_e_confirmar(uid, forma, categoria, valor, parcelas, descricao)
    return _registrar_e_confirmar(uid, forma, categoria, valor, descricao)


def _processar_confirmacao_comando(uid: int, sessao: dict, mensagem: str) -> str:
    """Mesmos três estados de `_processar_confirmacao_ia` — e aqui o retry
    em resposta ambígua importa ainda mais: comando mexe em grupo/membros/
    formas, então perder a sessão por causa de um "ok" não reconhecido
    obrigaria a pessoa a reescrever a frase inteira em linguagem natural e
    torcer pra IA interpretar igual de novo."""
    if eh_negativo(mensagem):
        deletar_sessao(uid)
        return "👍 Ok, nada foi executado."

    if not eh_afirmativo(mensagem):
        # Correção do comando pendente antes de cair no silêncio
        # (24/07/2026, print do Lucas: respondeu "falei errado, o nome
        # correto é teste123" e o bot ficou mudo). A frase sozinha não
        # significa nada — só colada no comando em aberto —, então vai pra
        # IA COM esse contexto, não pelo classificador de frase isolada.
        if parece_correcao(mensagem) and not _parece_nova_intencao(mensagem):
            pendente = get_dados_temp(sessao).get("comando_sugerido", "")
            corrigido = interpretar_correcao_comando(pendente, mensagem) if pendente else None
            if corrigido:
                return _propor_confirmacao_comando(uid, corrigido)
        return _fora_do_esperado(uid, mensagem)

    deletar_sessao(uid)

    dados   = get_dados_temp(sessao)
    comando = dados.get("comando_sugerido", "")
    resultado = _despachar_comando(uid, comando)
    if resultado is None:
        # Salvaguarda: services/ai_fallback.py já valida que comando_sugerido
        # começa com um prefixo conhecido antes de chegar aqui, então isso
        # não deveria acontecer — mas se acontecer (ex: prefixo bateu mas o
        # resto da sintaxe ficou errado, tipo "fixa add" sem os campos
        # completos), não pode travar o usuário numa mensagem confusa.
        return "❌ Não consegui executar esse comando. Tente digitar manualmente."
    return resultado


# ---------------------------------------------------------------------------
# Registro e confirmação
# ---------------------------------------------------------------------------

def _registrar_e_confirmar(uid: int, forma: dict, categoria: dict,
                            valor: float, descricao: str,
                            deduzido_por_ia: bool = False,
                            data: date = None) -> str:
    usuario  = get_usuario(uid) or {}
    nome     = usuario.get("nome") or usuario.get("telefone", "")
    grupo_id = usuario.get("grupo_id")

    registrar_gasto(
        uid, forma["id"], categoria["id"], valor, descricao,
        grupo_id=grupo_id, dia_fechamento=forma.get("dia_fechamento"), data=data,
    )
    saldo = get_saldo_forma(uid, forma["id"])

    gasto_mes  = float(saldo["gasto_mes"])
    limite     = float(saldo["limite_mensal"]) if saldo["limite_mensal"] else None
    forma_nome = saldo["nome"]
    cat_nome   = categoria["nome"] if categoria else "Outros"

    linhas = [
        f"✅ *Registrado por {nome}!*",
        f"💰 {_brl(valor)} — {cat_nome}",
        f"💳 {forma_nome}",
    ]

    # Mostra a data só quando NÃO é hoje — visível pra pessoa confirmar que
    # o "01-08" no fim da mensagem foi entendido certo (transparência, sem
    # bloquear com confirmação — mesmo raciocínio do aviso "categoria/forma
    # deduzidas pela IA" logo abaixo).
    if data and data != date.today():
        linhas.append(f"🗓 Data: {data.strftime('%d/%m/%Y')}")

    if limite:
        sobra = limite - gasto_mes
        pct   = (gasto_mes / limite) * 100
        linhas.append(f"*Saldo Disponível: {_brl(sobra)}*")
        linhas.append(f"Total: {_brl(gasto_mes)} de {_brl(limite)}")
        if gasto_mes > limite:
            linhas.append(f"🚨 Limite do {forma_nome} ultrapassado!")
        elif pct >= 80:
            linhas.append(f"⚠️ Já foi usado {pct:.0f}% do limite do {forma_nome}!")
    else:
        linhas.append(f"Total: {_brl(gasto_mes)} gastos este mês")

    if deduzido_por_ia:
        linhas.append("")
        linhas.append("_🤖 Categoria/forma deduzidas pela IA — se errei, *excluir ultimo*._")

    return "\n".join(linhas)


def _registrar_parcelado_e_confirmar(uid: int, forma: dict, categoria: dict,
                                      valor_total: float, parcelas: int,
                                      descricao: str,
                                      deduzido_por_ia: bool = False) -> str:
    """Fase 3.2 — compra parcelada: cria a compra + N gastos (services/parcelamento.py)
    e confirma mostrando quantas parcelas, valor de cada uma e a competência da 1ª."""
    usuario  = get_usuario(uid) or {}
    nome     = usuario.get("nome") or usuario.get("telefone", "")
    grupo_id = usuario.get("grupo_id")

    compra, gastos_criados, valor_parcela = criar_compra_parcelada(
        uid, grupo_id, forma, categoria, valor_total, parcelas, descricao
    )
    competencia_1a = gastos_criados[0]["competencia"]
    cat_nome = categoria["nome"] if categoria else "Outros"

    linhas = [
        f"✅ *Registrado por {nome}!*",
        f"💰 {_brl(valor_total)} em {parcelas}x de {_brl(valor_parcela)}",
        f"📂 {cat_nome} — 💳 {forma['nome']}",
        f"🗓 1ª parcela em {formatar_competencia(competencia_1a)}",
    ]
    if deduzido_por_ia:
        linhas.append("")
        linhas.append("_🤖 Categoria/forma deduzidas pela IA — se errei, *excluir ultimo*._")
    return "\n".join(linhas)


def _registrar_entrada_e_confirmar(uid: int, valor: float, descricao: str) -> str:
    """Fase 3.5 — entrada não passa pelo fluxo de gasto (sem categoria/forma,
    sem afetar saldo por forma de pagamento). Confirma com o total do mês."""
    usuario = get_usuario(uid) or {}
    nome    = usuario.get("nome") or usuario.get("telefone", "")

    registrar_entrada(uid, valor, descricao)
    total_mes = get_total_entradas_mes(uid)

    return (
        f"✅ *Entrada registrada por {nome}!*\n"
        f"📈 {_brl(valor)}\n"
        f"Total de entradas este mês: {_brl(total_mes)}"
    )


# ---------------------------------------------------------------------------
# Comandos extras
# ---------------------------------------------------------------------------
#
# _normalizar_telefone importado de utils/telefone.py (Fase A do
# AUDITORIA_E_PLANO_CADASTRO.md, corrige F1) — a versão que existia aqui
# antes não tinha a correção do 9º dígito que app.py:_normalizar_jid já
# tinha, então bot e web podiam gerar formatos diferentes pro mesmo número
# dependendo de qual caminho de código processava. Agora é uma função só.


def _cmd_apelido(uid: int, lower: str) -> str:
    partes = lower.split(None, 1)
    if len(partes) < 2:
        return "❌ Use: *apelido SeuNome*"
    nome = partes[1].strip()
    set_nome_usuario(uid, nome)
    return f"✅ Nome atualizado para *{nome}*!"


def _cmd_vincular(uid: int, lower: str) -> str:
    """
    vincular 44912345678  →  normaliza, cria grupo (se não tiver) e adiciona o parceiro.
    Aceita qualquer formato: com ou sem +55, com ou sem DDD completo.
    """
    partes = lower.split(None, 1)
    if len(partes) < 2:
        return "❌ Use: *vincular 44912345678* (DDD + número)"

    jid = _normalizar_telefone(partes[1])
    if not jid:
        return (
            "❌ Número inválido.\n"
            "Use: *vincular 44912345678* (DDD + número)\n"
            "Ou: *vincular +5544912345678* (com código do país)"
        )

    usuario = get_usuario(uid) or {}
    gid = usuario.get("grupo_id")

    # Se ainda não está em grupo, cria um automaticamente
    if not gid:
        criar_grupo(uid, "Casal")
        usuario = get_usuario(uid) or {}
        gid = usuario.get("grupo_id")

    try:
        membro, ja_em_grupo = adicionar_membro_com_limite(uid, jid)
    except AppError as exc:
        return f"❌ {exc.mensagem}"
    if ja_em_grupo:
        if membro.get("grupo_id") == gid:
            return "ℹ️ Esse número já está vinculado ao seu grupo."
        return "❌ Esse número já pertence a outro grupo."

    numero_display = "+" + jid.replace("@s.whatsapp.net", "")
    return (
        f"✅ *{numero_display}* vinculado!\n\n"
        "Agora vocês compartilham o mesmo saldo e registros.\n"
        "Configure as formas de pagamento com *forma add* ou veja o *saldo*."
    )


def _cmd_forma(uid: int, lower: str) -> str:
    partes = lower.split(None, 2)
    if len(partes) < 2:
        return "❌ Use: *forma add Nome 1000* ou *forma remover Nome*"

    acao = partes[1].lower()

    if acao in ("add", "adicionar"):
        if len(partes) < 3:
            return "❌ Use: *forma add Nome 1000*"
        tokens = partes[2].strip().rsplit(None, 1)
        if len(tokens) == 2 and re.match(r"^\d+([.,]\d{1,2})?$", tokens[1]):
            nome_forma = tokens[0].strip()
            limite     = float(tokens[1].replace(",", "."))
        else:
            nome_forma = partes[2].strip()
            limite     = None
        adicionar_forma_pagamento(uid, nome_forma, limite)
        limite_str = f" com limite de {_brl(limite)}" if limite else ""
        return f"✅ Forma *{nome_forma}* adicionada{limite_str}!"

    if acao in ("remover", "excluir", "deletar"):
        if len(partes) < 3:
            return "❌ Use: *forma remover Nome*"
        nome_forma = partes[2].strip()
        if remover_forma_pagamento(uid, nome_forma):
            return f"✅ Forma *{nome_forma}* removida!"
        return f"❌ Forma '{nome_forma}' não encontrada."

    return "❌ Use: *forma add Nome 1000* ou *forma remover Nome*"


def _cmd_categoria(uid: int, lower: str) -> str:
    """
    categoria listar        -> lista globais + customizadas do grupo
    categoria add Nome      -> cria customizada pro grupo do usuário
    categoria remover Nome  -> remove customizada do grupo (globais nunca somem, G5)
    """
    partes = lower.split(None, 2)
    if len(partes) < 2:
        return "❌ Use: *categoria add Nome*, *categoria remover Nome* ou *categoria listar*"

    acao = partes[1].lower()

    if acao == "listar":
        categorias = get_categorias(uid)
        linhas = ["📂 *Categorias disponíveis:*"]
        for c in categorias:
            tag = " _(personalizada)_" if c.get("grupo_id") is not None else ""
            linhas.append(f"• {c['nome']}{tag}")
        return "\n".join(linhas)

    if acao in ("add", "adicionar"):
        if len(partes) < 3:
            return "❌ Use: *categoria add Nome*"
        usuario = get_usuario(uid) or {}
        if not usuario.get("grupo_id"):
            return (
                "❌ Categorias personalizadas exigem um grupo.\n"
                "Crie um com *grupo criar Nome* primeiro."
            )
        nome = partes[2].strip()
        cat = adicionar_categoria(uid, nome)
        if not cat:
            return f"❌ Já existe uma categoria '{nome}' (padrão ou do seu grupo)."
        return f"✅ Categoria *{cat['nome']}* adicionada!"

    if acao in ("remover", "excluir", "deletar"):
        if len(partes) < 3:
            return "❌ Use: *categoria remover Nome*"
        nome = partes[2].strip()
        if remover_categoria(uid, nome):
            return f"✅ Categoria *{nome}* removida!"
        return f"❌ Categoria '{nome}' não encontrada entre as personalizadas do seu grupo."

    return "❌ Use: *categoria add Nome*, *categoria remover Nome* ou *categoria listar*"


def _cmd_fixa(uid: int, lower: str) -> str:
    """
    fixa add Aluguel 1200 dia 5  -> cria despesa fixa (lança sozinha todo dia 5)
    fixa listar                  -> lista despesas fixas ativas
    fixa remover Aluguel         -> desativa (soft-delete — não lança mais,
                                     mas não some o histórico já lançado)
    """
    partes = lower.split(None, 2)
    if len(partes) < 2:
        return "❌ Use: *fixa add Nome Valor dia DD*, *fixa remover Nome* ou *fixa listar*"

    acao = partes[1].lower()

    if acao == "listar":
        fixas = get_despesas_fixas(uid)
        if not fixas:
            return "📅 Nenhuma despesa fixa cadastrada."
        linhas = ["📅 *Despesas fixas:*"]
        for f in fixas:
            linhas.append(f"• {f['descricao']} — {_brl(float(f['valor']))} — todo dia {f['dia_lancamento']}")
        return "\n".join(linhas)

    if acao in ("add", "adicionar"):
        m = _FIXA_ADD_RE.match(lower)
        if not m:
            return "❌ Use: *fixa add Aluguel 1200 dia 5*"
        descricao = m.group(1).strip()
        valor     = float(m.group(2).replace(",", "."))
        dia       = int(m.group(3))
        if not (1 <= dia <= 31):
            return "❌ Dia inválido. Use um valor entre 1 e 31."
        criar_despesa_fixa(uid, descricao, valor, dia)
        return (
            f"✅ Despesa fixa *{descricao}* de {_brl(valor)} cadastrada — "
            f"lança sozinha todo dia {dia}."
        )

    if acao in ("remover", "excluir", "deletar"):
        if len(partes) < 3:
            return "❌ Use: *fixa remover Nome*"
        descricao = partes[2].strip()
        if desativar_despesa_fixa(uid, descricao):
            return f"✅ Despesa fixa *{descricao}* removida (não lança mais)."
        return f"❌ Despesa fixa '{descricao}' não encontrada."

    return "❌ Use: *fixa add Nome Valor dia DD*, *fixa remover Nome* ou *fixa listar*"


def _cmd_entrada(uid: int, mensagem: str) -> str:
    """Comando explícito de fallback (Fase 3.5): entrada 2000 salário.
    Complementa a detecção por palavra-chave em _processar_input_livre —
    útil quando a frase não usa nenhuma das palavras-chave (recebi/caiu/etc.)."""
    valor = extrair_valor(mensagem)
    if valor is None:
        return "❌ Use: *entrada 2000 salário*"
    return _registrar_entrada_e_confirmar(uid, valor, mensagem)


def _cmd_excluir(uid: int, lower: str) -> str:
    partes = lower.split()
    if len(partes) < 2 or partes[1] != "ultimo":
        return "❌ Use: *excluir ultimo*"

    # Peek antes de excluir: se for parcela de compra parcelada, D3 exige
    # perguntar "só esta x compra inteira" antes de mexer no banco.
    ultimo = get_ultimo_gasto(uid)
    if not ultimo:
        return "❌ Nenhum gasto registrado para excluir."

    if ultimo.get("compra_parcelada_id"):
        criar_sessao(
            uid,
            etapa="aguardando_confirmacao_exclusao_parcela",
            dados_temp={
                "gasto_id": ultimo["id"],
                "compra_parcelada_id": ultimo["compra_parcelada_id"],
            },
            timeout_minutos=5,
        )
        val   = _brl(float(ultimo["valor"]))
        num   = ultimo.get("parcela_num") or "?"
        total = ultimo.get("total_parcelas") or "?"
        return (
            f"🗑 Esse gasto é a parcela {num}/{total} de uma compra parcelada ({val}).\n\n"
            "Excluir *só essa parcela* ou a *compra inteira* (todas as parcelas)?\n"
            "Responda: *esta* ou *inteira*"
        )

    gasto = excluir_ultimo_gasto(uid)
    if not gasto:
        return "❌ Nenhum gasto registrado para excluir."
    val   = _brl(float(gasto["valor"]))
    cat   = gasto.get("categoria_nome") or "?"
    forma = gasto.get("forma_nome") or "?"
    return f"🗑 *Excluído:* {val} — {cat} — {forma}"


def _cmd_editar_ultimo(uid: int, lower: str) -> str:
    partes = lower.split()
    if len(partes) < 3:
        return "❌ Use: *editar ultimo 45,90*"
    try:
        novo_valor = float(partes[2].replace(",", "."))
    except ValueError:
        return "❌ Valor inválido. Use: *editar ultimo 45,90*"
    if editar_ultimo_gasto_valor(uid, novo_valor):
        return f"✅ Último gasto atualizado para {_brl(novo_valor)}"
    return "❌ Nenhum gasto registrado para editar."


# ---------------------------------------------------------------------------
# Grupos (contas compartilhadas)
# ---------------------------------------------------------------------------

def _cmd_grupo(uid: int, mensagem: str) -> str:
    usuario = get_usuario(uid) or {}
    gid     = usuario.get("grupo_id")
    partes  = mensagem.strip().split(None, 2)

    if len(partes) == 1:
        if not gid:
            return (
                "👨‍👩‍👧 Você não está em nenhum grupo.\n"
                "• *grupo criar Família* — cria um grupo com contas compartilhadas\n"
                "• *grupo add +5511999999999* — adiciona alguém depois de criar"
            )
        grupo   = get_grupo(gid) or {}
        membros = get_membros_grupo(gid)
        linhas  = [f"👨‍👩‍👧 *Grupo {grupo.get('nome', '')}*", "Membros:"]
        for m in membros:
            linhas.append(f"• {_fmt_membro(m)}")
        linhas.append("\n• *grupo add +55...* — adicionar membro")
        linhas.append("• *grupo sair* — sair do grupo")
        return "\n".join(linhas)

    acao = partes[1].lower()

    if acao == "criar":
        if gid:
            return "❌ Você já está em um grupo. Use *grupo sair* antes de criar outro."

        # "grupo criar Família" ou "grupo criar Família +5511999999999"
        resto       = partes[2].strip() if len(partes) > 2 else "Família"
        tokens      = resto.split()
        membro_tel  = None
        if tokens and tokens[-1].startswith("+"):
            membro_tel = tokens[-1]
            nome_grupo = " ".join(tokens[:-1]) or "Família"
        else:
            nome_grupo = resto

        criar_grupo(uid, nome_grupo)

        # Adiciona membro já na criação, se informado
        if membro_tel:
            jid = _normalizar_telefone(membro_tel)
            if jid:
                usuario_novo = get_usuario(uid)
                novo_gid     = usuario_novo.get("grupo_id") if usuario_novo else None
                if novo_gid:
                    adicionar_membro_grupo(novo_gid, jid)

        return _tutorial_grupo(nome_grupo, membro_tel)

    if acao == "tutorial":
        return _tutorial_grupo()

    if acao in ("add", "adicionar", "convidar"):
        if not gid:
            return "❌ Crie um grupo primeiro: *grupo criar Família*"
        if len(partes) < 3:
            return "❌ Use: *grupo add 44912345678*"
        jid = _normalizar_telefone(partes[2])
        if not jid:
            return "❌ Número inválido. Use: *grupo add 44912345678* (DDD + número)"

        try:
            membro, ja_em_grupo = adicionar_membro_com_limite(uid, jid)
        except AppError as exc:
            return f"❌ {exc.mensagem}"
        if ja_em_grupo:
            if membro.get("grupo_id") == gid:
                return "ℹ️ Essa pessoa já está no seu grupo."
            return "❌ Essa pessoa já pertence a outro grupo."
        numero_display = "+" + jid.replace("@s.whatsapp.net", "")
        return f"✅ *{numero_display}* adicionado ao grupo!"

    if acao == "sair":
        if not gid:
            return "❌ Você não está em nenhum grupo."
        sair_grupo(uid)
        return "✅ Você saiu do grupo. Suas formas de pagamento padrão foram restauradas."

    return "❌ Use: *grupo*, *grupo criar Nome*, *grupo add +55...* ou *grupo sair*"


# ---------------------------------------------------------------------------
# Tutorial de boas-vindas ao grupo
# ---------------------------------------------------------------------------

def _tutorial_grupo(nome_grupo: str = "", membro_tel: str = None) -> str:
    """
    Chamada em 2 contextos: logo após `grupo criar Nome` (nome_grupo
    preenchido, cabeçalho de confirmação) e por `grupo tutorial` (sem
    argumentos, só o tutorial — bug preexistente corrigido aqui: antes o
    cabeçalho aparecia como "Grupo  criado com saldo zerado!" mesmo sem
    grupo ter sido criado nessa chamada).
    """
    membro_linha = f"\n👥 *{membro_tel}* foi adicionado ao grupo!" if membro_tel else ""
    cabecalho = (
        f"✅ *Grupo {nome_grupo} criado com saldo zerado!*{membro_linha}\n\n"
        if nome_grupo else ""
    )
    return (
        cabecalho +
        "⚙️ *Antes de registrar gastos, configure as formas de pagamento:*\n"
        "• *forma add Nubank 2000* — adiciona com limite\n"
        "• *forma add Pix* — sem limite\n"
        "• *forma remover Cartão* — remove\n"
        "• *limite cartão 3000* — atualiza limite\n\n"
        + _bloco_tutorial_completo()
    )


# ---------------------------------------------------------------------------
# Menus de seleção
# ---------------------------------------------------------------------------

def _menu_categorias(categorias: list) -> str:
    linhas = ["📂 *Qual a categoria?*"]
    for i, c in enumerate(categorias, 1):
        linhas.append(f"{i}. {c['nome']}")
    return "\n".join(linhas)


def _menu_formas(formas: list) -> str:
    linhas = ["💳 *Qual a forma de pagamento?*"]
    for i, f in enumerate(formas, 1):
        linhas.append(f"{i}. {f['nome']}")
    return "\n".join(linhas)


def _selecionar_item(mensagem: str, items: list):
    txt = mensagem.strip()

    if txt.isdigit():
        idx = int(txt) - 1
        if 0 <= idx < len(items):
            return items[idx]

    txt_lower = txt.lower()
    for item in items:
        if txt_lower in item["nome"].lower() or item["nome"].lower() in txt_lower:
            return item

    melhor, melhor_score = None, 0.60
    for item in items:
        score = SequenceMatcher(None, txt_lower, item["nome"].lower()).ratio()
        if score > melhor_score:
            melhor_score = score
            melhor = item

    return melhor
