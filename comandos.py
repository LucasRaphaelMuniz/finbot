import re
from datetime import datetime
from db import get_saldo_todas_formas, get_resumo_mes, atualizar_limite


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março",    4: "Abril",
    5: "Maio",    6: "Junho",     7: "Julho",     8: "Agosto",
    9: "Setembro",10: "Outubro",  11: "Novembro", 12: "Dezembro",
}

def _mes_ano() -> str:
    now = datetime.now()
    return f"{_MESES_PT[now.month]}/{now.year}"

def _brl(valor: float) -> str:
    """Formata valor em reais: R$ 1.234,56"""
    s = f"{valor:,.2f}"                       # 1,234.56 (americano)
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")  # 1.234,56
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


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------

def cmd_saldo(usuario_id: int, mensagem: str) -> str:
    formas = get_saldo_todas_formas(usuario_id)
    if not formas:
        return "📊 Nenhuma forma de pagamento cadastrada."

    # Filtro opcional: "saldo cartão"
    partes = mensagem.strip().split(maxsplit=1)
    filtro = partes[1].strip() if len(partes) > 1 else None
    if filtro:
        formas = [f for f in formas if filtro.lower() in f["nome"].lower()]
        if not formas:
            return f"❌ Forma de pagamento '{filtro}' não encontrada."

    linhas = [f"📊 *Saldo — {_mes_ano()}*"]
    for f in formas:
        gasto  = float(f["gasto_mes"])
        limite = float(f["limite_mensal"]) if f["limite_mensal"] else None
        emoji  = _emoji_forma(f["nome"])

        if limite:
            sobra = limite - gasto
            linhas.append(
                f"{emoji} {f['nome']}: {_brl(gasto)} / {_brl(limite)} "
                f"— sobram {_brl(sobra)}"
            )
        else:
            linhas.append(f"{emoji} {f['nome']}: {_brl(gasto)} gastos este mês")

    return "\n".join(linhas)


def cmd_resumo(usuario_id: int) -> str:
    gastos = get_resumo_mes(usuario_id)
    if not gastos:
        return "📋 Nenhum gasto registrado este mês."

    total = sum(float(g["total"]) for g in gastos)
    linhas = [f"📋 *Resumo — {_mes_ano()}*\n"]

    for g in gastos:
        val = float(g["total"])
        pct = (val / total * 100) if total > 0 else 0
        linhas.append(
            f"• {g['categoria']} ({g['forma']}): {_brl(val)} ({pct:.0f}%)"
        )

    linhas.append(f"\n💰 *Total: {_brl(total)}*")
    return "\n".join(linhas)


def cmd_limite(usuario_id: int, mensagem: str) -> str:
    # Formato esperado: "limite <forma> <valor>"
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


def cmd_ajuda() -> str:
    return (
        "🤖 *Finbot — Comandos disponíveis*\n\n"
        "📝 *Registrar gasto (input livre):*\n"
        "Envie valor + categoria + pagamento em qualquer ordem:\n"
        "_Ex: 50 mercado cartão_\n"
        "_Ex: gastei 120,90 no restaurante no pix_\n\n"
        "📊 *Consultas:*\n"
        "• *saldo* — saldo de todas as formas\n"
        "• *saldo cartão* — saldo de uma forma específica\n"
        "• *resumo* — gastos do mês por categoria\n\n"
        "⚙️ *Configuração:*\n"
        "• *limite cartão 3000* — atualizar limite mensal\n\n"
        "ℹ️ *ajuda* — este menu\n\n"
        "⏱ Registros incompletos expiram em 5 minutos."
    )
