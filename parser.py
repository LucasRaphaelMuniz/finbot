import re
import unicodedata
from datetime import date
from difflib import SequenceMatcher


def _sem_acento(texto: str) -> str:
    """Remove acentos (NFD + descarta combining marks) pra comparação
    tolerante a como a pessoa digita ('credito' vs 'crédito', 'CRÉDITO' vs
    'credito'). Usado só em comparação — nunca altera o que é gravado."""
    nfkd = unicodedata.normalize("NFD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))

# ---------------------------------------------------------------------------
# Entrada/receita (Fase 3.5) — checado antes do fluxo de gasto no input livre
# ---------------------------------------------------------------------------

_ENTRADA_KEYWORDS = ["recebi", "entrada", "salário", "salario", "caiu", "ganhei"]


def eh_entrada(texto: str) -> bool:
    """
    Detecta se o texto descreve uma entrada/receita, não um gasto — mesmo
    padrão de palavra-chave usado pelo resto do parser (aliases de categoria,
    palavras numéricas), não é uma classificação por IA.
    """
    texto_lower = texto.lower()
    return any(p in texto_lower for p in _ENTRADA_KEYWORDS)


# ---------------------------------------------------------------------------
# Valor
# ---------------------------------------------------------------------------

_VALOR_RE = re.compile(r"R?\$?\s*(\d+(?:[.,]\d+)*)", re.IGNORECASE)

# Tamanho máximo de uma sequência de dígitos SEM separador nenhum (nem
# ponto, nem vírgula) pra ainda ser aceita como valor em reais plausível.
# Acima disso é quase certeza de ser outra coisa digitada no meio da frase —
# telefone (10-11 dígitos), CPF (11), CNPJ (14) — ninguém digita um gasto de
# R$ 44.999.999.999,00 sem separador de milhar. Bug real (24/07/2026): "como
# adiciono... com o numero 44999999999" virava esse "valor", sequestrando a
# mensagem inteira pro fluxo de gasto ANTES de extrair_valor sequer devolver
# None — que é a condição que faz handler.py cair no fallback de IA (onde
# 'comando'/'pergunta' são decididos). 7 dígitos cobre o teste existente de
# valor grande sem pontuação (R$ 1.234.567) sem abrir brecha pra 10+ dígitos.
_MAX_DIGITOS_VALOR_SEM_SEPARADOR = 7

# Palavras numéricas → valor
_UNIDADES = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2,
    "três": 3, "tres": 3, "quatro": 4, "cinco": 5,
    "seis": 6, "sete": 7, "oito": 8, "nove": 9,
    "dez": 10, "onze": 11, "doze": 12, "treze": 13,
    "quatorze": 14, "catorze": 14, "quinze": 15,
    "dezesseis": 16, "dezasseis": 16, "dezessete": 17,
    "dezoito": 18, "dezenove": 19, "dezanove": 19,
}
_DEZENAS = {
    "vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50,
    "sessenta": 60, "setenta": 70, "oitenta": 80, "noventa": 90,
}
_CENTENAS = {
    "cem": 100, "cento": 100,
    "duzentos": 200, "duzentas": 200,
    "trezentos": 300, "trezentas": 300,
    "quatrocentos": 400, "quatrocentas": 400,
    "quinhentos": 500, "quinhentas": 500,
    "seiscentos": 600, "seiscentas": 600,
    "setecentos": 700, "setecentas": 700,
    "oitocentos": 800, "oitocentas": 800,
    "novecentos": 900, "novecentas": 900,
}
_TODAS_PALAVRAS = {**_CENTENAS, **_DEZENAS, **_UNIDADES}


