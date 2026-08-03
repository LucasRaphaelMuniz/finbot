"""
tests/test_limpar_descricao.py — descrição limpa (03/08/2026, pedido do Lucas).

Antes, o gasto reconhecido direto por palavra-chave (valor+categoria+forma
no fluxo automático de handler.py:_processar_input_livre) gravava a
MENSAGEM INTEIRA como descrição — a tabela de Lançamentos mostrava
"200 Eloá pix berço portatil" na coluna Descrição, duplicando o que
Categoria/Forma/Valor já mostram. `limpar_descricao` tira o que já foi
reconhecido; sobra só a descrição de verdade.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser import limpar_descricao


_CATEGORIA_ELOA = {"id": 1, "nome": "Eloá", "grupo_id": 5}  # customizada
_CATEGORIA_RESTAURANTE = {"id": 2, "nome": "Restaurante", "grupo_id": None}  # global
_CATEGORIA_OUTROS = {"id": 3, "nome": "Outros", "grupo_id": None}

_FORMA_DEBITO_PIX = {"id": 10, "nome": "DÉBITO/PIX"}
_FORMA_CREDITO = {"id": 11, "nome": "CRÉDITO"}


def test_categoria_customizada_e_forma_por_alias():
    # Caso exato do print do Lucas.
    resultado = limpar_descricao(
        "200 Eloá pix berço portatil", 200.0, _CATEGORIA_ELOA, _FORMA_DEBITO_PIX
    )
    assert resultado == "berço portatil"


def test_categoria_por_nome_e_forma_por_alias_credito():
    resultado = limpar_descricao(
        "restaurante 28,78 credito japones almoço de sexta",
        28.78, _CATEGORIA_RESTAURANTE, _FORMA_CREDITO,
    )
    assert resultado == "japones almoço de sexta"


def test_mensagem_inteira_consumida_vira_descricao_vazia():
    # "restaurante 9,20 pix" — nada sobra depois de tirar categoria/valor/forma.
    resultado = limpar_descricao(
        "restaurante 9,20 pix", 9.20, _CATEGORIA_RESTAURANTE, _FORMA_DEBITO_PIX
    )
    assert resultado == ""


def test_sem_categoria_ou_forma_so_tira_o_valor():
    resultado = limpar_descricao("100 combustivel posto shell", 100.0, None, None)
    assert resultado == "combustivel posto shell"


def test_categoria_generica_outros_ainda_remove_o_alias():
    resultado = limpar_descricao(
        "outros 3,39 credito", 3.39, _CATEGORIA_OUTROS, _FORMA_CREDITO
    )
    assert resultado == ""


def test_texto_vazio_devolve_vazio():
    assert limpar_descricao("", None, None, None) == ""
