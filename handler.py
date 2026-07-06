"""
handler.py — lógica principal de processamento de mensagens do Finbot.
"""

import re
from difflib import SequenceMatcher

from db import (
    get_or_create_usuario,
    get_usuario,
    get_categorias,
    get_formas_pagamento,
    registrar_gasto,
    get_saldo_forma,
    set_nome_usuario,
    adicionar_forma_pagamento,
    remover_forma_pagamento,
    excluir_ultimo_gasto,
    editar_ultimo_gasto_valor,
    get_grupo,
    get_membros_grupo,
    criar_grupo,
    adicionar_membro_grupo,
    sair_grupo,
    limpar_formas_grupo,
    restaurar_formas_padrao_grupo,
)
from sessao import (
    get_sessao_ativa,
    get_dados_temp,
    criar_sessao,
    atualizar_sessao,
    deletar_sessao,
    verificar_sessao_expirada,
)
from parser import extrair_valor, extrair_categoria, extrair_forma_pagamento
from comandos import cmd_saldo, cmd_resumo, cmd_limite, cmd_ajuda, cmd_gastos


def _brl(valor: float) -> str:
    s = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


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
        if lower.startswith("apelido "):
            return _cmd_apelido(uid, lower)
        if lower.startswith("vincular "):
            return _cmd_vincular(uid, lower)
        if lower == "grupo" or lower.startswith("grupo "):
            return _cmd_grupo(uid, mensagem)

        # ── Input livre ─────────────────────────────────────────────────────
        return _processar_input_livre(uid, mensagem)

    except Exception as exc:
        print(f"[Finbot ERROR] {exc}")
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
            "Digite o número com DDD _(ex: 44999604273)_ ou *não*"
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
                "Digite com DDD _(ex: 44999604273)_ ou *não* para pular."
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
            "Digite o número _(ex: 44999604273)_ ou *não*"
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


def _onboarding_resumo(uid: int) -> str:
    """Finaliza onboarding e exibe resumo completo da configuração."""
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

    linhas.append(
        "\n─────────────────────────\n"
        "💡 *Como registrar gastos:*\n"
        "💬 Texto: _50 mercado cartão_\n"
        "🎤 Áudio: fale o gasto normalmente\n"
        "📸 Foto: envie o comprovante\n\n"
        "📊 *saldo* · *gastos* · *resumo* · *ajuda*"
    )

    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# Cenário 1 — input livre
# ---------------------------------------------------------------------------

def _processar_input_livre(uid: int, mensagem: str) -> str:
    categorias = get_categorias()
    formas     = get_formas_pagamento(uid)

    valor     = extrair_valor(mensagem)
    categoria = extrair_categoria(mensagem, categorias)
    forma     = extrair_forma_pagamento(mensagem, formas)

    if valor is None:
        return (
            "🤔 Não entendi. Digite um valor (ex: *50* ou *50,90*) "
            "para registrar um gasto.\n"
            "Ou use: *saldo*, *resumo*, *gastos*, *ajuda*."
        )

    if categoria and forma:
        return _registrar_e_confirmar(uid, forma, categoria, valor, mensagem)

    etapa_inicial = "aguardando_categoria" if not categoria else "aguardando_pagamento"
    criar_sessao(
        uid,
        etapa=etapa_inicial,
        valor_temp=valor,
        categoria_temp=categoria["id"] if categoria else None,
        forma_temp=forma["id"] if forma else None,
    )

    if not categoria:
        return _menu_categorias(categorias)
    return _menu_formas(formas)


# ---------------------------------------------------------------------------
# Cenário 2 — fluxo guiado
# ---------------------------------------------------------------------------

def _processar_sessao(uid: int, sessao: dict, mensagem: str) -> str:
    etapa = sessao["etapa"]

    if etapa == "aguardando_categoria":
        categorias = get_categorias()
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
        deletar_sessao(uid)

        categorias = get_categorias()
        cat_id = sessao_atual["categoria_temp"] if sessao_atual else sessao["categoria_temp"]
        cat    = next((c for c in categorias if c["id"] == cat_id), None)
        valor  = float(sessao_atual["valor_temp"] if sessao_atual else sessao["valor_temp"])

        return _registrar_e_confirmar(uid, forma, cat, valor, "")

    return "❓ Sessão inválida. Envie um novo valor para começar."


# ---------------------------------------------------------------------------
# Registro e confirmação
# ---------------------------------------------------------------------------