def _palavras_para_numero(texto: str) -> float | None:
    """
    Converte sequências de palavras numéricas para float.
    Ex: "cem" → 100, "cento e cinquenta" → 150, "mil e duzentos" → 1200
    """
    t = texto.lower()
    # Normaliza variações
    t = re.sub(r"\be\b", "e", t)

    # Tokens relevantes: palavras numéricas + "mil" + "e"
    palavras = re.split(r"[\s,]+", t)

    total = 0
    acumulado = 0  # valor atual sendo construído
    encontrou = False

    i = 0
    while i < len(palavras):
        p = palavras[i].strip(".,!?")

        if p == "mil":
            acumulado = max(acumulado, 1) * 1000
            total += acumulado
            acumulado = 0
            encontrou = True
        elif p in _TODAS_PALAVRAS:
            v = _TODAS_PALAVRAS[p]
            if v >= 100:
                acumulado += v
            else:
                acumulado += v
            encontrou = True
        elif p == "e" and encontrou:
            pass  # conectivo, continua
        elif encontrou:
            # Parou de ler números
            break

        i += 1

    if encontrou:
        total += acumulado
        return float(total) if total > 0 else None
    return None


def _normalizar_numero_br(raw: str) -> float:
    """
    Normaliza uma string numérica em formato brasileiro para float.

    Regra (decisão D1 do PLANO_EXECUCAO.md):
    - Se há vírgula: vírgula é sempre o separador decimal, qualquer ponto
      presente é separador de milhar (removido). Ex: '1.103,04' -> 1103.04.
    - Se há só ponto: ambíguo. Só é tratado como decimal quando há exatamente
      um ponto seguido de exatamente 2 dígitos no final (ex: '1103.04',
      formato que aparece no caminho valor-da-IA -> texto -> parser).
      Qualquer outro caso (1, 3+ dígitos após o ponto, ou múltiplos pontos)
      é tratado como separador de milhar e removido. Ex: '1.103' -> 1103.0.
    - Sem pontuação: número inteiro.
    """
    raw = raw.strip(".,")
    if "," in raw:
        normalizado = raw.replace(".", "").replace(",", ".")
    elif "." in raw:
        partes = raw.split(".")
        if len(partes) == 2 and len(partes[1]) == 2:
            normalizado = raw
        else:
            normalizado = raw.replace(".", "")
    else:
        normalizado = raw
    return float(normalizado)


def extrair_valor(texto: str) -> float | None:
    """
    Retorna float ou None.
    Aceita: '50', '50,90', 'R$ 50', '1.103,04', 'cem', 'cinquenta reais', 'cento e vinte'.

    Ignora sequências de dígitos cruas (sem ponto/vírgula) implausivelmente
    longas pra ser um valor em reais — ver _MAX_DIGITOS_VALOR_SEM_SEPARADOR.
    `finditer` (não só o 1º match) pra não perder um valor de verdade que
    apareça DEPOIS de um número desses na mesma frase.
    """
    # 1) Dígitos (padrão original)
    for m in _VALOR_RE.finditer(texto):
        bruto = m.group(1)
        bare_longo_demais = (
            "." not in bruto and "," not in bruto
            and len(bruto) > _MAX_DIGITOS_VALOR_SEM_SEPARADOR
        )
        if bare_longo_demais:
            continue
        return _normalizar_numero_br(bruto)

    # 2) Palavras numéricas em português
    return _palavras_para_numero(texto)


# ---------------------------------------------------------------------------
# Data explícita no fim da mensagem (03/08/2026, pedido do Lucas)
#
# "restaurante 28,78 credito japones almoço de sexta 01-08" tem que
# registrar o gasto com data 01/08, não hoje. Aceita dd-mm, dd/mm, dd.mm
# (ano = corrente) e com ano explícito (dd/mm/aaaa, dd-mm-aa).
#
# Só olha o ÚLTIMO token da mensagem, de propósito: o mesmo padrão d/d
# aparece em descrição de parcela digitada à mão ("Amazon 2/12", como no
# print do Lucas em Lançamentos) — varrer a frase inteira atrás de
# qualquer coisa "dd/mm" criaria falso positivo ali. No fim da frase é
# onde faz sentido uma correção de data ("... foi dia 01-08"); no meio,
# "2/12" é descrição, não data.
# ---------------------------------------------------------------------------

