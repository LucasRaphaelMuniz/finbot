"""
services/contas_mes.py — "contas do mês" (pedido do Lucas, 24/07/2026).

O QUE ISTO É, E POR QUE NÃO É MAIS UMA TELA DE GASTOS
-----------------------------------------------------
O resto do finbot raciocina em COMPETÊNCIA ("quanto gastei este mês").
Este módulo raciocina em CAIXA ("o que preciso pagar este mês, e o que já
paguei") — a pergunta que o Lucas respondia numa planilha à mão. São visões
diferentes do mesmo dado e divergem exatamente no cartão: compra de 05/07
num cartão que fecha 28/07 é gasto de JULHO lá, e conta de AGOSTO aqui.

A regra de "qual fatura pesa em qual mês" NÃO é reimplementada aqui: sai de
services/competencia.py::mes_vencimento, a mesma função que services/resumo.py
já usa no bloco `caixa`. Este módulo é a ITEMIZAÇÃO linha a linha de um
número que já existia somado no dashboard.

O QUE ENTRA NO BOARD (decisão do Lucas, 24/07/2026)
---------------------------------------------------
Entra:
  - gasto não-cartão vindo de despesa fixa (Sanepar, Copel, internet);
  - gasto não-cartão vindo de compra parcelada (consórcio, "Mauro/Tania 2/7");
  - a FATURA de cada cartão que vence no mês, como UMA linha só.

NÃO entra: gasto avulso no pix/débito. Ele já saiu do bolso no ato — nunca
é "a pagar". Se entrasse, nasceria na coluna errada e o Lucas teria que
arrastar todo mês item que na vida real já estava pago (foi justamente esse
tipo de ritual sem retorno que matou a `faturas_pagas` da migração 021 e o
botão "Confirmar" das fixas, ambos em 18/07/2026).

Consequência assumida: `total_a_pagar` daqui é MENOR que `caixa.saida_total`
do /api/resumo, que inclui os avulsos à vista. São perguntas diferentes; por
isso o bloco `caixa` do resumo não foi alterado, só ganhou um vizinho.

TRÊS IDENTIDADES DE LINHA
-------------------------
"Internet 99,90"   = 1 linha = 1 registro em `gastos`   -> chave "gasto:{id}"
"Cartão BTG 6.000" = 1 linha = N registros em `gastos`  -> chave
                     "fatura:{forma_id}:{competencia}"
"Salário Lucas"    = 1 linha = 1 registro em `entradas` -> chave "entrada:{id}"

Por isso o estado de "pago" mora em dois lugares (migração 027): a coluna
`gastos.pago` e a tabela `faturas_pagamentos`. A chave string existe pra que
o front trate as três como a mesma coisa — ele arrasta/edita um card e manda
a chave de volta, sem saber a diferença. Entrada é a mais simples das três:
não tem status de pago (dinheiro que entra não fica "a pagar"), só valor
editável — por isso `marcar_conta` a rejeita explicitamente (400) e só
`editar_valor_conta` a aceita.
"""

import calendar
from datetime import date

from db import get_conn, _get_grupo_id, get_formas_pagamento
from services.competencia import mes_vencimento, somar_meses
from services.faturas import _get_ajuste
from services.gastos import projetar_despesas_fixas
from utils.app_error import AppError


# ---------------------------------------------------------------------------
# Parte pura (sem banco) — testável isoladamente, mesma filosofia de
# services/competencia.py e do montar_comparativo em services/resumo.py.
# ---------------------------------------------------------------------------

def competencias_que_vencem_em(mes_alvo: date, dia_fechamento: int | None,
                                dia_vencimento: int | None) -> list[date]:
    """
    Inverso de `mes_vencimento`: dado o mês do board, quais competências de
    fatura caem nele.

    Resolvido por tentativa sobre 2 candidatos (o próprio mês e o anterior)
    em vez de uma fórmula fechada — de propósito. A regra de vencimento é a
    função pura `mes_vencimento`; testar candidatos contra ela garante que
    board e resumo nunca divirjam, mesmo que a regra mude depois. Uma
    fórmula inversa própria seria uma segunda cópia da regra, livre pra
    divergir em silêncio.

    Só faz sentido pra cartão: sem dia_fechamento não existe fatura, e o
    gasto sai do caixa no próprio mês (retorna lista vazia — quem chama
    trata gasto não-cartão pela outra via, linha a linha).
    """
    if not dia_fechamento:
        return []
    candidatas = [mes_alvo, somar_meses(mes_alvo, -1)]
    return [c for c in candidatas
            if mes_vencimento(c, dia_fechamento, dia_vencimento) == mes_alvo]