def _registrar_e_confirmar(uid: int, forma: dict, categoria: dict,
                            valor: float, descricao: str) -> str:
    usuario  = get_usuario(uid) or {}
    nome     = usuario.get("nome") or usuario.get("telefone", "")
    grupo_id = usuario.get("grupo_id")

    registrar_gasto(uid, forma["id"], categoria["id"], valor, descricao, grupo_id=grupo_id)
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


# ---------------------------------------------------------------------------
# Comandos extras
# ---------------------------------------------------------------------------

def _normalizar_telefone(tel: str) -> str | None:
    """
    Converte qualquer formato de telefone brasileiro para JID do WhatsApp.
    Aceita: 44999604273, 5544999604273, +5544999604273, (44) 99960-4273, etc.
    Retorna: '5544999604273@s.whatsapp.net' ou None se inválido.
    """
    tel = tel.strip()
    # Remove tudo que não é dígito
    digits = re.sub(r"\D", "", tel)

    if not digits:
        return None

    # 10-11 dígitos → DDD + número sem código do país → adiciona 55
    if len(digits) in (10, 11):
        digits = "55" + digits

    # Deve ter 12 ou 13 dígitos (55 + DDD2 + número8ou9)
    if len(digits) not in (12, 13):
        return None

    return digits + "@s.whatsapp.net"


def _cmd_apelido(uid: int, lower: str) -> str:
    partes = lower.split(None, 1)
    if len(partes) < 2:
        return "❌ Use: *apelido SeuNome*"
    nome = partes[1].strip()
    set_nome_usuario(uid, nome)
    return f"✅ Nome atualizado para *{nome}*!"


def _cmd_vincular(uid: int, lower: str) -> str:
    """
    vincular 44999912629  →  normaliza, cria grupo (se não tiver) e adiciona o parceiro.
    Aceita qualquer formato: com ou sem +55, com ou sem DDD completo.
    """
    partes = lower.split(None, 1)
    if len(partes) < 2:
        return "❌ Use: *vincular 44999912629* (DDD + número)"

    jid = _normalizar_telefone(partes[1])
    if not jid:
        return (
            "❌ Número inválido.\n"
            "Use: *vincular 44999912629* (DDD + número)\n"
            "Ou: *vincular +5544999912629* (com código do país)"
        )

    usuario = get_usuario(uid) or {}
    gid = usuario.get("grupo_id")

    # Se ainda não está em grupo, cria um automaticamente
    if not gid:
        criar_grupo(uid, "Casal")
        usuario = get_usuario(uid) or {}
        gid = usuario.get("grupo_id")

    membro, ja_em_grupo = adicionar_membro_grupo(gid, jid)
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


def _cmd_excluir(uid: int, lower: str) -> str:
    partes = lower.split()
    if len(partes) < 2 or partes[1] != "ultimo":
        return "❌ Use: *excluir ultimo*"
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
            return "❌ Use: *grupo add 44999912629*"
        jid = _normalizar_telefone(partes[2])
        if not jid:
            return "❌ Número inválido. Use: *grupo add 44999912629* (DDD + número)"

        membro, ja_em_grupo = adicionar_membro_grupo(gid, jid)
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
    membro_linha = f"\n👥 *{membro_tel}* foi adicionado ao grupo!" if membro_tel else ""
    return (
        f"✅ *Grupo {nome_grupo} criado com saldo zerado!*{membro_linha}\n\n"
        "─────────────────────────\n"
        "⚙️ *Passo 1 — Configure as formas de pagamento:*\n"
        "• *forma add Nubank 2000* — adiciona com limite\n"
        "• *forma add Pix* — sem limite\n"
        "• *forma remover Cartão* — remove\n"
        "• *limite cartão 3000* — atualiza limite\n\n"
        "─────────────────────────\n"
        "💸 *Passo 2 — Registre gastos de 3 formas:*\n\n"
        "💬 *Mensagem de texto:*\n"
        "_50 mercado cartão_\n"
        "_gastei 120,90 no restaurante no pix_\n\n"
        "🎤 *Áudio:*\n"
        "Fale o gasto normalmente. Ex: _\"cinquenta reais no mercado no cartão\"_\n\n"
        "📸 *Foto de comprovante:*\n"
        "Envie a foto — a IA lê o valor e registra automaticamente.\n\n"
        "─────────────────────────\n"
        "📊 *Consultas úteis:*\n"
        "• *saldo* — saldo de cada forma\n"
        "• *gastos* — últimos 5 gastos\n"
        "• *resumo* — resumo mensal por categoria\n"
        "• *excluir ultimo* — remove o último gasto\n\n"
        "ℹ️ *ajuda* — todos os comandos"
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