_DATA_RE = re.compile(r"^(\d{1,2})[-/.](\d{1,2})(?:[-/.](\d{2,4}))?$")


def extrair_data(texto: str, hoje: date | None = None) -> date | None:
    """
    Retorna a data explícita no fim da mensagem, ou None (segue com a data
    default de quem chama — hoje). Rejeita dia/mês fora de faixa (dia>31,
    mês>12) e combinações que não existem no calendário (31/02).
    """
    if not texto:
        return None
    tokens = texto.strip().split()
    if not tokens:
        return None

    m = _DATA_RE.match(tokens[-1])
    if not m:
        return None

    dia, mes, ano_bruto = int(m.group(1)), int(m.group(2)), m.group(3)
    if not (1 <= dia <= 31 and 1 <= mes <= 12):
        return None

    if ano_bruto:
        ano = int(ano_bruto)
        if ano < 100:
            ano += 2000
    else:
        ano = (hoje or date.today()).year

    try:
        return date(ano, mes, dia)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Parcelamento (Fase 3.2)
# ---------------------------------------------------------------------------

_PARCELAS_RE = re.compile(
    r"(?:(\d{1,2})\s*x\b)"
    r"|(?:em\s+(\d{1,2})\s+vezes)"
    r"|(?:parcelad[oa]\s+em\s+(\d{1,2}))",
    re.IGNORECASE,
)


def extrair_parcelas(texto: str) -> int | None:
    """
    Detecta quantidade de parcelas no texto: '12x', 'em 12 vezes', 'parcelado em 12'.
    Retorna None se não houver menção a parcelamento, ou se o número for <= 1
    (parcelar em 1x não é parcelamento).
    """
    m = _PARCELAS_RE.search(texto.lower())
    if not m:
        return None
    grupo = next((g for g in m.groups() if g), None)
    if not grupo:
        return None
    n = int(grupo)
    return n if n > 1 else None


# ---------------------------------------------------------------------------
# Categoria (fuzzy + aliases)
# ---------------------------------------------------------------------------

# Mapeamento de aliases → fragmento do nome da categoria no banco.
# Chave: fragmento que aparece (case-insensitive) no nome da categoria.
# Valor: lista de palavras-chave que o usuário pode digitar.
_CAT_ALIASES: dict[str, list[str]] = {
    "mercado":     ["mercado", "supermercado", "feira", "hortifruti", "padaria", "açougue"],
    "combustível": ["gasolina", "etanol", "diesel", "posto", "abasteci", "combustivel", "combust"],
    "restaurante": ["restaurante", "almoço", "jantar", "lanche", "pizza", "comida",
                    "refeicao", "refeição", "cafe", "café", "hamburger", "hamburguer",
                    "ifood", "delivery"],
    "farmácia":    ["remedio", "remédio", "farmacia", "farmácia", "drogaria", "medicamento",
                    "vitamina", "suplemento"],
    "lazer":       ["cinema", "show", "teatro", "passeio", "diversao", "diversão",
                    "netflix", "spotify", "jogo", "game", "clube", "bar"],
    "educação":    ["escola", "curso", "faculdade", "universidade", "livro", "material",
                    "aula", "educacao", "educação", "mensalidade"],
    "saúde":       ["medico", "médico", "consulta", "hospital", "plano", "dentista",
                    "saude", "saúde", "academia", "fisio", "terapia"],
    "transporte":  ["uber", "99", "taxi", "táxi", "metro", "onibus", "ônibus", "passagem",
                    "condutor", "brt", "trem"],
    "outros":      ["outros", "misc", "diverso"],
}

