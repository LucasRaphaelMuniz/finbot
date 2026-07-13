"""
tests/test_categorias.py — Fase 3.1 do PLANO_EXECUCAO.md.

Cobre só a parte testável sem banco: a regra de que os aliases de
`_CAT_ALIASES` (ex.: "netflix" -> Lazer) só valem para categorias globais
(grupo_id None). Categorias customizadas por grupo (services/categorias.py)
só casam por substring exato do nome ou por fuzzy match — nunca por alias
genérico que o grupo não escolheu.

Os serviços de CRUD de categoria (services/categorias.py) dependem de banco
(get_conn) e não são cobertos aqui — verificação é manual, via bot, como o
resto das regras de negócio desta fase.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser import extrair_categoria


def test_alias_casa_categoria_global():
    categorias = [{"id": 1, "nome": "Lazer", "grupo_id": None}]
    cat = extrair_categoria("assinei o netflix esse mes", categorias)
    assert cat is not None
    assert cat["nome"] == "Lazer"


def test_alias_nao_casa_categoria_customizada():
    # Mesmo nome/fragmento "lazer", mas é customizada (grupo_id preenchido):
    # o alias "netflix" não deve casar por alias — só por substring/fuzzy.
    categorias = [{"id": 2, "nome": "Lazer VIP", "grupo_id": 9}]
    cat = extrair_categoria("assinei o netflix esse mes", categorias)
    assert cat is None


def test_substring_direto_casa_customizada():
    categorias = [{"id": 3, "nome": "Assinaturas", "grupo_id": 9}]
    cat = extrair_categoria("paguei a assinaturas do mes", categorias)
    assert cat is not None
    assert cat["nome"] == "Assinaturas"


def test_categoria_sem_chave_grupo_id_tratada_como_global():
    # Compatibilidade: dicts antigos sem a chave grupo_id (ex.: fixtures
    # que ainda não foram atualizadas) continuam se comportando como globais.
    categorias = [{"id": 4, "nome": "Combustível"}]
    cat = extrair_categoria("abasteci o carro", categorias)
    assert cat is not None
    assert cat["nome"] == "Combustível"


def test_global_e_customizada_juntas_prioriza_substring():
    categorias = [
        {"id": 1, "nome": "Lazer", "grupo_id": None},
        {"id": 5, "nome": "Presentes", "grupo_id": 9},
    ]
    cat = extrair_categoria("comprei um presentes de aniversario", categorias)
    assert cat is not None
    assert cat["nome"] == "Presentes"