def chave_gasto(gasto_id: int) -> str:
    return f"gasto:{gasto_id}"


def chave_fatura(forma_pagamento_id: int, competencia: date) -> str:
    return f"fatura:{forma_pagamento_id}:{competencia.isoformat()}"


def chave_entrada(entrada_id: int) -> str:
    return f"entrada:{entrada_id}"


def parsear_chave(chave: str) -> tuple:
    """
    "gasto:123"                  -> ("gasto", 123, None)
    "entrada:9"                  -> ("entrada", 9, None)
    "fatura:5:2026-07-01"        -> ("fatura", 5, date(2026, 7, 1))

    Levanta AppError 400 em qualquer formato fora disso — a chave vem da
    URL, então é entrada não confiável, não detalhe interno.
    """
    partes = (chave or "").split(":")
    try:
        if partes[0] == "gasto" and len(partes) == 2:
            return ("gasto", int(partes[1]), None)
        if partes[0] == "entrada" and len(partes) == 2:
            return ("entrada", int(partes[1]), None)
        if partes[0] == "fatura" and len(partes) == 3:
            return ("fatura", int(partes[1]), date.fromisoformat(partes[2]))
    except (ValueError, TypeError):
        pass
    raise AppError(f"Identificador de conta inválido: {chave}", 400, "chave_invalida")


def _mes_para_data(mes: str) -> date:
    """"YYYY-MM" -> date(YYYY, MM, 1). Default: mês corrente."""
    if not mes:
        return date.today().replace(day=1)
    try:
        ano, mes_num = (int(p) for p in mes.split("-")[:2])
        return date(ano, mes_num, 1)
    except (ValueError, TypeError):
        raise AppError("Mês inválido — use o formato YYYY-MM.", 400, "mes_invalido")


# ---------------------------------------------------------------------------
# Montagem das linhas
# ---------------------------------------------------------------------------

def _filtro_escopo(gid: int | None, usuario_id: int, alias: str = "g") -> tuple[str, list]:
    """Mesmo padrão grupo_id/usuario_id do resto dos services (com grupo, o
    dado é compartilhado; sem grupo, é pessoal)."""
    if gid:
        return f"{alias}.grupo_id = %s", [gid]
    return f"{alias}.usuario_id = %s AND {alias}.grupo_id IS NULL", [usuario_id]


def _linhas_avulsas(conn, gid, usuario_id, mes_alvo: date) -> list[dict]:
    """
    Contas que são 1 gasto só: fixas e parcelas em forma SEM fatura
    (boleto, débito, pix, "Custo Fixo").

    O filtro `despesa_fixa_id IS NOT NULL OR compra_parcelada_id IS NOT NULL`
    é o que exclui o avulso à vista (ver docstring do módulo). O
    `fp.dia_fechamento IS NULL` é o que evita contar duas vezes: fixa paga
    no cartão já está dentro da linha da fatura.
    """
    escopo, params = _filtro_escopo(gid, usuario_id)
    with conn.cursor() as cur:
        cur.execute(
            f"""SELECT g.id, g.descricao, g.valor, g.data, g.pago, g.pago_em,
                       g.despesa_fixa_id, g.compra_parcelada_id,
                       c.nome AS categoria_nome, fp.nome AS forma_nome,
                       cp.parcelas AS total_parcelas
                FROM gastos g
                LEFT JOIN formas_pagamento fp   ON fp.id = g.forma_pagamento_id
                LEFT JOIN categorias c          ON c.id  = g.categoria_id
                LEFT JOIN compras_parceladas cp ON cp.id = g.compra_parcelada_id
                WHERE {escopo}
                  AND (fp.id IS NULL OR fp.dia_fechamento IS NULL)
                  AND (g.despesa_fixa_id IS NOT NULL OR g.compra_parcelada_id IS NOT NULL)
                  AND DATE_TRUNC('month', g.competencia) = DATE_TRUNC('month', %s::date)
                ORDER BY g.data, g.descricao""",
            params + [mes_alvo],
        )
        linhas = []
        for r in cur.fetchall():
            linhas.append({
                "chave": chave_gasto(r["id"]),
                "tipo": "gasto",
                "descricao": r["descricao"] or "(sem descrição)",
                "detalhe": r["forma_nome"] or r["categoria_nome"] or "",
                "valor": float(r["valor"]),
                "valor_pago": None,
                "pago": bool(r["pago"]),
                "pago_em": r["pago_em"],
                "vencimento": r["data"].isoformat() if r["data"] else None,
                "editavel": True,
                "origem": "fixa" if r["despesa_fixa_id"] else "parcela",
            })
        return linhas


