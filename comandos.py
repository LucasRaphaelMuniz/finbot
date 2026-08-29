import calendar
import re
from datetime import date as _date, datetime
from db import (get_saldo_todas_formas, get_resumo_mes, atualizar_limite,
                 get_ultimos_gastos, get_formas_pagamento, get_conn, _get_dia_corte)
from services.competencia import calcular_competencia, dia_corte_como_fechamento
from services.contas_mes import listar_contas_mes
from services.entradas import get_total_entradas_mes
from services.faturas import status_cartao


_MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março",    4: "Abril",
    5: "Maio",    6: "Junho",     7: "Julho",     8: "Agosto",
    9: "Setembro",10: "Outubro",  11: "Novembro", 12: "Dezembro",
}

def _mes_ano(usuario_id: int) -> str:
    """
    Label do cabeçalho ("Saldo — Setembro/2026") — corrigido em 25/08/2026:
    antes usava datetime.now() puro (mês calendário), então no próprio dia
    do corte o cabeçalho ainda dizia o mês velho mesmo com os dados de baixo
    (get_saldo_todas_formas/get_resumo_mes, já corte-aware desde a migração
    028) mostrando o ciclo novo — o "meu mês virou" que o Lucas reportou.
    Usa o mesmo dia_corte do usuário, convertido pra dia_corte_como_fechamento
    (dia_regra sem cartão, já que o cabeçalho é 1 só pra formas mistas).
    """
    with get_conn() as conn:
        dia_corte = _get_dia_corte(conn, usuario_id)
    competencia = calcular_competencia(_date.today(), dia_corte_como_fechamento(dia_corte))
    return f"{_MESES_PT[competencia.month]}/{competencia.year}"

