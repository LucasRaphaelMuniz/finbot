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