def _linhas_faturas(conn, gid, usuario_id, mes_alvo: date, formas: list,
                     projecoes_por_mes: dict) -> list[dict]:
    """
    Uma linha por fatura de cartão que VENCE no mês do board — a "Cartão BTG
    6.000" da planilha. O valor é a soma dos gastos daquela competência, e
    fica intocado mesmo quando o Lucas paga um valor diferente (o valor pago
    mora em faturas_pagamentos.valor_pago; ver migração 027).

    `projecoes_por_mes` traz as fixas em cartão que o lançador ainda não
    materializou naquela competência — sem somá-las, a fatura de um mês
    futuro apareceria menor do que vai ser de verdade.

    Também soma o ajuste manual da fatura (`ajustes_fatura`, migração 028 —
    juros/IOF/arredondamento do banco que não vira um gasto lançado). Até
    29/08/2026 esta função ignorava a tabela: o board mostrava o valor bruto
    enquanto o /saldo do bot e o modal "Ver fatura" (services/faturas.py::
    status_cartao, que já aplica `_get_ajuste`) mostravam o valor ajustado —
    os três precisam bater, então reusa a mesma função em vez de duplicar a
    lógica de soma.
    """
    escopo, params_escopo = _filtro_escopo(gid, usuario_id)
    linhas = []

    for forma in formas:
        if not forma.get("dia_fechamento"):
            continue  # não é cartão: não tem fatura, sai linha a linha

        for competencia in competencias_que_vencem_em(
            mes_alvo, forma.get("dia_fechamento"), forma.get("dia_vencimento")
        ):
            with conn.cursor() as cur:
                cur.execute(
                    f"""SELECT COALESCE(SUM(g.valor), 0) AS total, COUNT(*) AS itens
                        FROM gastos g
                        WHERE {escopo} AND g.forma_pagamento_id = %s
                          AND DATE_TRUNC('month', g.competencia) = DATE_TRUNC('month', %s::date)""",
                    params_escopo + [forma["id"], competencia],
                )
                agregado = cur.fetchone()

                cur.execute(
                    "SELECT valor_pago, pago_em FROM faturas_pagamentos "
                    "WHERE forma_pagamento_id = %s AND competencia = %s",
                    (forma["id"], competencia),
                )
                pagamento = cur.fetchone()

                ajuste, motivo_ajuste = _get_ajuste(cur, forma["id"], competencia)

            total = float(agregado["total"])
            itens = int(agregado["itens"])

            previstas = [
                p for p in projecoes_por_mes.get(competencia.strftime("%Y-%m"), [])
                if p.get("forma_pagamento_id") == forma["id"]
            ]
            total_previsto = sum(float(p["valor"]) for p in previstas)

            # Fatura zerada e sem previsão nenhuma não vira linha — cartão
            # que não foi usado naquele mês não é uma conta a pagar. O ajuste
            # entra fora dessa checagem de propósito: fatura zerada não tem
            # ajuste manual salvo na prática (o form só existe depois que a
            # fatura já tem gasto), então isolar esse caso não muda o board.
            if total + total_previsto <= 0:
                continue

            linhas.append({
                "chave": chave_fatura(forma["id"], competencia),
                "tipo": "fatura",
                "descricao": f"Fatura {forma['nome']}",
                "detalhe": _detalhe_fatura(itens, len(previstas)),
                "valor": total + total_previsto + ajuste,
                "ajuste_fatura": ajuste,
                "ajuste_motivo": motivo_ajuste,
                "valor_pago": float(pagamento["valor_pago"])
                    if pagamento and pagamento["valor_pago"] is not None else None,
                "pago": pagamento is not None,
                "pago_em": pagamento["pago_em"] if pagamento else None,
                "vencimento": _data_vencimento(mes_alvo, forma.get("dia_vencimento")),
                # Editar o valor de uma fatura não altera `gastos` (seria
                # mexer em N compras já registradas) — grava valor_pago à
                # parte. O front deixa claro que é "quanto paguei", não
                # "quanto a fatura fechou".
                "editavel": True,
                "origem": "fatura",
                "competencia": competencia.isoformat(),
                "forma_pagamento_id": forma["id"],
                "tem_previsto": bool(previstas),
            })

    return linhas