def _ciclo_corte(usuario_id: int, hoje: _date) -> tuple[int, int]:
    """
    (dias_no_ciclo, dia_no_ciclo) pro ritmo do Status em cmd_saldo — ciclo de
    CORTE, não calendário puro (29/08/2026, correção do Lucas: o Status
    comparava com "31 dias, dia 29" — agosto calendário — enquanto o
    cabeçalho da própria mensagem já mostra a competência de setembro,
    corte já aplicado; perto da virada do mês os dois divergem).

    O ciclo da competência atual vai do dia (dia_corte + 1) do mês anterior
    até o dia (dia_corte) do mês corrente — mesma fronteira de
    services/competencia.py::calcular_competencia, só que aqui preciso das
    DUAS pontas (não só do mês resultante) pra saber o tamanho do ciclo e em
    que ponto dele "hoje" está. Sem dia_corte configurado, cai no calendário
    puro — não há corte pra aplicar.
    """
    with get_conn() as conn:
        dia_corte = _get_dia_corte(conn, usuario_id)
    dc = dia_corte_como_fechamento(dia_corte)
    if not dc:
        return calendar.monthrange(hoje.year, hoje.month)[1], hoje.day

    if hoje.day > dc:
        ano_ini, mes_ini = hoje.year, hoje.month
    elif hoje.month == 1:
        ano_ini, mes_ini = hoje.year - 1, 12
    else:
        ano_ini, mes_ini = hoje.year, hoje.month - 1

    dias_mes_ini = calendar.monthrange(ano_ini, mes_ini)[1]
    cycle_start = _date(ano_ini, mes_ini, min(dc + 1, dias_mes_ini))

    ano_fim, mes_fim = (ano_ini + 1, 1) if mes_ini == 12 else (ano_ini, mes_ini + 1)
    dias_mes_fim = calendar.monthrange(ano_fim, mes_fim)[1]
    cycle_end = _date(ano_fim, mes_fim, min(dc, dias_mes_fim))

    dias_no_ciclo = (cycle_end - cycle_start).days + 1
    dia_no_ciclo  = (hoje - cycle_start).days + 1
    return dias_no_ciclo, dia_no_ciclo


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

    # Cartão (dia_fechamento configurado): gasto do mês = fatura atual —
    # mesmo número, nomes diferentes (modelo final de 18/07/2026, ver
    # services/faturas.py e o histórico das 2 tentativas descartadas lá).
    # A linha extra "fatura anterior" é o que vai sair do caixa agora.
    cartoes_ids = {
        f["id"] for f in get_formas_pagamento(usuario_id) if f.get("dia_fechamento")
    }

    linhas = [f"📊 *Saldo — {_mes_ano(usuario_id)}*"]
    for f in formas:
        emoji = _emoji_forma(f["nome"])

        if f["id"] in cartoes_ids:
            status = status_cartao(usuario_id, f["id"])
            if not status:
                linhas.append("")
                linhas.append(f"{emoji} *{f['nome']}*")
                linhas.append("⚠️ Não foi possível calcular a fatura.")
                continue
            gasto  = status["fatura_atual"]
            limite = status["limite_mensal"]
        else:
            status = None
            gasto  = float(f["gasto_mes"])
            limite = float(f["limite_mensal"]) if f["limite_mensal"] else None

        # Forma sem limite (ex.: Custos Fixos) não tem "saldo" de verdade
        # pra comparar — pedido do Lucas: nem a linha "Total: X gastos este
        # mês" (25/08/2026), nem o cabeçalho da forma inteira (29/08/2026,
        # ficava um "💰 CUSTOS FIXOS" solto sem nada embaixo). A composição
        # desse total aparece detalhada por categoria no /resumo, não
        # precisa duplicar aqui.
        linhas_forma = []

        if limite:
            sobra = limite - gasto
            pct   = (gasto / limite) * 100
            linhas_forma.append(f"*Saldo Disponível: {_brl(sobra)}*")
            linhas_forma.append(f"Total: {_brl(gasto)} / {_brl(limite)}")

            # Projeção Fatura (25/08/2026, pedido do Lucas): pra onde a
            # fatura atual deve fechar — real lançado (compras avulsas E
            # parcelas do mês, já reais desde o momento da compra) + as
            # despesas fixas/recorrentes DAQUELE cartão que ainda não foram
            # lançadas nessa competência. SEMPRE aparece pra cartão, mesmo
            # igual ao Total (sinaliza "nada pendente pra entrar ainda") —
            # 26/08/2026: antes só aparecia com pendência, o Lucas queria
            # a linha fixa logo depois do Total, antes dos alertas de
            # limite.
            if status:
                linhas_forma.append(
                    f"📈 Projeção Fatura: {_brl(status['fatura_atual_estimada'])}"
                )

            if gasto > limite:
                linhas_forma.append("🚨 Limite ultrapassado!")
            elif pct >= 80:
                linhas_forma.append(f"⚠️ {pct:.0f}% do limite usado")

        if status:
            # Fatura anterior: só mostra "a pagar" se ainda não foi marcada
            # como paga no board de /contas (faturas_pagamentos, migração
            # 027) — corrigido em 25/08/2026: o bot continuava cobrando uma
            # fatura que o Lucas já tinha pago.
            if status["fatura_anterior"] > 0 and not status["fatura_anterior_paga"]:
                mes_venc = status["vencimento_fatura_anterior"][:7]
                linhas_forma.append(
                    f"🧾 Fatura anterior a pagar em {mes_venc}: {_brl(status['fatura_anterior'])}"
                )

        if not linhas_forma:
            continue  # nada a mostrar pra essa forma — não abre cabeçalho à toa

        linhas.append("")
        linhas.append(f"{emoji} *{f['nome']}*")
        linhas.extend(linhas_forma)

    # Bloco final (pedido do Lucas, 29/08/2026). Só aparece sem filtro: com
    # "/saldo Nubank" a pessoa quer olhar aquele cartão, um total de TODAS
    # as formas ali embaixo confundiria mais do que ajudaria.
    #
    # Duas bases diferentes de propósito, cada uma seguindo a definição que
    # o Lucas deu: "Total Gasto" usa a Projeção Fatura (fatura_atual_estimada
    # — já inclui fixa que ainda não venceu), enquanto "Saldo Restante" soma
    # a mesma "Saldo Disponível" que já aparece linha a linha acima (baseada
    # no gasto REAL/fatura_atual, não na projeção). Ou seja: o "Total Gasto"
    # é otimista (conta o que ainda vai entrar), o "Saldo Restante" é
    # conservador (só desconta o que já é fatura fechada). É assim que os
    # dois nomes já eram usados nas linhas por forma; manter a mesma base
    # aqui evita um "Saldo Restante" que não bate com a soma das linhas de
    # cima se alguém for conferir na mão.
    #
    # As DUAS só somam formas COM limite (29/08/2026, correção do Lucas: o
    # Total Gasto bateu R$11.764,77 porque somava também o gasto_mes de
    # "Custos Fixos" — forma sem limite, que nem aparece na mensagem acima
    # pra conferir de onde veio aquele número). Mesmo critério que já valia
    # pra Saldo Restante desde o início: forma sem limite não entra na
    # conta, porque não tem "saldo" nenhum contra o qual comparar.
    if not filtro:
        total_gasto = 0.0
        saldo_restante = 0.0
        orcamento_mensal = 0.0
        for f in get_saldo_todas_formas(usuario_id):
            if f["id"] in cartoes_ids:
                status_f = status_cartao(usuario_id, f["id"])
                if not status_f:
                    continue
                gasto_estimado_f = status_f["fatura_atual_estimada"]
                gasto_real_f = status_f["fatura_atual"]
                limite_f = status_f["limite_mensal"]
            else:
                gasto_estimado_f = gasto_real_f = float(f["gasto_mes"])
                limite_f = float(f["limite_mensal"]) if f["limite_mensal"] else None

            if limite_f:
                total_gasto += gasto_estimado_f
                saldo_restante += (limite_f - gasto_real_f)
                orcamento_mensal += limite_f

        linhas.append("")
        linhas.append("━━━━━━━━━━━━━━")
        linhas.append(f"💸 Total Gasto: {_brl(total_gasto)}")
        linhas.append(f"💰 Saldo Restante: {_brl(saldo_restante)}")

        # "Orçamento mensal" = soma dos limites cadastrados (não existe um
        # campo de orçamento separado no modelo hoje). Sem nenhuma forma com
        # limite não dá pra calcular ritmo esperado, então a linha some em
        # vez de mostrar um "Status" sem sentido.
        if orcamento_mensal > 0:
            dias_no_ciclo, dia_no_ciclo = _ciclo_corte(usuario_id, _date.today())
            gasto_esperado_ate_hoje = (orcamento_mensal / dias_no_ciclo) * dia_no_ciclo

            # Só 2 estados (29/08/2026, pedido do Lucas — tirou o "na
            # média" do meio). Sem 3ª faixa não tem mais "quase empatado"
            # pra proteger com folga: acima do esperado é acima, ponto.
            if total_gasto > gasto_esperado_ate_hoje:
                status_txt = "🔴 Gasto acima do previsto"
            else:
                status_txt = "🟢 Gasto dentro do orçamento"
            linhas.append(f"📅 Status: {status_txt}")

    return "\n".join(linhas)


