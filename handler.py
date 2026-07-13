"""
handler.py — lógica principal de processamento de mensagens do Finbot.
"""

import re
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
from services.ai_fallback import interpretar_mensagem
from services.grupos import adicionar_membro as adicionar_membro_com_limite
from utils.app_error import AppError
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
)
from comandos import cmd_saldo, cmd_resumo, cmd_limite, cmd_ajuda, cmd_gastos


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
        if verificar_sessao_expirada(uid):
            return (
                "⏱ _Registro cancelado por inatividade._\n"
                "Sua próxima mensagem será tratada como novo gasto."
            )

        # ── Comandos normais ────────────────────────────────────────────────
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

        # ── Input livre ─────────────────────────────────────────────────────
        return _processar_input_livre(uid, mensagem)

    except Exception as exc:
        logger.exception(f"Erro ao processar mensagem de {telefone}: {exc}")
        return "😕 Ocorreu um erro interno. Tente novamente em instantes."


# ---------------------------------------------------------------------------
# Onboarding — setup guiado para novos usuários
# ---------------------------------------------------------------------------

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

        if lower in _NAO:
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

        if lower in _NAO:
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

    if categoria and forma:
        if parcelas:
            return _registrar_parcelado_e_confirmar(uid, forma, categoria, valor, parcelas, mensagem)
        return _registrar_e_confirmar(uid, forma, categoria, valor, mensagem)

    etapa_inicial = "aguardando_categoria" if not categoria else "aguardando_pagamento"
    criar_sessao(
        uid,
        etapa=etapa_inicial,
        valor_temp=valor,
        categoria_temp=categoria["id"] if categoria else None,
        forma_temp=forma["id"] if forma else None,
        dados_temp={"parcelas": parcelas} if parcelas else None,
    )

    if not categoria:
        return _menu_categorias(categorias)
    return _menu_formas(formas)


# ---------------------------------------------------------------------------
# Fallback de IA (Fase 3.6) — mensagem sem comando reconhecido e sem valor
# extraído pelo parser regex.
# ---------------------------------------------------------------------------

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

    intencao = resultado.get("intencao")

    if intencao == "ajuda":
        return cmd_ajuda()

    if intencao == "cancelar":
        return "👍 Ok, nada foi registrado."

    if intencao == "gasto":
        return _propor_confirmacao_ia(uid, resultado)

    return (
        "🤔 Não entendi. Digite um valor (ex: *50* ou *50,90*) "
        "para registrar um gasto.\n"
        "Ou use: *saldo*, *resumo*, *gastos*, *ajuda*."
    )


def _propor_confirmacao_ia(uid: int, resultado: dict) -> str:
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
        dados_temp={"descricao": descricao},
        timeout_minutos=5,
    )

    cat_txt   = categoria["nome"] if categoria else "categoria não identificada"
    forma_txt = forma["nome"] if forma else "forma de pagamento não identificada"
    return (
        f"🤔 Entendi que pode ser um gasto de {_brl(valor)} — {cat_txt} ({forma_txt}).\n\n"
        "Confirma? Responda *sim* para registrar ou qualquer outra coisa para cancelar."
    )


# ---------------------------------------------------------------------------
# Cenário 2 — fluxo guiado
# ---------------------------------------------------------------------------

def _processar_sessao(uid: int, sessao: dict, mensagem: str) -> str:
    etapa = sessao["etapa"]

    if etapa == "aguardando_categoria":
        categorias = get_categorias(uid)
        cat = _selecionar_item(mensagem, categorias)
        if not cat:
            return f"❌ Categoria inválida.\n{_menu_categorias(categorias)}"

        formas = get_formas_pagamento(uid)
        atualizar_sessao(uid, etapa="aguardando_pagamento", categoria_temp=cat["id"])
        return _menu_formas(formas)

    if etapa == "aguardando_pagamento":
        formas = get_formas_pagamento(uid)
        forma  = _selecionar_item(mensagem, formas)
        if not forma:
            return f"❌ Forma inválida.\n{_menu_formas(formas)}"

        sessao_atual = get_sessao_ativa(uid)
        dados    = get_dados_temp(sessao_atual or sessao)
        parcelas = dados.get("parcelas")
        deletar_sessao(uid)

        categorias = get_categorias(uid)
        cat_id = sessao_atual["categoria_temp"] if sessao_atual else sessao["categoria_temp"]
        cat    = next((c for c in categorias if c["id"] == cat_id), None)
        valor  = float(sessao_atual["valor_temp"] if sessao_atual else sessao["valor_temp"])

        if parcelas:
            return _registrar_parcelado_e_confirmar(uid, forma, cat, valor, parcelas, "")
        return _registrar_e_confirmar(uid, forma, cat, valor, "")

    if etapa == "aguardando_confirmacao_exclusao_parcela":
        return _processar_confirmacao_exclusao_parcela(uid, sessao, mensagem)

    if etapa == "aguardando_confirmacao_ia":
        return _processar_confirmacao_ia(uid, sessao, mensagem)

    return "❓ Sessão inválida. Envie um novo valor para começar."


