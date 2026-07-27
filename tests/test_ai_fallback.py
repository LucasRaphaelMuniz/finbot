"""
tests/test_ai_fallback.py — Fase 3.6 do PLANO_EXECUCAO.md (gap G4).

Cobre só a parte pura de services/ai_fallback.py:
- os atalhos baratos ("ajuda"/"cancelar") que NÃO chamam IA;
- a resolução fuzzy de categoria_sugerida/forma_sugerida contra listas reais;
- o tratamento de erro quando `ai.classificar_mensagem` falha ou devolve
  algo inesperado.

`ai.classificar_mensagem` (chamada real à OpenAI) é mockada via monkeypatch
— não fazemos requisição de rede em teste. O fluxo de ponta a ponta (sessão
"aguardando_confirmacao_ia" → registrar_gasto só com "sim") depende de banco
e é verificado manualmente via bot, mesmo padrão dos outros services.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import services.ai_fallback as ai_fallback


_CATEGORIAS = [
    {"id": 1, "nome": "Mercado"},
    {"id": 2, "nome": "Restaurante"},
]
_FORMAS = [
    {"id": 10, "nome": "Cartão"},
    {"id": 11, "nome": "Pix"},
]


def test_ajuda_fuzzy_nao_chama_ia(monkeypatch):
    chamou = {"valor": False}

    def _fake_classificar(texto):
        chamou["valor"] = True
        return {"intencao": "indefinido"}

    monkeypatch.setattr(ai_fallback, "classificar_mensagem", _fake_classificar)

    resultado = ai_fallback.interpretar_mensagem("me ajuda ai", _CATEGORIAS, _FORMAS)

    assert resultado == {"intencao": "ajuda"}
    assert chamou["valor"] is False


def test_cancelar_fuzzy_nao_chama_ia(monkeypatch):
    chamou = {"valor": False}

    def _fake_classificar(texto):
        chamou["valor"] = True
        return {"intencao": "indefinido"}

    monkeypatch.setattr(ai_fallback, "classificar_mensagem", _fake_classificar)

    resultado = ai_fallback.interpretar_mensagem("cancela isso ai", _CATEGORIAS, _FORMAS)

    assert resultado == {"intencao": "cancelar"}
    assert chamou["valor"] is False


def test_gasto_com_categoria_e_forma_resolvidas(monkeypatch):
    monkeypatch.setattr(
        ai_fallback, "classificar_mensagem",
        lambda texto: {
            "intencao": "gasto",
            "valor": 42.5,
            "categoria_sugerida": "mercado",
            "forma_sugerida": "cartao",
            "descricao": "compras",
        },
    )

    resultado = ai_fallback.interpretar_mensagem("qro por 42,50 la", _CATEGORIAS, _FORMAS)

    assert resultado["intencao"] == "gasto"
    assert resultado["valor"] == 42.5
    assert resultado["categoria"]["id"] == 1
    assert resultado["forma"]["id"] == 10
    assert resultado["descricao"] == "compras"


def test_gasto_sem_categoria_ou_forma_reconhecivel(monkeypatch):
    monkeypatch.setattr(
        ai_fallback, "classificar_mensagem",
        lambda texto: {
            "intencao": "gasto",
            "valor": 100.0,
            "categoria_sugerida": "algo bem aleatorio sem relacao",
            "forma_sugerida": None,
            "descricao": None,
        },
    )

    resultado = ai_fallback.interpretar_mensagem("gastei uns cem la", _CATEGORIAS, _FORMAS)

    assert resultado["intencao"] == "gasto"
    assert resultado["categoria"] is None
    assert resultado["forma"] is None


def test_gasto_sem_valor_vira_indefinido(monkeypatch):
    monkeypatch.setattr(
        ai_fallback, "classificar_mensagem",
        lambda texto: {"intencao": "gasto", "valor": None},
    )

    resultado = ai_fallback.interpretar_mensagem("nao sei quanto gastei", _CATEGORIAS, _FORMAS)

    assert resultado == {"intencao": "indefinido"}


def test_falha_na_chamada_ia_vira_indefinido(monkeypatch):
    def _explode(texto):
        raise RuntimeError("timeout")

    monkeypatch.setattr(ai_fallback, "classificar_mensagem", _explode)

    resultado = ai_fallback.interpretar_mensagem("mensagem qualquer", _CATEGORIAS, _FORMAS)

    assert resultado == {"intencao": "indefinido"}


def test_json_invalido_ou_intencao_desconhecida_vira_indefinido(monkeypatch):
    monkeypatch.setattr(
        ai_fallback, "classificar_mensagem",
        lambda texto: {"intencao": "algo_que_nao_existe"},
    )

    resultado = ai_fallback.interpretar_mensagem("???", _CATEGORIAS, _FORMAS)

    assert resultado == {"intencao": "indefinido"}


# ---------------------------------------------------------------------------
# 'pergunta' e 'comando' (24/07/2026) — pedido do Lucas: "qualquer comando
# que não faça parte do app, a IA precisa entender qual ação tomar... quando
# usuario perguntar algo sobre o app, a IA responde".
# ---------------------------------------------------------------------------

def test_pergunta_com_resposta_e_propagada(monkeypatch):
    monkeypatch.setattr(
        ai_fallback, "classificar_mensagem",
        lambda texto: {
            "intencao": "pergunta",
            "resposta": "Pra registrar um pagamento, digite o valor e a forma. Ex: 50 mercado cartão.",
        },
    )

    resultado = ai_fallback.interpretar_mensagem("como registro o pagamento?", _CATEGORIAS, _FORMAS)

    assert resultado == {
        "intencao": "pergunta",
        "resposta": "Pra registrar um pagamento, digite o valor e a forma. Ex: 50 mercado cartão.",
    }


def test_pergunta_sem_resposta_vira_indefinido(monkeypatch):
    """A IA classificou como pergunta mas não preencheu 'resposta' (JSON mal
    formado/incompleto) — não pode devolver mensagem vazia pro usuário."""
    monkeypatch.setattr(
        ai_fallback, "classificar_mensagem",
        lambda texto: {"intencao": "pergunta", "resposta": None},
    )

    resultado = ai_fallback.interpretar_mensagem("onde eu vejo isso no bot?", _CATEGORIAS, _FORMAS)

    assert resultado == {"intencao": "indefinido"}


def test_comando_valido_e_propagado_para_confirmacao(monkeypatch):
    monkeypatch.setattr(
        ai_fallback, "classificar_mensagem",
        lambda texto: {
            "intencao": "comando",
            "comando_sugerido": "grupo add 44912345678",
            "descricao_acao": "Adicionar +55 44 91234-5678 ao grupo",
        },
    )

    resultado = ai_fallback.interpretar_mensagem(
        "adiciona a Yasmin no grupo, numero 44912345678", _CATEGORIAS, _FORMAS
    )

    assert resultado == {
        "intencao": "comando",
        "comando_sugerido": "grupo add 44912345678",
        "descricao_acao": "Adicionar +55 44 91234-5678 ao grupo",
    }


def test_comando_fora_do_vocabulario_conhecido_vira_indefinido(monkeypatch):
    """Proteção contra alucinação: a IA sugeriu um 'comando' que não começa
    com nenhum prefixo real do bot — não pode virar uma confirmação de ação
    que na verdade não existe."""
    monkeypatch.setattr(
        ai_fallback, "classificar_mensagem",
        lambda texto: {
            "intencao": "comando",
            "comando_sugerido": "deletar minha conta inteira agora",
            "descricao_acao": "Apagar tudo",
        },
    )

    resultado = ai_fallback.interpretar_mensagem("apaga tudo", _CATEGORIAS, _FORMAS)

    assert resultado == {"intencao": "indefinido"}


def test_comando_sem_comando_sugerido_vira_indefinido(monkeypatch):
    monkeypatch.setattr(
        ai_fallback, "classificar_mensagem",
        lambda texto: {"intencao": "comando", "comando_sugerido": None},
    )

    resultado = ai_fallback.interpretar_mensagem("faz uma coisa la", _CATEGORIAS, _FORMAS)

    assert resultado == {"intencao": "indefinido"}


def test_comando_sem_descricao_acao_usa_o_proprio_comando(monkeypatch):
    """descricao_acao é opcional na resposta da IA — sem ela, mostra o
    comando cru mesmo (melhor que travar ou mostrar 'None')."""
    monkeypatch.setattr(
        ai_fallback, "classificar_mensagem",
        lambda texto: {"intencao": "comando", "comando_sugerido": "forma add Nubank 2000"},
    )

    resultado = ai_fallback.interpretar_mensagem("cria uma forma nubank com 2000", _CATEGORIAS, _FORMAS)

    assert resultado["descricao_acao"] == "forma add Nubank 2000"


def test_comando_valido_aceita_todos_os_prefixos_conhecidos():
    validos = [
        "saldo", "saldo cartão", "resumo", "gastos", "excluir ultimo",
        "editar ultimo 45,90", "forma add Nubank 2000", "categoria listar",
        "fixa add Aluguel 1200 dia 5", "entrada 2000 salário", "apelido Lucas",
        "vincular 44912345678", "grupo", "grupo add 44912345678", "limite cartão 3000",
    ]
    for comando in validos:
        assert ai_fallback._comando_valido(comando) is True, comando

    invalidos = ["", None, "faz um cafe", "deleta tudo", "me da um emprestimo"]
    for comando in invalidos:
        assert ai_fallback._comando_valido(comando) is False, comando


# ---------------------------------------------------------------------------
# completar_categoria_forma (24/07/2026) — "IA consiga também alocar gastos
# pelo entendimento da mensagem" (ex: "50 remédio" -> Farmácia, mesmo sem
# bater em nenhum alias de categoria).
# ---------------------------------------------------------------------------

def test_completar_nao_chama_ia_quando_os_dois_ja_foram_achados(monkeypatch):
    chamou = {"valor": False}

    def _fake_sugerir(texto, categorias, formas):
        chamou["valor"] = True
        return {}

    monkeypatch.setattr(ai_fallback, "sugerir_categoria_forma", _fake_sugerir)

    cat_atual   = _CATEGORIAS[0]
    forma_atual = _FORMAS[0]
    categoria, forma = ai_fallback.completar_categoria_forma(
        "50 mercado cartão", _CATEGORIAS, _FORMAS, cat_atual, forma_atual
    )

    assert chamou["valor"] is False
    assert categoria is cat_atual
    assert forma is forma_atual


def test_completar_preenche_categoria_faltante_via_ia(monkeypatch):
    monkeypatch.setattr(
        ai_fallback, "sugerir_categoria_forma",
        lambda texto, categorias, formas: {"categoria_sugerida": "restaurante", "forma_sugerida": None},
    )

    forma_atual = _FORMAS[0]
    categoria, forma = ai_fallback.completar_categoria_forma(
        "50 remédio no cartão", _CATEGORIAS, _FORMAS, None, forma_atual
    )

    assert categoria["id"] == 2  # Restaurante
    assert forma is forma_atual  # não muda o que já tinha sido achado por palavra-chave


def test_completar_preenche_os_dois_via_ia(monkeypatch):
    monkeypatch.setattr(
        ai_fallback, "sugerir_categoria_forma",
        lambda texto, categorias, formas: {"categoria_sugerida": "mercado", "forma_sugerida": "pix"},
    )

    categoria, forma = ai_fallback.completar_categoria_forma(
        "50 remédio", _CATEGORIAS, _FORMAS, None, None
    )

    assert categoria["id"] == 1  # Mercado
    assert forma["id"] == 11     # Pix


def test_completar_devolve_originais_se_ia_falhar(monkeypatch):
    def _explode(texto, categorias, formas):
        raise RuntimeError("timeout")

    monkeypatch.setattr(ai_fallback, "sugerir_categoria_forma", _explode)

    categoria, forma = ai_fallback.completar_categoria_forma(
        "50 remédio", _CATEGORIAS, _FORMAS, None, None
    )

    assert categoria is None
    assert forma is None
