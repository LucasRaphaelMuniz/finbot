import re
from datetime import datetime
from db import get_saldo_todas_formas, get_resumo_mes, atualizar_limite, get_ultimos_gastos, get_formas_pagamento
from services.entradas import get_total_entradas_mes
from services.faturas import status_cartao, marcar_fatura_paga


_MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março",    4: "Abril",
    5: "Maio",    6: "Junho",     7: "Julho",     8: "Agosto",
    9: "Setembro",10: "Outubro",  11: "Novembro", 12: "Dezembro",
}

def _mes_ano() -> str:
    now = datetime.now()
    return f"{_MESES_PT[now.month]}/{now.year}"

def _brl(valor: float) -> str:
    s = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"

def _emoji_forma(nome: str) -> str:
    n = nome.lower()
    if "cart" in n:
        return "💳"
    if "pix" in n or "dinheiro" in n:
        return "💵"
    if "ticket" in n or "vale" in n:
        return "🎫"
    return "💰"


def cmd_saldo(usuario_id: int, mensagem: str) -> str:
    formas = get_saldo_todas_formas(usuario_id)
    if not formas:
        return "📊 Nenhuma forma de pagamento cadastrada."

    partes = mensagem.strip().split(maxsplit=1)
    filtro = partes[1].strip() if len(partes) > 1 else None
    if filtro:
        formas = [f for f in formas if filtro.lower() in f["nome"].lower()]
        if not formas:
            return f"❌ Forma de pagamento '{filtro}' não encontrada."

    # Formas tipo cartão (dia_fechamento configurado) mostram limite
    # rotativo real (services/faturas.py, migração 021) em vez do simples
    # "gasto do mês" — desde 019/020 a competência do cartão já é o mês do
    # VENCIMENTO, então "gasto do mês corrente" não é mais "quanto usei do
    # limite" (ignora fatura fechada a pagar e parcelas futuras).
    cartoes_ids = {
        f["id"] for f in get_formas_pagamento(usuario_id) if f.get("dia_fechamento")
    }

    linhas = [f"📊 *Saldo — {_mes_ano()}*"]
    for f in formas:
        emoji = _emoji_forma(f["nome"])
        linhas.append("")
        linhas.append(f"{emoji} *{f['nome']}*")

        if f["id"] in cartoes_ids:
            status = status_cartao(usuario_id, f["id"])
            if not status:
                linhas.append("⚠️ Não foi possível calcular o limite rotativo.")
                continue
            limite = status["limite_mensal"]
            usado  = status["limite_usado"]
            linhas.append(f"Fatura fechada a pagar: {_brl(status['fatura_fechada_a_pagar'])}")
            linhas.append(f"Fatura aberta (em formação): {_brl(status['fatura_aberta'])}")
            if limite:
                sobra = status["limite_disponivel"]
                pct   = (usado / limite) * 100
                linhas.append(f"*Limite disponível: {_brl(sobra)}*")
                linhas.append(f"Limite usado (rotativo): {_brl(usado)} / {_brl(limite)}")
                if usado > limite:
                    linhas.append("🚨 Limite ultrapassado!")
                elif pct >= 80:
                    linhas.append(f"⚠️ {pct:.0f}% do limite usado")
            else:
                linhas.append(f"Limite usado (rotativo): {_brl(usado)}")
            linhas.append("_Marque como pago com: *paguei a fatura " + f["nome"].lower() + "*_")
            continue

        gasto  = float(f["gasto_mes"])
        limite = float(f["limite_mensal"]) if f["limite_mensal"] else None
        if limite:
            sobra = limite - gasto
            pct   = (gasto / limite) * 100
            linhas.append(f"*Saldo Disponível: {_brl(sobra)}*")
            linhas.append(f"Total: {_brl(gasto)} / {_brl(limite)}")
            if gasto > limite:
                linhas.append("🚨 Limite ultrapassado!")
            elif pct >= 80:
                linhas.append(f"⚠️ {pct:.0f}% do limite usado")
        else:
            linhas.append(f"Total: {_brl(gasto)} gastos este mês")

    return "\n".join(linhas)


def cmd_paguei_fatura(usuario_id: int, mensagem: str) -> str:
    """'paguei a fatura <forma>' / 'paguei fatura <forma>' — marca a fatura
    do mês corrente como paga (services/faturas.py). Idempotente: rodar de
    novo não duplica nem quebra."""
    m = re.match(r"paguei\s+(?:a\s+)?fatura\s+(.+)$", mensagem.strip(), re.IGNORECASE)
    if not m:
        return "❌ Formato correto: *paguei a fatura nubank*"

    forma_nome = m.group(1).strip()
    formas = [f for f in get_formas_pagamento(usuario_id) if f.get("dia_fechamento")]
    forma = next((f for f in formas if forma_nome.lower() in f["nome"].lower()), None)
    if not forma:
        return f"❌ Forma de pagamento (cartão) '{forma_nome}' não encontrada."

    resultado = marcar_fatura_paga(usuario_id, forma["id"])
    if not resultado:
        return f"❌ Não foi possível marcar a fatura de '{forma['nome']}' como paga."

    status = status_cartao(usuario_id, forma["id"])
    disponivel = _brl(status["limite_disponivel"]) if status and status["limite_disponivel"] is not None else "—"
    return (
        f"✅ Fatura de *{forma['nome']}* ({_mes_ano()}) marcada como paga!\n"
        f"💳 Limite disponível agora: {disponivel}"
    )