def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def extrair_categoria(texto: str, categorias: list, threshold: float = 0.70):
    """
    Retorna o dict da categoria detectada ou None.

    `categorias` pode incluir tanto globais (grupo_id None/ausente) quanto
    customizadas de um grupo (Fase 3.1). Os aliases de `_CAT_ALIASES` só se
    aplicam às globais — uma categoria customizada só casa por nome exato
    (substring) ou por fuzzy match (etapa 3), nunca por um alias genérico que
    o grupo não escolheu.
    """
    texto_lower = texto.lower()
    palavras = re.split(r"\W+", texto_lower)

    # 1) Substring direto no nome da categoria
    for cat in categorias:
        nome = cat["nome"].lower()
        if nome in texto_lower:
            return cat

    # 2) Aliases — só para categorias globais (grupo_id None)
    for cat in categorias:
        if cat.get("grupo_id") is not None:
            continue
        nome_cat = cat["nome"].lower()
        for fragmento, aliases in _CAT_ALIASES.items():
            if fragmento in nome_cat or nome_cat in fragmento:
                if any(alias in texto_lower for alias in aliases):
                    return cat

    # 3) Fuzzy por palavra
    melhor_cat = None
    melhor_score = 0.0
    for cat in categorias:
        nome = cat["nome"].lower()
        for p in palavras:
            if not p:
                continue
            score = _sim(p, nome)
            if score >= threshold and score > melhor_score:
                melhor_score = score
                melhor_cat = cat

    return melhor_cat


# ---------------------------------------------------------------------------
# Forma de pagamento
# ---------------------------------------------------------------------------

_FORMA_ALIASES: list[tuple[str, list[str]]] = [
    # "debito"/"débito" fica fora deste grupo de propósito: quando existe
    # uma forma separada tipo "DÉBITO/PIX", o próprio nome dela já cobre a
    # palavra "debito" no primeiro check (match direto por token do nome).
    # Deixar "debito" aqui faria "cart" (ex.: forma "CRÉDITO", que também
    # entra neste grupo pelo alargamento de gatilho) roubar esse match —
    # crédito e débito são conceitos opostos, não deveriam compartilhar
    # grupo de alias.
    ("cart", ["cartao", "cartão", "card", "credito", "crédito",
              "visa", "master", "elo"]),
    ("pix",  ["pix", "dinheiro", "especie", "espécie", "cash",
              "transferencia", "transferência"]),
    ("ticket", ["ticket", "vale", "vr", "va", "refeicao", "refeição",
                "alimentacao", "alimentação", "beneficio", "benefício"]),
]


def extrair_forma_pagamento(texto: str, formas: list):
    """
    Retorna dict da forma detectada ou None.

    Duas correções (bug real 17/07/2026, "VA atualizacao 264" caiu no menu
    mesmo com "VA" no texto — não era esse caso específico, mas o teste
    revelou dois problemas vizinhos no mesmo mecanismo de match):

    1. Comparação por TOKEN (fronteira de palavra), não substring — "VA"
       não pode casar dentro de "vaquinha". Antes: `"va" in "vaquinha 30"`
       era True (substring). Agora: "va" precisa ser um token inteiro do
       texto tokenizado.
    2. Comparação sem acento nos dois lados — "credito" (usuário digita
       sem acento) não batia com o nome "CRÉDITO" cadastrado (com acento),
       porque só a versão SEM normalizar era comparada.
    """
    texto_normalizado = _sem_acento(texto.lower())
    tokens_texto = set(re.split(r"\W+", texto_normalizado)) - {""}

    for forma in formas:
        nome_normalizado = _sem_acento(forma["nome"].lower())

        # Palavras do nome (ex: "pix", "va", "vr", "credito") como token
        # inteiro no texto — mínimo 2 chars pra não casar token de 1 letra
        # à toa.
        palavras_nome = [w for w in re.split(r"\W+", nome_normalizado) if len(w) >= 2]
        if any(w in tokens_texto for w in palavras_nome):
            return forma

        # Aliases por tipo (ex: forma "CRÉDITO" com o usuário digitando
        # "cartao" ou "visa"). Gatilho do grupo: nome da forma contém o
        # fragmento (ex: "cartão de crédito" contém "cart") OU o próprio
        # nome da forma é um dos aliases do grupo (ex: forma cadastrada só
        # como "CRÉDITO", sem a palavra "cartão" — "credito" é alias do
        # grupo "cart"). Restrito ao grupo "ticket" NÃO usar essa segunda
        # regra: "va"/"vr" são ao mesmo tempo nomes de forma comuns E
        # aliases um do outro dentro do próprio grupo ("vr" é alias de
        # "ticket", que também é o grupo de "va") — alargar o gatilho ali
        # fazia "vr almoço" casar com a forma "VA" por tabela cruzada.
        for fragmento, aliases in _FORMA_ALIASES:
            aliases_normalizados = [_sem_acento(a) for a in aliases]
            gatilho = fragmento in nome_normalizado
            if fragmento != "ticket":
                gatilho = gatilho or nome_normalizado in aliases_normalizados
            if gatilho and any(a in tokens_texto for a in aliases_normalizados):
                return forma

    return None


