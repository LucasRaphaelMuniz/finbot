"""
services/ai_fallback.py — Fase 3.6 do PLANO_EXECUCAO.md (gap G4).

Fallback de IA para mensagens que não batem em nenhum comando conhecido nem
têm valor extraído por `parser.extrair_valor` (regex já falhou antes disso
ser chamado — ver handler.py:_processar_input_livre).

Dois atalhos baratos resolvem sem gastar 1 chamada de LLM por mensagem
(preocupação de custo/latência explícita no plano, 3.6):
1. Fuzzy "ajuda"/"ajudar"/"ajude" — mostra o menu de comandos.
2. Fuzzy "cancelar"/"esquece" — não faz nada, sem chamar IA.

Só cai em `ai.classificar_mensagem` (OpenAI) se nenhum atalho bateu.
"""

from difflib import SequenceMatcher

from ai import classificar_mensagem
from utils.logging_config import obter_logger

logger = obter_logger("finbot.ai_fallback")

_AJUDA_KEYWORDS = ["ajuda", "ajudar", "ajude", "help", "comandos", "como funciona"]
_CANCELAR_KEYWORDS = ["cancelar", "cancela", "esquece", "deixa pra la", "deixa pra lá"]


def _fuzzy_match(texto: str, keywords: list[str], limiar: float = 0.75) -> bool:
    """
    Compara por substring (cobre frases: "me ajuda ai" contém "ajuda") e,
    palavra a palavra, por similaridade (cobre erro de digitação: "ajduda").
    Comparar a frase inteira contra a keyword (como na 1ª versão) falhava
    pra qualquer frase com mais de 1-2 palavras — a similaridade cai demais
    diluída pelo resto do texto. Bug pego pelos próprios testes desta fase.
    """
    txt = texto.strip().lower()
    for kw in keywords:
        if kw in txt:
            return True
    for palavra in txt.split():
        for kw in keywords:
            if " " not in kw and SequenceMatcher(None, palavra, kw).ratio() >= limiar:
                return True
    return False


def _resolver_por_nome(nome: str | None, items: list[dict], limiar: float = 0.55):
    """
    Casa uma string sugerida pela IA contra categorias/formas reais do
    usuário. Mesma lógica de fuzzy match do `handler._selecionar_item`,
    duplicada aqui de propósito — acoplar os dois módulos por essa função
    pequena não vale a pena (D2 do PLANO_EXECUCAO.md: migração incremental,
    não big-bang de estrutura).
    """
    if not nome:
        return None
    nome_lower = nome.strip().lower()
    for item in items:
        if nome_lower in item["nome"].lower() or item["nome"].lower() in nome_lower:
            return item
    melhor, melhor_score = None, limiar
    for item in items:
        score = SequenceMatcher(None, nome_lower, item["nome"].lower()).ratio()
        if score > melhor_score:
            melhor_score = score
            melhor = item
    return melhor


def interpretar_mensagem(texto: str, categorias: list[dict], formas: list[dict]) -> dict:
    """
    Retorna sempre um dict com a chave 'intencao':
    - 'ajuda'      -> mostrar cmd_ajuda(), sem chamar IA
    - 'cancelar'   -> nenhuma ação, sem chamar IA
    - 'gasto'      -> {'intencao': 'gasto', 'valor': float,
                        'categoria': dict|None, 'forma': dict|None, 'descricao': str}
    - 'indefinido' -> IA não conseguiu deduzir nada útil (ou a chamada falhou)
    """
    if _fuzzy_match(texto, _AJUDA_KEYWORDS):
        return {"intencao": "ajuda"}
    if _fuzzy_match(texto, _CANCELAR_KEYWORDS):
        return {"intencao": "cancelar"}

    try:
        resultado = classificar_mensagem(texto)
    except Exception as exc:
        logger.error(f"Falha ao classificar mensagem via IA: {exc}")
        return {"intencao": "indefinido"}

    intencao = resultado.get("intencao")

    if intencao == "ajuda":
        return {"intencao": "ajuda"}

    if intencao == "gasto" and resultado.get("valor") is not None:
        try:
            valor = float(resultado["valor"])
        except (TypeError, ValueError):
            return {"intencao": "indefinido"}
        return {
            "intencao": "gasto",
            "valor": valor,
            "categoria": _resolver_por_nome(resultado.get("categoria_sugerida"), categorias),
            "forma": _resolver_por_nome(resultado.get("forma_sugerida"), formas),
            "descr