def _processar_confirmacao_exclusao_parcela(uid: int, sessao: dict, mensagem: str) -> str:
    """D3 (Fase 3.2): 'excluir ultimo' numa parcela pergunta antes de excluir —
    só *esta* ou a compra *inteira*. Qualquer outra resposta mantém a sessão
    viva (retry), até o timeout de 5 min cancelar tudo com segurança."""
    dados    = get_dados_temp(sessao)
    resposta = mensagem.strip().lower()

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

    return (
        "❓ Não entendi.\n"
        "Responda *esta* (só essa parcela) ou *inteira* (compra toda) —"
        " ou espere 5 min pra cancelar."
    )


def _processar_confirmacao_ia(uid: int, sessao: dict, mensagem: str) -> str:
    """Fase 3.6 (D-fallback): só 'sim/confirmar' insere o gasto sugerido
    pela IA. Qualquer outra resposta cancela (mesmo padrão de segurança de
    _processar_confirmacao_exclusao_parcela — mas aqui sem retry: resposta
    ambígua também cancela, porque o texto original já está perdido depois
    da 1ª interpretação e pedir de novo só devolveria outra suposição)."""
    resposta = mensagem.strip().lower()
    deletar_sessao(uid)

    if resposta not in ("sim", "s", "confirma", "confirmar"):
        return "👍 Ok, nada foi registrado."

    valor     = float(sessao["valor_temp"])
    dados     = get_dados_temp(sessao)
    descricao = dados.get("descricao", "")
    cat_id    = sessao.get("categoria_temp")
    forma_id  = sessao.get("forma_temp")

    # A IA não conseguiu deduzir categoria e/ou forma com confiança —
    # cai no mesmo fluxo guiado do input livre normal, sem perder o valor
    # já confirmado pelo usuário.
    if not cat_id or not forma_id:
        categorias = get_categorias(uid)
        formas     = get_formas_pagamento(uid)
        etapa_inicial = "aguardando_categoria" if not cat_id else "aguardando_pagamento"
        criar_sessao(
            uid, etapa=etapa_inicial, valor_temp=valor,
            categoria_temp=cat_id, forma_temp=forma_id,
        )
        return _menu_categorias(categorias) if not cat_id else _menu_formas(formas)

    categorias = get_categorias(uid)
    formas     = get_formas_pagamento(uid)
    categoria  = next((c for c in categorias if c["id"] == cat_id), None)
    forma      = next((f for f in formas if f["id"] == forma_id), None)

    return _registrar_e_confirmar(uid, forma, categoria, valor, descricao)


# ---------------------------------------------------------------------------
# Registro e confirmação
# ---------------------------------------------------------------------------

def _registrar_e_confirmar(uid: int, forma: dict, categoria: dict,
                            valor: float, descricao: str) -> str:
    usuario  = get_usuario(uid) or {}
    nome     = usuario.get("nome") or usuario.get("telefone", "")
    grupo_id = usuario.get("grupo_id")

    registrar_gasto(
        uid, forma["id"], categoria["id"], valor, descricao,
        grupo_id=grupo_id, dia_fechamento=forma.get("dia_fechamento"),
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

    return "\n".join(linhas)


def _registrar_parcelado_e_confirmar(uid: int, forma: dict, categoria: dict,
                                      valor_total: float, parcelas: int,
                                      descricao: str) -> str:
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
