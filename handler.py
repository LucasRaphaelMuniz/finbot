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
    set_parceiro_telefone,
    adicionar_forma_pagamento,
    remover_forma_pagamento,
    excluir_ultimo_gasto,
    editar_ultimo_gasto_valor,
    get_grupo,
    get_membros_grupo,
    criar_grupo,
    adicionar_membro_grupo,
    sair_grupo,
)
from sessao import (
    get_sessao_ativa,
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
        if novo:
            return (
                "👋 *Olá! Você foi cadastrado no Finbot.*\n"
                "Digite um valor para registrar seu primeiro gasto "
                "ou *ajuda* para ver os comandos."
            )

        uid   = usuario["id"]
        lower = mensagem.lower().strip()

        # ── Comandos ────────────────────────────────────────────────────────
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

        # ── Sessão ativa ────────────────────────────────────────────────────
        sessao = get_sessao_ativa(uid)
        if sessao:
            return _processar_sessao(uid, sessao, mensagem)

        # ── Sessão expirada ─────────────────────────────────────────────────
        if verificar_sessao_expirada(uid):
            return (
                "⏱ _Registro cancelado por inatividade._\n"
                "Sua próxima mensagem será tratada como novo gasto."
            )

        # ── Input livre ─────────────────────────────────────────────────────
        return _processar_input_livre(uid, mensagem)

    except Exception as exc:
        print(f"[Finbot ERROR] {exc}")
        return "😕 Ocorreu um erro interno. Tente novamente em instantes."


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

def _cmd_apelido(uid: int, lower: str) -> str:
    partes = lower.split(None, 1)
    if len(partes) < 2:
        return "❌ Use: *apelido SeuNome*"
    nome = partes[1].strip()
    set_nome_usuario(uid, nome)
    return f"✅ Nome atualizado para *{nome}*!"


def _cmd_vincular(uid: int, lower: str) -> str:
    partes = lower.split(None, 1)
    if len(partes) < 2:
        return "❌ Use: *vincular +5511999999999*"
    tel = partes[1].strip().replace(" ", "")
    if not tel.startswith("+"):
        return "❌ Informe o número com código do país. Ex: *vincular +5511999999999*"
    jid = tel.lstrip("+") + "@s.whatsapp.net"
    set_parceiro_telefone(uid, jid)
    return f"✅ Parceiro *{tel}* vinculado!"


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
            linhas.append(f"• {m.get('nome') or m['telefone']}")
        linhas.append("\n• *grupo add +55...* — adicionar membro")
        linhas.append("• *grupo sair* — sair do grupo")
        return "\n".join(linhas)

    acao = partes[1].lower()

    if acao == "criar":
        if gid:
            return "❌ Você já está em um grupo. Use *grupo sair* antes de criar outro."
        nome_grupo = partes[2].strip() if len(partes) > 2 else "Família"
        criar_grupo(uid, nome_grupo)
        return (
            f"✅ Grupo *{nome_grupo}* criado!\n"
            "Suas formas de pagamento e gastos agora são compartilhados com o grupo.\n"
            "Adicione membros com: *grupo add +5511999999999*"
        )

    if acao in ("add", "adicionar", "convidar"):
        if not gid:
            return "❌ Crie um grupo primeiro: *grupo criar Família*"
        if len(partes) < 3:
            return "❌ Use: *grupo add +5511999999999*"
        tel = partes[2].strip().replace(" ", "")
        if not tel.startswith("+"):
            return "❌ Informe o número com código do país. Ex: *grupo add +5511999999999*"
        jid = tel.lstrip("+") + "@s.whatsapp.net"

        membro, ja_em_grupo = adicionar_membro_grupo(gid, jid)
        if ja_em_grupo:
            if membro.get("grupo_id") == gid:
                return "ℹ️ Essa pessoa já está no seu grupo."
            return "❌ Essa pessoa já pertence a outro grupo."
        return f"✅ *{tel}* adicionado ao grupo!"

    if acao == "sair":
        if not gid:
            return "❌ Você não está em nenhum grupo."
        sair_grupo(uid)
        return "✅ Você saiu do grupo. Suas formas de pagamento padrão foram restauradas."

    return "❌ Use: *grupo*, *grupo criar Nome*, *grupo add +55...* ou *grupo sair*"


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
