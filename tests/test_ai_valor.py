"""
tests/test_ai_valor.py — Fase 1 do PLANO_EXECUCAO.md.

Cobre o caminho: valor (float retornado pela Vision API em ai.py)
-> texto_sintetico (app.py) -> extrair_valor (parser.py).

É o caminho onde o bug se manifestava com comprovantes: `str(float)` gera
ponto decimal nem sempre com 2 casas (ex.: 50.0 -> '50.0'), e a heurística
D1 do parser interpretava isso como separador de milhar. Não importamos o
Flask app inteiro (evita exigir DATABASE_URL/OPENAI_API_KEY reais) — só a
função de formatação e o parser, que é tudo que esse caminho exercita.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import _valor_para_texto_br
from parser import extrair_valor


def _simular_texto_sintetico(valor, descricao="", categoria="", forma="", caption=""):
    """Reproduz a montagem de `texto_sintetico` em app.py (linhas ~207-214)."""
    partes = [_valor_para_texto_br(valor), descricao, categoria, forma, caption]
    return " ".join(p for p in partes if p).strip()


def test_valor_float_inteiro_da_vision():
    # Caso que expunha o bug: 50.0 (não 50.00) vindo da Vision.
    texto = _simular_texto_sintetico(50.0, descricao="Mercado")
    assert texto.startswith("50,00")
    assert extrair_valor(texto) == 50.0


def test_valor_float_com_centavos_da_vision():
    texto = _simular_texto_sintetico(1103.04, descricao="Posto Shell")
    assert texto.startswith("1103,04")
    assert extrair_valor(texto) == 1103.04


def test_valor_float_milhar_da_vision():
    texto = _simular_texto_sintetico(1234.56, descricao="Supermercado")
    assert extrair_valor(texto) == 1234.56


def test_valor_float_arredonda_duas_casas():
    # Vision poderia (em tese) devolver mais casas por artefato de float.
    texto = _simular_texto_sintetico(73.4, descricao="Farmácia")
    assert texto.startswith("73,40")
    assert extrair_valor(texto) == 73.4
