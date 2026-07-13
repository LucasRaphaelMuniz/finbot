"""
tests/test_parece_gasto_ou_comando.py — Fase 7.4 do PLANO_EXECUCAO.md.

Cobre parser.parece_gasto_ou_comando, o filtro barato usado só em grupos
reais do WhatsApp antes de acionar o fallback de IA (evita 1 chamada de LLM
por mensagem de chit-chat não dirigida ao bot).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser import parece_gasto_ou_comando


def test_mensagem_com_valor_passa():
    assert parece_gasto_ou_comando("50 mercado cartão") is True


def test_mensagem_com_valor_por_extenso_passa():
    assert parece_gasto_ou_comando("gastei cinquenta reais no mercado") is True


def test_comando_ajuda_passa():
    assert parece_gasto_ou_comando("ajuda") is True


def test_comando_saldo_passa():
    assert parece_gasto_ou_comando("saldo") is True


def test_comando_categoria_passa():
    assert parece_gasto_ou_comando("categoria listar") is True


def test_chitchat_sem_valor_nem_comando_nao_passa():
    assert parece_gasto_ou_comando("bom dia pessoal, tudo bem?") is False
    assert parece_gasto_ou_comando("kkkkkk mds") is False


def test_texto_vazio_nao_passa():
    assert parece_gasto_ou_comando("") is False
    assert parece_gasto_ou_comando("   ") is False
