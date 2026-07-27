"""
services/ai_fallback.py — Fase 3.6 do PLANO_EXECUCAO.md (gap G4), estendida
em 24/07/2026 (pedido do Lucas: "qualquer comando que o usuario der que nao
faça parte no app, a IA precisa entender qual ação tomar... quando usuario
perguntar algo sobre o app, a IA responde").

Fallback de IA para mensagens que não batem em nenhum comando conhecido nem
têm valor extraído por `parser.extrair_valor` (regex já falhou antes disso
ser chamado — ver handler.py:_processar_input_livre).

Dois atalhos baratos resolvem sem gastar 1 chamada de LLM por mensagem
(preocupação de custo/latência explícita no plano, 3.6):
1. Fuzzy "ajuda"/"ajudar"/"ajude" — mostra o menu de comandos.
2. Fuzzy "cancelar"/"esquece" — não faz nada, sem chamar IA.

Só cai em `ai.classificar_mensagem` (OpenAI) se nenhum atalho bateu. A partir
daí a intenção pode ser:
- 'gasto'    -> já existia (Fase 3.6)
- 'pergunta' -> usuário perguntando "como faço X" — resposta vem grounded na
  referência de comandos (cmd_ajuda), montada dentro do próprio prompt de
  ai.py::classificar_mensagem, não inventada aqui.
- 'comando'  -> usuário quer executar uma ação em linguagem natural (ex:
  "adiciona a Yasmin no grupo com o numero X"). Este módulo VALIDA que o
  `comando_sugerido` devolvido pela IA começa com um prefixo de comando real
  do bot antes de propagar pra frente — proteção contra a IA alucinar um
  comando que não existe. A EXECUÇÃO em si (e a confirmação "sim" antes de
  executar) fica em handler.py, que já tem o roteador de comandos.

`completar_categoria_forma` (novo) é uma função separada, chamada de um
lugar diferente (handler.py:_processar_input_livre, quando o VALOR já foi
extraído por regex mas categoria/forma não bateram em nenhum alias) — não
passa por `interpretar_mensagem` porque ali o cenário é outro (valor incerto
demais até pra tentar regex).
"""

from difflib import SequenceMatcher

from ai import classificar_mensagem, sugerir_categoria_forma
from utils.logging_config import obter_logger

logger = obter_logger("finbot.ai_fallback")

_AJUDA_KEYWORDS = ["ajuda", "ajudar", "ajude", "help", "comandos", "como funciona"]
_CANCELAR_KEYWORDS = ["cancelar", "cancela", "esquece", "deixa pra la", "deixa pra lá"]

# Prefixos de comando reais do bot (espelha o roteador em
# handler.py:_despachar_comando) — usado só pra VALIDAR o `comando_sugerido`
# que a IA devolve antes de propagar pra confirmação/execução. Se a IA
# alucinar algo fora desse vocabulário, cai em 'indefinido' em vez de
# oferecer pro usuário confirmar um comando que não existe.
_PREFIXOS_COMANDO_VALIDOS = (
    "saldo", "resumo", "gastos", "excluir", "editar ultimo",
    "forma ", "categoria ", "fixa ", "entrada ", "apelido ",
    "vincular ", "grupo", "limite ",
)


def _comando_valido(comando: str | None) -> bool:
    if not comando or not comando.strip():
        return False
    txt = comando.strip().lower()
    return any(txt.startswith(p) for p in _PREFIXOS_COMANDO_VALIDOS)


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
    - 'pergunta'   -> {'intencao': 'pergunta', 'resposta': str} — resposta já
                       pronta (grounded na referência de comandos), handler.py
                       só devolve pro usuário, sem ação nenhuma no banco.
    - 'comando'    -> {'intencao': 'comando', 'comando_sugerido': str,
                        'descricao_acao': str} — handler.py pede confirmação
                       ("sim") antes de rotear pro comando de verdade; nunca
                       executa direto (ação pode alterar grupo/membros/etc.).
    - 'indefinido' -> IA não conseguiu deduzir nada útil (ou a chamada falhou,
                       ou sugeriu um comando fora do vocabulário conhecido)
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
            "descricao": resultado.get("descricao") or texto,
        }

    if intencao == "pergunta":
        resposta = resultado.get("resposta")
        if not resposta or not str(resposta).strip():
            return {"intencao": "indefinido"}
        return {"intencao": "pergunta", "resposta": str(resposta).strip()}

    if intencao == "comando":
        comando_sugerido = resultado.get("comando_sugerido")
        if not _comando_valido(comando_sugerido):
            logger.warning(
                f"IA sugeriu comando fora do vocabulário conhecido, descartado: {comando_sugerido!r}"
            )
            return {"intencao": "indefinido"}
        return {
            "intencao": "comando",
            "comando_sugerido": comando_sugerido.strip(),
            "descricao_acao": (resultado.get("descricao_acao") or comando_sugerido).strip(),
        }

    return {"intencao": "indefinido"}


def completar_categoria_forma(
    mensagem: str,
    categorias: list[dict],
    formas: list[dict],
    categoria_atual: dict | None,
    forma_atual: dict | None,
) -> tuple[dict | None, dict | None]:
    """
    Pedido do Lucas (24/07/2026): "IA consiga também alocar gastos pelo
    entendimento da mensagem" — ex: "50 remédio" tem valor certo (regex), mas
    "remédio" não bate em nenhum alias de categoria (parser.py); a IA
    entende que é Farmácia.

    Só chamada quando `categoria_atual` e/ou `forma_atual` já vieram None do
    casamento por palavra-chave (handler.py:_processar_input_livre) — nunca
    quando os dois já foram achados, pra não gastar 1 chamada de LLM em todo
    gasto registrado (só nos ambíguos).

    Nunca piora o que já foi encontrado por palavra-chave: só tenta
    completar o que está faltando, e se a IA falhar (erro de rede, JSON
    inválido) devolve os mesmos valores recebidos sem propagar a exceção —
    quem chama sempre tem um resultado utilizável (mesmo que igual ao que
    já tinha).
    """
    if categoria_atual and forma_atual:
        return categoria_atual, forma_atual

    try:
        sugestao = sugerir_categoria_forma(
            mensagem,
            [c["nome"] for c in categorias],
            [f["nome"] for f in formas],
        )
    except Exception as exc:
        logger.error(f"Falha ao sugerir categoria/forma via IA: {exc}")
        return categoria_atual, forma_atual

    categoria = categoria_atual or _resolver_por_nome(sugestao.get("categoria_sugerida"), categorias)
    forma     = forma_atual or _resolver_por_nome(sugestao.get("forma_sugerida"), formas)
    return categoria, forma
