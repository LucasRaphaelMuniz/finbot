"""
handler.py — lógica principal de processamento de mensagens do Finbot.

Fluxo:
  1. Cadastra usuário novo se necessário.
  2. Executa comandos (saldo / resumo / limite / ajuda).
  3. Se há sessão ativa → fluxo guiado (Cenário 2).
  4. Se há sessão expirada → notifica e encerra.
  5. Tenta parsear input livre (Cenário 1).
"""

from difflib import SequenceMatcher

from db import (
    get_or_create_usuario,
    get_usuario,
    get_categorias,
    get_formas_pagamento,
    registrar_gasto,
    get_saldo_forma,
    get_parceiro_telefone,
    set_parceiro_telefone,
)
from notificar import enviar_notificacao
from sessao import (
    get_sessao_ativa,
    criar_sessao,
    atualizar_sessao,
    deletar_sessao,
    verificar_sessao_expirada,
)
from parser import extrair_valor, extrair_categoria, extrair_forma_pagamento
from comandos import cmd_saldo, cmd_resumo, cmd_limite, cmd_ajuda


# ---------------------------------------------------------------------------
# Helper BRL (espelhado de comandos para evitar import circular)
# ---------------------------------------------------------------------------

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

        uid = usuario["id"]
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
        if lower.startswith("vincular "):
            return _cmd_vincular(uid, lower)

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
            "Ou use: *saldo*, *resumo*, *limite*, *ajuda*."
        )

    if categoria and forma:
        # Tudo encontrado — registra direto
        return _registrar_e_confirmar(uid, forma, categoria, valor, mensagem)

    # Cria sessão com o que já temos
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

        # Recupera sessão atualizada para pegar categoria_temp
        sessao_atual = get_sessao_ativa(uid)
        deletar_sessao(uid)

        categorias = get_categorias()
        cat_id = sessao_atual["categoria_temp"] if sessao_atual else sessao["categoria_temp"]
        cat = next((c for c in categorias if c["id"] == cat_id), None)
        valor = float(sessao_atual["valor_temp"] if sessao_atual else sessao["valor_temp"])

        return _registrar_e_confirmar(uid, forma, cat, valor, "")

    return "❓ Sessão inválida. Envie um novo valor para começar."


# ---------------------------------------------------------------------------
# Registro e confirmação
# ---------------------------------------------------------------------------

def _registrar_e_confirmar(uid: int, forma: dict, categoria: dict,
                            valor: float, descricao: str) -> str:
    usuario = get_usuario(uid) or {}

    registrar_gasto(uid, forma["id"], categoria["id"], valor, descricao)
    saldo = get_saldo_forma(uid, forma["id"])

    gasto_mes  = float(saldo["gasto_mes"])
    limite     = float(saldo["limite_mensal"]) if saldo["limite_mensal"] else None
    forma_nome = saldo["nome"]
    cat_nome   = categoria["nome"] if categoria else "Outros"

    linhas = [
        "✅ *Registrado!*",
        f"💰 {_brl(valor)} — {cat_nome} — {forma_nome}",
    ]

    if limite:
        sobra = limite - gasto_mes
        pct   = (gasto_mes / limite) * 100
        linhas.append(
            f"💳 {forma_nome}: {_brl(gasto_mes)} gastos de {_brl(limite)} "
            f"— sobram {_brl(sobra)}"
        )
        if gasto_mes > limite:
            linhas.append(f"🚨 Limite do {forma_nome} ultrapassado!")
        elif pct >= 80:
            linhas.append(f"⚠️ Você já usou {pct:.0f}% do limite do {forma_nome}!")
    else:
        linhas.append(f"💳 {forma_nome}: {_brl(gasto_mes)} gastos este mês")

    # Notifica parceiro se configurado
    parceiro = usuario.get("parceiro_telefone")
    if parceiro:
        nome_quem = usuario.get("nome") or usuario.get("telefone", "Sua parceira")
        msg_notif = [f"🔔 *{nome_quem} registrou um gasto:*"]
        msg_notif.append(f"💰 {_brl(valor)} — {cat_nome} — {forma_nome}")
        if limite:
            sobra = limite - gasto_mes
            msg_notif.append(f"💳 {forma_nome}: {_brl(gasto_mes)} de {_brl(limite)} — sobram {_brl(sobra)}")
        else:
            msg_notif.append(f"💳 {forma_nome}: {_brl(gasto_mes)} gastos este mês")
        enviar_notificacao(parceiro, "\n".join(msg_notif))

    return "\n".join(linhas)


def _cmd_vincular(uid: int, lower: str) -> str:
    partes = lower.split(None, 1)
    if len(partes) < 2:
        return "❌ Use: *vincular +5511999999999*"

    telefone = partes[1].strip().replace(" ", "")
    if not telefone.startswith("+"):
        return "❌ Informe o número com código do país. Ex: *vincular +5511999999999*"

    set_parceiro_telefone(uid, telefone)
    return f"✅ Parceiro vinculado! Você será notificado quando {telefone} registrar gastos — e vice-versa se ele também vincular você."


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
    """Tenta match por número, nome exato ou fuzzy."""
    txt = mensagem.strip()

    # Por número
    if txt.isdigit():
        idx = int(txt) - 1
        if 0 <= idx < len(items):
            return items[idx]

    txt_lower = txt.lower()
    # Substring
    for item in items:
        if txt_lower in item["nome"].lower() or item["nome"].lower() in txt_lower:
            return item

    # Fuzzy
    melhor, melhor_score = None, 0.60
    for item in items:
        score = SequenceMatcher(None, txt_lower, item["nome"].lower()).ratio()
        if score > melhor_score:
            melhor_score = score
            melhor = item

    return melhor
