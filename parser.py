import re
from difflib import SequenceMatcher

# ---------------------------------------------------------------------------
# Valor
# ---------------------------------------------------------------------------

_VALOR_RE = re.compile(r"R?\$?\s*(\d{1,6}(?:[.,]\d{1,2})?)", re.IGNORECASE)

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


def extrair_valor(texto: str) -> float | None:
    """
    Retorna float ou None.
    Aceita: '50', '50,90', 'R$ 50', 'cem', 'cinquenta reais', 'cento e vinte'.
    """
    # 1) Dígitos (padrão original)
    m = _VALOR_RE.search(texto)
    if m:
        raw = m.group(1).replace(",", ".")
        return float(raw)

    # 2) Palavras numéricas em português
    return _palavras_para_numero(texto)


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
    """Retorna o dict da categoria detectada ou None."""
    texto_lower = texto.lower()
    palavras = re.split(r"\W+", texto_lower)

    # 1) Substring direto no nome da categoria
    for cat in categorias:
        nome = cat["nome"].lower()
        if nome in texto_lower:
            return cat

    # 2) Aliases
    for cat in categorias:
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
    ("cart", ["cartao", "cartão", "card", "credito", "crédito",
              "debito", "débito", "visa", "master", "elo"]),
    ("pix",  ["pix", "dinheiro", "especie", "espécie", "cash",
              "transferencia", "transferência"]),
    ("ticket", ["ticket", "vale", "vr", "va", "refeicao", "refeição",
                "alimentacao", "alimentação", "beneficio", "benefício"]),
]


def extrair_forma_pagamento(texto: str, formas: list):
    """Retorna dict da forma detectada ou None."""
    texto_lower = texto.lower()

    for forma in formas:
        nome_lower = forma["nome"].lower()

        # Palavras do nome (ex: "Pix", "Dinheiro") no texto
        palavras_nome = [w for w in re.split(r"\W+", nome_lower) if len(w) > 2]
        if any(w in texto_lower for w in palavras_nome):
            return forma

        # Aliases por tipo
        for fragmento, aliases in _FORMA_ALIASES:
            if fragmento in nome_lower:
                if any(a in texto_lower for a in aliases):
                    return forma

    return None