def _detalhe_fatura(itens: int, previstas: int) -> str:
    partes = [f"{itens} lançamento{'s' if itens != 1 else ''}"]
    if previstas:
        partes.append(f"+{previstas} fixa(s) ainda não lançada(s)")
    return " ".join(partes)


def _data_vencimento(mes_alvo: date, dia_vencimento: int | None) -> str | None:
    """Data exibida no card. Capa no último dia do mês pela mesma razão do
    _dia_efetivo das fixas (dia 31 em fevereiro)."""
    if not dia_vencimento:
        return None
    dia = min(dia_vencimento, calendar.monthrange(mes_alvo.year, mes_alvo.month)[1])
    return date(mes_alvo.year, mes_alvo.month, dia).isoformat()


def _linhas_previstas(conn, gid, usuario_id, mes_alvo: date,
                       projecoes_por_mes: dict) -> list[dict]:
    """
    Fixas NÃO-cartão que o lançador ainda não materializou no mês (mês
    futuro além do horizonte de antecipação do passe 2 —
    services/despesas_fixas.py). Entram como linha somente-leitura: não têm
    id em `gastos`, então não há o que marcar como pago. Existem só pra que
    um mês futuro não pareça vazio.
    """
    linhas = []
    for p in projecoes_por_mes.get(mes_alvo.strftime("%Y-%m"), []):
        if p.get("dia_fechamento_forma"):
            continue  # em cartão: já foi somado na linha da fatura
        linhas.append({
            "chave": p["id"],  # "projetado-fixa-{id}-{mes}" — não persistível
            "tipo": "previsto",
            "descricao": p["descricao"],
            "detalhe": "ainda não lançada",
            "valor": float(p["valor"]),
            "valor_pago": None,
            "pago": False,
            "pago_em": None,
            "vencimento": p["data"],
            "editavel": False,
            "origem": "previsto",
        })
    return linhas


def _projecoes(conn, gid, usuario_id, meses: set, formas: list) -> dict:
    """
    Cache de projetar_despesas_fixas por mês — a mesma competência costuma
    ser pedida por mais de um cartão, e a função é cara (várias queries).
    Anota dia_fechamento da forma em cada projeção pra quem chama saber se
    ela cai dentro de uma fatura ou vira linha própria.
    """
    formas_por_id = {f["id"]: f for f in formas}
    cache = {}
    for mes in meses:
        projetados = projetar_despesas_fixas(conn, gid, usuario_id, mes)
        for p in projetados:
            forma = formas_por_id.get(p.get("forma_pagamento_id")) or {}
            p["dia_fechamento_forma"] = forma.get("dia_fechamento")
        cache[mes] = projetados
    return cache