# ---------------------------------------------------------------------------
# Descrição limpa (03/08/2026, pedido do Lucas)
#
# "200 Eloá pix berço portatil" registrava a MENSAGEM INTEIRA como
# descrição, mesmo já tendo extraído valor=200, categoria=Eloá e
# forma=Pix/Débito dela mesma — a tabela de Lançamentos mostrava a frase
# crua na coluna Descrição, duplicando o que as colunas Categoria/Forma/
# Valor já mostram. O que sobra depois de tirar exatamente o que foi
# reconhecido ("berço portatil") é a descrição de verdade.
#
# Por remoção de TOKEN, não por posição de regex. Duas regras DIFERENTES
# pra categoria e forma, de propósito:
#
# - Forma: remove nome ("CRÉDITO"/"DÉBITO/PIX") E os aliases do grupo dela
#   ("credito", "visa", "pix", "cartao"...) — vocabulário de forma de
#   pagamento não colide com descrição de verdade (ninguém escreve "visa"
#   ou "credito" querendo dizer outra coisa).
# - Categoria: remove só o NOME ("Restaurante", "Eloá"), NUNCA os aliases
#   do grupo. Aliases de categoria SÃO palavras comuns de descrição
#   ("almoço", "cinema", "show", "consulta" — ver _CAT_ALIASES) — foi o que
#   classificou a categoria, mas continuam informação útil na frase. Bug
#   pego pelo próprio teste desta função: "restaurante 28,78 credito
#   japones almoço de sexta" removendo aliases de categoria virava "japones
#   de sexta" (comeu "almoço"), quando o esperado é manter a frase inteira
#   menos o que é redundante com as colunas Categoria/Forma/Valor.
#
# Se a categoria/forma foi resolvida só por fuzzy (typo do usuário, sem
# bater nome/alias exato), a palavra digitada pode não ser removida —
# aceitável: sobrar 1 palavra a mais na descrição é inofensivo (nunca perde
# informação, só não limpa 100%).
# ---------------------------------------------------------------------------

def _limpar_token(tok: str) -> str:
    return _sem_acento(tok.strip(".,!?;:()\"'").lower())


def limpar_descricao(texto: str, valor: float | None, categoria: dict | None, forma: dict | None) -> str:
    """
    Remove do texto original os tokens já capturados como valor/categoria/
    forma de pagamento — o que sobra é a descrição. Pode devolver "" quando
    a mensagem inteira foi consumida pela classificação (ex: "restaurante
    9,20 pix"): melhor vazio do que repetir categoria/forma/valor na
    Descrição.
    """
    if not texto:
        return ""

    remover = set()

    if valor is not None:
        m = _VALOR_RE.search(texto)
        if m:
            remover.add(_limpar_token(m.group(1)))

    def _somar_nome(item):
        if not item:
            return
        nome_normalizado = _sem_acento(item["nome"].lower())
        for palavra in re.split(r"\W+", nome_normalizado):
            if palavra:
                remover.add(palavra)

    def _somar_nome_e_aliases(item, grupos_alias):
        if not item:
            return
        _somar_nome(item)
        nome_normalizado = _sem_acento(item["nome"].lower())
        for fragmento, aliases in grupos_alias:
            fragmento_norm = _sem_acento(fragmento.lower())
            if fragmento_norm in nome_normalizado or nome_normalizado in fragmento_norm:
                for alias in aliases:
                    remover.add(_sem_acento(alias.lower()))

    _somar_nome(categoria)
    _somar_nome_e_aliases(forma, _FORMA_ALIASES)

    sobra = [tok for tok in texto.split() if _limpar_token(tok) not in remover]
    return " ".join(sobra).strip()