def cmd_resumo(usuario_id: int) -> str:
    gastos          = get_resumo_mes(usuario_id)
    total_entradas  = get_total_entradas_mes(usuario_id)

    if not gastos and not total_entradas:
        return "📋 Nenhum gasto ou entrada registrado este mês."

    total_gastos = sum(float(g["total"]) for g in gastos) if gastos else 0.0
    linhas = [f"📋 *Resumo — {_mes_ano()}*\n"]

    if gastos:
        for g in gastos:
            val = float(g["total"])
            pct = (val / total_gastos * 100) if total_gastos > 0 else 0
            linhas.append(f"• {g['categoria']} ({g['forma']}): {_brl(val)} ({pct:.0f}%)")
        linhas.append(f"\n💸 *Gastos: {_brl(total_gastos)}*")
    else:
        linhas.append("💸 Nenhum gasto este mês.")

    # Entradas do mês (Fase 3.5, G1) — não afetam saldo por forma, só o
    # saldo geral do mês (entradas − gastos).
    linhas.append(f"📈 *Entradas: {_brl(total_entradas)}*")
    saldo = total_entradas - total_gastos
    linhas.append(f"💰 *Saldo do mês: {_brl(saldo)}*")

    return "\n".join(linhas)


def cmd_limite(usuario_id: int, mensagem: str) -> str:
    m = re.match(
        r"limite\s+(.+?)\s+(\d{1,6}(?:[.,]\d{1,2})?)$",
        mensagem.strip(),
        re.IGNORECASE,
    )
    if not m:
        return "❌ Formato correto: *limite cartão 3000*"

    forma_nome  = m.group(1).strip()
    novo_limite = float(m.group(2).replace(",", "."))

    if atualizar_limite(usuario_id, forma_nome, novo_limite):
        return f"✅ Limite de *{forma_nome.capitalize()}* atualizado para {_brl(novo_limite)}"
    return f"❌ Forma de pagamento '{forma_nome}' não encontrada."


def cmd_gastos(usuario_id: int) -> str:
    gastos = get_ultimos_gastos(usuario_id, limit=5)
    if not gastos:
        return "📋 Nenhum gasto registrado."

    linhas = ["📋 *Últimos gastos:*"]
    for i, g in enumerate(gastos, 1):
        val   = _brl(float(g["valor"]))
        cat   = g.get("categoria_nome") or "?"
        forma = g.get("forma_nome") or "?"
        data  = str(g["data"])[:10] if g.get("data") else "?"
        linhas.append(f"{i}. {val} — {cat} — {forma} ({data})")

    linhas.append("\n• *excluir ultimo* — remove o mais recente")
    linhas.append("• *editar ultimo 45,90* — corrige o valor do mais recente")
    return "\n".join(linhas)


def cmd_ajuda() -> str:
    return (
        "🤖 *Finbot — Comandos disponíveis*\n\n"
        "📝 *Registrar gasto (input livre):*\n"
        "_Ex: 50 mercado cartão_\n"
        "_Ex: gastei 120,90 no restaurante no pix_\n"
        "_Ex: notebook 1103,04 em 12x no cartão_ — compra parcelada\n\n"
        "📈 *Registrar entrada/receita:*\n"
        "_Ex: recebi 2000 de salário_\n"
        "_Ex: entrada 2000 salário_ — comando explícito\n\n"
        "📊 *Consultas:*\n"
        "• *saldo* — saldo de todas as formas\n"
        "• *saldo cartão* — saldo de uma forma específica\n"
        "• *resumo* — gastos do mês por categoria\n"
        "• *gastos* — últimos 5 gastos\n\n"
        "🗑 *Gerenciar gastos:*\n"
        "• *excluir ultimo* — remove o último gasto (se for parcela, pergunta "
        "se é só ela ou a compra inteira)\n"
        "• *editar ultimo 45,90* — corrige o valor do último\n\n"
        "💳 *Gerenciar formas de pagamento:*\n"
        "• *forma add Nubank 2000* — adiciona forma com limite\n"
        "• *forma remover Nubank* — remove forma\n"
        "• *limite cartão 3000* — atualiza limite mensal\n"
        "• *paguei a fatura nubank* — marca a fatura do mês como paga "
        "(libera limite rotativo)\n\n"
        "📂 *Gerenciar categorias (por grupo):*\n"
        "• *categoria add Assinaturas* — cria categoria personalizada\n"
        "• *categoria remover Assinaturas* — remove (só personalizadas)\n"
        "• *categoria listar* — mostra todas as disponíveis\n\n"
        "📅 *Despesas fixas (lançam sozinhas todo mês):*\n"
        "• *fixa add Aluguel 1200 dia 5* — cadastra\n"
        "• *fixa remover Aluguel* — para de lançar\n"
        "• *fixa listar* — mostra todas as ativas\n\n"
        "👨‍👩‍👧 *Grupo (contas compartilhadas):*\n"
        "• *vincular 44912345678* — vincula parceiro (cria grupo automaticamente)\n"
        "• *grupo criar Família* — cria grupo com nome personalizado\n"
        "• *grupo add 44912345678* — adiciona membro ao grupo\n"
        "• *grupo* — mostra o grupo e os membros\n"
        "• *grupo sair* — sai do grupo\n\n"
        "👤 *Perfil:*\n"
        "• *apelido SeuNome* — define seu nome no bot\n\n"
        "ℹ️ *ajuda* — este menu\n\n"
        "⏱ Registros incompletos expiram em 5 minutos."
    )
