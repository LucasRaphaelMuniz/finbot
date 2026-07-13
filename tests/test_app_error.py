"""
tests/test_app_error.py — Fase 4.3 do PLANO_EXECUCAO.md.

Cobre o contrato de serialização do AppError (utils/app_error.py), que é o
formato de erro consumido pelo finbot-web inteiro (ver (app)/layout.jsx e
CompletarCadastro no front: checam `erro` como código de máquina e exibem
`mensagem` como texto). Um erro de digitação aqui quebraria silenciosamente
toda tela que depende desse contrato.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.app_error import AppError


def test_to_dict_com_codigo_explicito():
    err = AppError("Grupo não encontrado.", 404, "sem_grupo")
    assert err.to_dict() == {"erro": "sem_grupo", "mensagem": "Grupo não encontrado."}
    assert err.status_code == 404


def test_to_dict_sem_codigo_usa_generico():
    err = AppError("Algo deu errado.")
    d = err.to_dict()
    assert d["erro"] == "erro_generico"
    assert d["mensagem"] == "Algo deu errado."
    assert err.status_code == 400  # default