def listar_contas_mes(usuario_id: int, mes: str = None) -> dict:
    """
    Payload da tela de contas: as 3 colunas da planilha (entradas, a pagar,
    pagas) + os totais que ficavam nas células de resumo do Excel.

    `mes` é o mês do CAIXA (quando a conta é paga), não a competência do
    gasto — a fatura que fechou em 28/07 aparece no board de agosto.
    """
    mes_alvo = _mes_para_data(mes)

    # Buscado UMA vez e passado adiante: get_formas_pagamento abre conexão
    # própria, e ele é necessário em 3 pontos do fluxo abaixo.
    formas = get_formas_pagamento(usuario_id)

    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)

        # Competências envolvidas: a do próprio mês (contas não-cartão) e as
        # das faturas que vencem nele (podem ser do mês anterior).
        meses_necessarios = {mes_alvo.strftime("%Y-%m")}
        for forma in formas:
            for c in competencias_que_vencem_em(
                mes_alvo, forma.get("dia_fechamento"), forma.get("dia_vencimento")
            ):
                meses_necessarios.add(c.strftime("%Y-%m"))

        projecoes = _projecoes(conn, gid, usuario_id, meses_necessarios, formas)

        linhas = (
            _linhas_avulsas(conn, gid, usuario_id, mes_alvo)
            + _linhas_faturas(conn, gid, usuario_id, mes_alvo, formas, projecoes)
            + _linhas_previstas(conn, gid, usuario_id, mes_alvo, projecoes)
        )

        entradas = _linhas_entradas(conn, gid, usuario_id, mes_alvo)

    a_pagar = [l for l in linhas if not l["pago"]]
    pagas = [l for l in linhas if l["pago"]]

    total_entradas = sum(e["valor"] for e in entradas)
    # No total pago vale o valor REALMENTE pago quando ele existe (fatura de
    # 6.000 paga em 5.500 tira 5.500 do caixa, não 6.000).
    total_pago = sum(l["valor_pago"] if l["valor_pago"] is not None else l["valor"]
                     for l in pagas)
    total_a_pagar = sum(l["valor"] for l in a_pagar)

    return {
        "mes": mes_alvo.strftime("%Y-%m"),
        "entradas": entradas,
        "a_pagar": a_pagar,
        "pagas": pagas,
        "totais": {
            "entradas": total_entradas,
            "a_pagar": total_a_pagar,
            "pago": total_pago,
            "saidas": total_a_pagar + total_pago,
            # A "SOBRA MÊS" da planilha.
            "sobra": total_entradas - (total_a_pagar + total_pago),
        },
    }


