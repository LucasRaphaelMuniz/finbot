import re
from difflib import SequenceMatcher

# ---------------------------------------------------------------------------
# Valor
# ---------------------------------------------------------------------------

_VALOR_RE = re.compile(r"R?\$?\s*(\d{1,6}(?:[.,]\d{1,2})?)", re.IGNORECASE)

def extrair_valor(texto: str):
    """Retorna float ou None."""
    m = _VALOR_RE.search(texto)
    if m:
        raw = m.group(1).replace(",", ".")
        return float(raw)
    return None


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

        # Nome completo da forma no texto (cobre nomes curtos como VR, VA)
        if re.search(r"\b" + re.escape(nome_lower) + r"\b", texto_lower):
            return forma

        # Palavras longas do nome (ex: "Pix", "Dinheiro")
        palavras_nome = [w for w in re.split(r"\W+", nome_lower) if len(w) > 2]
        if any(w in texto_lower for w in palavras_nome):
            return forma

        # Aliases por tipo
        for fragmento, aliases in _FORMA_ALIASES:
            if fragmento in nome_lower:
                if any(a in texto_lower for a in aliases):
                    return forma

    return None