def cmd_contas(usuario_id: int) -> str:
    """
    "Contas do mês" no bot (29/08/2026, pedido do Lucas: "preciso de uma
    inteligencia para entender comandos pelo whats... quais sao as contas do
    mes?"). Reusa services/contas_mes.py::listar_contas_mes — a mesma função
    que monta a tela do site — de propósito: bot e site nunca podem mostrar
    números diferentes pra a mesma pergunta.
    """
    board = listar_contas_mes(usuario_id)
    ano, mes_num = (int(p) for p in board["mes"].split("-"))
    mes_label = f"{_MESES_PT[mes_num]}/{ano}"

    linhas = [f"🧾 *Contas do mês — {mes_label}*"]

    linhas.append("")
    linhas.append(f"🔴 *Não pagas ({_brl(board['totais']['a_pagar'])}):*")
    if board["a_pagar"]:
        for c in board["a_pagar"]:
            linhas.append(f"• {c['descricao']} — {_brl(c['valor'])}")
    else:
        linhas.append("_nenhuma 🎉_")

    linhas.append("")
    linhas.append(f"🟢 *Pagas ({_brl(board['totais']['pago'])}):*")
    if board["pagas"]:
        for c in board["pagas"]:
            # Fatura paga com valor diferente do que fechou: mostra o que
            # SAIU do caixa (valor_pago), não o valor bruto da fatura — mesmo
            # critério de totais["pago"] em listar_contas_mes.
            valor = c["valor_pago"] if c["valor_pago"] is not None else c["valor"]
            linhas.append(f"• {c['descricao']} — {_brl(valor)}")
    else:
        linhas.append("_nenhuma ainda_")

    linhas.append("")
    linhas.append(f"💰 Sobra do mês: {_brl(board['totais']['sobra'])}")
    return "\n".join(linhas)


def cmd_resumo(usuario_id: int) -> str:
    gastos          = get_resumo_mes(usuario_id)
    total_entradas  = get_total_entradas_mes(usuario_id)

    if not gastos and not total_entradas:
        return "📋 Nenhum gasto ou entrada registrado este mês."

    total_gastos = sum(float(g["total"]) for g in gastos) if gastos else 0.0
    linhas = [f"📋 *Resumo — {_mes_ano(usuario_id)}*\n"]

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

    # Caixa (modelo "fatura como conta a pagar", 17-18/07/2026): o bloco
    # acima é CONTROLE (o que foi comprado no mês, cartão incluído). Este é
    # o que sai do bolso no mês — a fatura que vence agora é a do mês
    # passado. Import local pra evitar ciclo (resumo importa faturas, que
    # não importa comandos — mas manter o topo do módulo leve).
    from services.resumo import resumo_mensal
    caixa = resumo_mensal(usuario_id)["caixa"]
    if caixa["fatura_a_pagar"] > 0:
        linhas.append("")
        linhas.append(f"🧾 Fatura(s) vencendo este mês: {_brl(caixa['fatura_a_pagar'])}")
        linhas.append(f"🏦 *Saída de caixa do mês: {_brl(caixa['saida_total'])}*")

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
        "💬 *Não precisa decorar nada disso:* fale normal que eu entendo.\n"
        "_\"adiciona a Ana no grupo, número 44912345678\"_\n"
        "_\"como eu cadastro uma despesa fixa?\"_\n"
        "Se eu entender uma ação, confirmo com você antes de fazer.\n\n"
        "─────────────────────────\n"
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
        "• *limite cartão 3000* — atualiza limite mensal\n\n"
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
        "🧾 *Contas do mês (fale normal):*\n"
        "_\"quais são as contas do mês?\"_ — lista o que falta pagar e o que "
        "já foi pago\n"
        "_\"paguei a fatura do cartão\"_ — marca como paga (eu confirmo antes)\n"
        "_\"todas as contas já foram pagas\"_ — marca todas de uma vez (eu "
        "mostro a lista e confirmo antes)\n\n"
        "👤 *Perfil:*\n"
        "• *apelido SeuNome* — define seu nome no bot\n\n"
        "ℹ️ *ajuda* — este menu\n\n"
        "⏱ Registros incompletos expiram em 5 minutos."
    )
