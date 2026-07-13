"""tests/test_verificacao.py — Fase B5 do AUDITORIA_E_PLANO_CADASTRO.md.

services/verificacao.py é majoritariamente DB-dependente (grava/lê
verificacoes_telefone, chama Evolution API) — mesma filosofia de teste já
aplicada ao resto do projeto (DB-dependente não é unit-testado aqui, só
reasoned about/documentado). O único pedaço puro é `_gerar_codigo`, testado
abaixo: formato de 6 dígitos, sempre string, sem depender de banco/rede."""

import re

from services.verificacao import _gerar_codigo


def test_gerar_codigo_tem_6_digitos():
    codigo = _gerar_codigo()
    assert re.fullmatch(r"\d{6}", codigo)


def test_gerar_codigo_eh_string():
    assert isinstance(_gerar_codigo(), str)


def test_gerar_codigo_varia_entre_chamadas():
    # secrets.randbelow é aleatório — não há garantia matemática de que duas
    # chamadas nunca coincidam, mas gerar 50 códigos e achar pelo menos 2
    # valores distintos é uma checagem de sanidade suficiente (a chance de
    # todos os 50 saírem idênticos com uma faixa de 1 milhão é desprezível).
    codigos = {_gerar_codigo() for _ in range(50)}
    assert len(codigos) > 1


def test_gerar_codigo_aceita_zeros_a_esquerda():
    # f"{n:06d}" preserva zeros à esquerda (ex: 42 -> "000042") — garante que
    # o código sempre tem exatamente 6 caracteres, nunca "42" cru.
    codigos = [_gerar_codigo() for _ in range(200)]
    assert all(len(c) == 6 for c in codigos)