# ---------------------------------------------------------------------------
# Comando em linguagem natural COM número no meio (24/07/2026)
#
# Bug real (print do Lucas): "Adiciona a forma de pgto teste com limite de
# 2999" caiu no menu "Qual a forma de pagamento?", como se fosse um gasto de
# R$ 2.999,00. Mesma classe do bug do telefone (44999999999) corrigido antes,
# mas o corte por quantidade de dígitos NÃO resolve este: 2999 é um número
# perfeitamente plausível como valor de gasto — o que denuncia que não é
# gasto é a ESTRUTURA da frase, não a magnitude do número.
#
# handler.py:_processar_input_livre só consulta a IA quando extrair_valor
# devolve None. Achando qualquer número, assume gasto e nunca dá à IA a
# chance de ver que era um comando. Este filtro é o sinal barato (sem LLM)
# de "espera, isso tem cara de ordem, não de gasto" — verbo de ação +
# substantivo do domínio do bot na mesma frase.
#
# Exige os DOIS de propósito. Só o verbo daria falso positivo em
# "adiciona 50 no mercado" (gasto legítimo); só o substantivo daria em
# "50 no cartão da categoria mercado". Juntos, o padrão é bem específico:
# ninguém escreve um gasto como "adiciona a forma X com limite Y".
# ---------------------------------------------------------------------------

_VERBOS_ACAO = (
    "adiciona", "adicione", "adicionar", "acrescenta", "acrescentar",
    "cria", "crie", "criar", "cadastra", "cadastre", "cadastrar",
    "remove", "remova", "remover", "exclui", "exclua", "excluir",
    "deleta", "delete", "deletar", "apaga", "apague", "apagar",
    "tira", "tire", "tirar", "altera", "altere", "alterar",
    "muda", "mude", "mudar", "atualiza", "atualize", "atualizar",
    "define", "defina", "definir", "coloca", "coloque", "colocar",
    "aumenta", "aumente", "aumentar", "diminui", "diminua", "diminuir",
    "vincula", "vincule", "vincular", "convida", "convide", "convidar",
    "lista", "liste", "listar", "mostra", "mostre", "mostrar",
    "configura", "configure", "configurar", "renomeia", "renomear",
)

# Substantivos que só fazem sentido falando DO BOT, não de uma compra.
# "cartão"/"mercado"/"pix" ficam FORA de propósito — são nomes de forma e
# categoria, apareceriam em gasto legítimo o tempo todo.
_SUBSTANTIVOS_DOMINIO = (
    "grupo", "membro", "participante",
    "forma de pagamento", "forma de pgto", "formas de pagamento",
    "categoria", "categorias",
    "despesa fixa", "despesas fixas", "conta fixa", "custo fixo",
    "limite", "apelido",
)