def _linhas_entradas(conn, gid, usuario_id, mes_alvo: date) -> list[dict]:
    """Coluna "Entradas" da planilha. Entrada tem `competencia` própria
    desde a migração 028 (dia_corte do usuário — salário não tem fatura,
    mas tem "mês do recebimento" igual gasto tem "mês da fatura")."""
    escopo, params = _filtro_escopo(gid, usuario_id, alias="e")
    with conn.cursor() as cur:
        cur.execute(
            f"""SELECT e.id, e.descricao, e.valor, e.data
                FROM entradas e
                WHERE {escopo}
                  AND DATE_TRUNC('month', e.competencia) = DATE_TRUNC('month', %s::date)
                ORDER BY e.data, e.descricao""",
            params + [mes_alvo],
        )
        return [{
            "chave": chave_entrada(r["id"]),
            "tipo": "entrada",
            "descricao": r["descricao"] or "(sem descrição)",
            "valor": float(r["valor"]),
            "data": r["data"].isoformat() if r["data"] else None,
            # Editável igual gasto/fixa (pedido do Lucas, 24/07/2026) — sem
            # status de pago, então não passa por marcar_conta, só por
            # editar_valor_conta (que reusa services.entradas.atualizar_entrada).
            "editavel": True,
        } for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Mutações — o que o drag-and-drop e a edição inline chamam
# ---------------------------------------------------------------------------

def marcar_conta(usuario_id: int, chave: str, pago: bool,
                  valor_pago: float = None) -> dict:
    """
    Move a linha entre "Não pago" e "Pago".

    Gasto: flip do booleano. Fatura: INSERT/DELETE em faturas_pagamentos —
    a presença da linha É o estado (ver migração 027), não há booleano lá.
    `valor_pago` só é aceito na fatura; num gasto, "paguei outro valor"
    significa que o valor do gasto estava errado, e aí o certo é editar o
    gasto (services/gastos.py::atualizar_gasto) em vez de guardar dois
    números divergentes pra mesma linha.

    Entrada não passa por aqui: dinheiro que entra não tem "pago/não pago",
    só valor. O front nunca chama isto pra uma chave "entrada:" (o card não
    tem o botão de status), mas a rejeição explícita existe pra não deixar
    a chave cair, sem querer, no bloco de fatura logo abaixo — ident de
    entrada tratado como forma_pagamento_id seria um bug silencioso.
    """
    tipo, ident, competencia = parsear_chave(chave)

    if tipo == "entrada":
        raise AppError(
            "Entrada não tem status de pago — edite o valor diretamente.",
            400, "sem_status_pago",
        )

    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)

        if tipo == "gasto":
            escopo, params = _filtro_escopo(gid, usuario_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""UPDATE gastos g SET pago = %s, pago_em = {'NOW()' if pago else 'NULL'}
                        WHERE g.id = %s AND {escopo} RETURNING g.id""",
                    [pago, ident] + params,
                )
                encontrado = cur.fetchone()
                conn.commit()
            if not encontrado:
                raise AppError("Conta não encontrada.", 404, "nao_encontrado")
            return {"chave": chave, "pago": pago}

        # tipo == "fatura" — valida que o cartão é mesmo do usuário/grupo
        # antes de gravar (faturas_pagamentos não tem grupo_id próprio: o
        # dono é a forma de pagamento, e é nela que a checagem tem que ser
        # feita, senão qualquer id de cartão seria aceito).
        if not any(f["id"] == ident for f in get_formas_pagamento(usuario_id)):
            raise AppError("Forma de pagamento não encontrada.", 404, "nao_encontrado")

        with conn.cursor() as cur:
            if pago:
                cur.execute(
                    """INSERT INTO faturas_pagamentos (forma_pagamento_id, competencia, valor_pago)
                       VALUES (%s, %s, %s)
                       ON CONFLICT (forma_pagamento_id, competencia)
                       DO UPDATE SET valor_pago = EXCLUDED.valor_pago, pago_em = NOW()""",
                    (ident, competencia, valor_pago),
                )
            else:
                cur.execute(
                    "DELETE FROM faturas_pagamentos WHERE forma_pagamento_id = %s AND competencia = %s",
                    (ident, competencia),
                )
            conn.commit()
        return {"chave": chave, "pago": pago, "valor_pago": valor_pago}


def editar_valor_conta(usuario_id: int, chave: str, valor: float) -> dict:
    """
    Edição inline do valor no card.

    Gasto: altera `gastos.valor` de verdade (é o valor da conta).

    Entrada: altera `entradas.valor` de verdade, mesma lógica do gasto —
    entrada não tem os dois números (fechado x pago) que a fatura tem, é
    só um valor (services/entradas.py::atualizar_entrada).

    Fatura: NÃO altera `gastos` — grava valor_pago. Editar o total de uma
    fatura significaria redistribuir a diferença entre N compras já
    registradas, e não existe critério pra isso. O que o Lucas quer dizer
    ao editar uma fatura é "paguei um valor diferente do que fechou", e é
    exatamente isso que fica guardado.

    Daí a restrição: numa fatura AINDA NÃO PAGA não há o que editar — o
    valor exibido é a soma real dos gastos, e "quanto vou pagar" antes de
    pagar não é um dado, é um plano. Recusar aqui (em vez de só esconder o
    lápis no front) evita o efeito colateral silencioso de a edição criar a
    linha em faturas_pagamentos e, com isso, marcar a fatura como paga sem
    ninguém ter pedido — a presença da linha É o estado (migração 027).
    """
    tipo, ident, competencia = parsear_chave(chave)
    if valor is None or float(valor) < 0:
        raise AppError("Valor inválido.", 400, "valor_invalido")

    if tipo == "gasto":
        # Reusa o service de gastos em vez de fazer UPDATE aqui — 1 fonte de
        # verdade pra validação/escopo de edição de gasto (padrão CLAUDE.md).
        from services.gastos import atualizar_gasto
        gasto = atualizar_gasto(usuario_id, ident, valor=float(valor))
        if not gasto:
            raise AppError("Conta não encontrada.", 404, "nao_encontrado")
        return {"chave": chave, "valor": float(valor)}

    if tipo == "entrada":
        from services.entradas import atualizar_entrada
        entrada = atualizar_entrada(usuario_id, ident, valor=float(valor))
        if not entrada:
            raise AppError("Entrada não encontrada.", 404, "nao_encontrado")
        return {"chave": chave, "valor": float(valor)}

    if not any(f["id"] == ident for f in get_formas_pagamento(usuario_id)):
        raise AppError("Forma de pagamento não encontrada.", 404, "nao_encontrado")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE faturas_pagamentos SET valor_pago = %s "
                "WHERE forma_pagamento_id = %s AND competencia = %s RETURNING id",
                (float(valor), ident, competencia),
            )
            atualizado = cur.fetchone()
            conn.commit()

    if not atualizado:
        raise AppError(
            "O valor de uma fatura vem da soma dos lançamentos. Marque a fatura "
            "como paga para registrar um valor pago diferente.",
            409, "fatura_nao_paga",
        )
    return {"chave": chave, "valor_pago": float(valor)}


# ---------------------------------------------------------------------------
# Consumido por services/resumo.py
# ---------------------------------------------------------------------------

def totais_contas_mes(usuario_id: int, mes: str = None) -> dict:
    """Só os totais, pro StatCard do dashboard — mesma montagem de linhas,
    pra não existir um segundo jeito de somar a mesma coisa."""
    return listar_contas_mes(usuario_id, mes)["totais"]


# ---------------------------------------------------------------------------
# Detalhe de uma linha (pedido do Lucas, 24/07/2026: "clicar no Cartão abre
# as despesas do cartão no mês")
# ---------------------------------------------------------------------------

def detalhe_conta(usuario_id: int, chave: str) -> dict:
    """
    Breakdown de UMA linha do board. Só existe pra fatura: ela é 1 card
    resumindo N gastos, e é exatamente essa lista que este endpoint devolve.
    Gasto avulso/fixa já É o item — não tem o que abrir por trás dele, e o
    front nem oferece o clique nesse caso (não é uma limitação escondida:
    pedir detalhe de uma chave "gasto:" é erro de uso, por isso 400).

    Traz TODOS os gastos daquele cartão naquela competência, não só os que
    entram no board como linha própria — o card resume o TOTAL da fatura
    (que inclui compra avulsa no cartão), então o detalhe tem que bater com
    esse total, senão a soma dos itens do modal não fecharia com o valor do
    card que o abriu.
    """
    tipo, forma_id, competencia = parsear_chave(chave)
    if tipo != "fatura":
        raise AppError("Só faturas têm detalhe — a conta já é o item.", 400, "sem_detalhe")

    forma = next((f for f in get_formas_pagamento(usuario_id) if f["id"] == forma_id), None)
    if not forma:
        raise AppError("Forma de pagamento não encontrada.", 404, "nao_encontrado")

    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        escopo, params = _filtro_escopo(gid, usuario_id)
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT g.id, g.descricao, g.valor, g.data,
                           c.nome AS categoria_nome, cp.parcelas AS total_parcelas
                    FROM gastos g
                    LEFT JOIN categorias c          ON c.id  = g.categoria_id
                    LEFT JOIN compras_parceladas cp ON cp.id = g.compra_parcelada_id
                    WHERE {escopo} AND g.forma_pagamento_id = %s
                      AND DATE_TRUNC('month', g.competencia) = DATE_TRUNC('month', %s::date)
                    ORDER BY g.data, g.descricao""",
                params + [forma_id, competencia],
            )
            itens = [dict(r) for r in cur.fetchall()]

    return {
        "chave": chave,
        "forma_nome": forma["nome"],
        "competencia": competencia.isoformat(),
        "itens": itens,
        "total": sum(float(i["valor"]) for i in itens),
    }