def parece_comando_natural(texto: str) -> bool:
    """
    True quando a frase tem estrutura de ORDEM sobre o próprio bot (verbo de
    ação + substantivo do domínio), mesmo contendo um número que o
    extrair_valor aceitaria como valor.

    Usado por handler.py pra consultar a IA ANTES de assumir gasto. Só um
    palpite barato: quem decide de fato é a IA (services/ai_fallback.py), e
    se ela não reconhecer um comando, o fluxo de gasto segue normal — um
    falso positivo aqui custa 1 chamada de LLM, não um registro errado.
    """
    txt = _sem_acento((texto or "").strip().lower())
    if not txt:
        return False

    # "forma de pgto" etc. são multi-palavra: checa por substring. Verbo
    # checa por token inteiro pra "criar" não casar dentro de outra palavra.
    tokens = set(re.split(r"\W+", txt))
    tem_verbo = any(v in tokens for v in _VERBOS_ACAO)
    if not tem_verbo:
        return False

    # "forma" sozinha é ambígua demais ("forma de pagamento" não, mas o
    # usuário pode escrever só "forma"): aceita a palavra isolada só quando
    # o verbo já apareceu, que é o caso aqui.
    tem_substantivo = (
        any(s in txt for s in _SUBSTANTIVOS_DOMINIO)
        or "forma" in tokens
        or "fixa" in tokens
    )
    return tem_substantivo


# ---------------------------------------------------------------------------
# Correção de algo pendente (24/07/2026)
#
# Bug real (print do Lucas): com uma confirmação em aberto ("Vou executar:
# forma add teste 2999. Confirma?"), ele respondeu "falei errado, o nome
# correto é teste123" e o bot ficou MUDO — o silêncio que eu tinha acabado
# de implementar tratou a correção como ruído.
#
# Diferença que o silêncio ignorava: "kkkk" não quer nada; "falei errado, o
# nome é X" quer MUITO, só que a frase sozinha não significa nada — ela é um
# delta sobre o que está pendente. Este filtro separa os dois casos sem
# gastar LLM em cada mensagem solta.
# ---------------------------------------------------------------------------

_MARCADORES_CORRECAO = (
    "errado", "errei", "me enganei", "enganei", "equivoquei",
    "na verdade", "na vdd", "quis dizer", "queria dizer", "digo",
    "correto", "o certo", "certo e", "corrige", "corrigir", "corrija",
    "desconsidera", "desconsidere", "ignora isso", "esquece isso",
    "nao e isso", "nao era isso", "foi mal", "perdao", "desculpa",
    "troca por", "muda para", "muda pra", "seria",
)


def parece_correcao(texto: str) -> bool:
    """
    True quando a frase tem cara de "eu errei, o certo é X" — sinal pra
    reinterpretar o que está pendente EM CONTEXTO, em vez de ignorar.

    Só um palpite barato: quem resolve é a IA, que recebe o pendente + esta
    frase e devolve a versão corrigida (services/ai_fallback.py).
    """
    txt = _sem_acento((texto or "").strip().lower())
    if not txt:
        return False
    return any(m in txt for m in _MARCADORES_CORRECAO)


# ---------------------------------------------------------------------------
# Filtro barato pra mensagens de grupo real do WhatsApp (Fase 7.4)
# ---------------------------------------------------------------------------

_COMANDOS_CONHECIDOS = (
    "ajuda", "saldo", "resumo", "gastos", "excluir", "editar ultimo",
    "forma ", "categoria ", "fixa ", "entrada ", "apelido ", "vincular ", "grupo",
)


def parece_gasto_ou_comando(texto: str) -> bool:
    """
    Filtro barato (sem IA), Fase 7.4 do PLANO_EXECUCAO.md: usado só em
    mensagens de grupos reais do WhatsApp (@g.us) antes de decidir se vale
    a pena chamar o fallback de IA (services/ai_fallback.py) — evita 1
    requisição de LLM por mensagem de chit-chat num grupo cheio de gente
    que não é dirigida ao bot.

    Mensagens diretas (1:1) NÃO passam por esse filtro (ver app.py) — quem
    manda pro bot ali é sempre o próprio dono da conta, sem ruído de
    terceiros, então vale sempre tentar interpretar.
    """
    txt = (texto or "").strip().lower()
    if not txt:
        return False
    if extrair_valor(texto) is not None:
        return True
    return any(txt.startswith(c) for c in _COMANDOS_CONHECIDOS)
