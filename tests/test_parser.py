"""
Testes de tests/test_parser.py — Fase 1 do PLANO_EXECUCAO.md.

Cobrem o bug original (`_VALOR_RE` capturando '1.10' de '1.103,04') e a
normalização BR adotada em D1 (`_normalizar_numero_br`).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser import extrair_valor, extrair_forma_pagamento


def test_valor_com_milhar_e_decimal():
    # Bug original: virava 1.10 (R$ 1,10). Correto: 1103.04.
    assert extrair_valor("1.103,04") == 1103.04


def test_valor_inteiro_simples():
    assert extrair_valor("50") == 50.0


def test_valor_com_decimal_virgula():
    assert extrair_valor("50,90") == 50.9


def test_valor_com_prefixo_moeda_e_milhar():
    assert extrair_valor("R$ 1.234,56") == 1234.56


def test_valor_so_ponto_duas_casas_decimal_por_d1():
    # Caminho valor-da-IA -> texto -> parser: '1103.04' (str de float).
    assert extrair_valor("1103.04") == 1103.04


def test_valor_so_ponto_tres_digitos_e_milhar():
    assert extrair_valor("1.103") == 1103.0


def test_valor_so_ponto_um_digito_e_milhar_nao_decimal():
    # Caso que motivou o fix em app.py: '50.0' (str de 50.0) não deve virar 5.0.
    assert extrair_valor("50.0") == 500.0


def test_valor_muitos_digitos_sem_pontuacao():
    assert extrair_valor("1234567") == 1234567.0


def test_valor_milhar_multiplo_grupo():
    assert extrair_valor("1.234.567,89") == 1234567.89


def test_valor_em_frase():
    assert extrair_valor("gastei 1.103,04 no mercado") == 1103.04


def test_palavra_numerica_simples():
    assert extrair_valor("cem") == 100.0


def test_palavra_numerica_composta():
    assert extrair_valor("cento e cinquenta") == 150.0


def test_palavra_numerica_mil():
    assert extrair_valor("mil e duzentos") == 1200.0


def test_valor_nao_encontrado():
    assert extrair_valor("não tem número nenhum aqui") is None


# ---------------------------------------------------------------------------
# 24/07/2026 — telefone/CPF/CNPJ no meio da frase não pode virar "valor".
# Bug real: "adiciona a pessoa com o numero 44999999999" virava um gasto de
# R$ 44.999.999.999,00 e nunca chegava a ser classificado como comando pela
# IA (extrair_valor != None sequestra a mensagem pro fluxo de gasto antes
# do fallback de IA rodar — ver handler.py:_processar_input_livre).
# ---------------------------------------------------------------------------

def test_telefone_no_meio_da_frase_nao_vira_valor():
    assert extrair_valor("adiciona a pessoa teste com o numero 44999999999") is None


def test_cpf_no_meio_da_frase_nao_vira_valor():
    assert extrair_valor("meu cpf é 12345678901") is None


def test_cnpj_no_meio_da_frase_nao_vira_valor():
    assert extrair_valor("cnpj 12345678000199") is None


def test_valor_de_sete_digitos_ainda_e_aceito():
    # Limite exato: 7 dígitos sem separador ainda é um valor plausível
    # (R$ 1.234.567) — não pode regredir o caso já coberto por
    # test_valor_muitos_digitos_sem_pontuacao.
    assert extrair_valor("1234567") == 1234567.0


def test_valor_real_apos_numero_longo_na_mesma_frase_ainda_e_encontrado():
    # finditer (não só o 1º match): um número implausível cedo na frase não
    # pode engolir um valor de verdade que apareça depois.
    assert extrair_valor("numero 44999999999, gastei 50 reais no mercado") == 50.0


def test_valor_com_separador_grande_continua_aceito_mesmo_longo():
    # Com vírgula/ponto de verdade (intenção monetária clara), não aplica o
    # limite de dígitos — só a heurística D1 de decimal vs. milhar.
    assert extrair_valor("12.345.678,90") == 12345678.90


# ---------------------------------------------------------------------------
# 29/08/2026 — extrair_forma_pagamento: vence quem aparece PRIMEIRO NO TEXTO,
# não quem aparece primeiro na lista `formas` (que get_formas_pagamento
# devolve ordenada alfabeticamente pelo nome — ORDER BY nome em db.py).
#
# Bug real (print do Lucas): "VR 94 mercado café da manha (reembolso pix)"
# registrou como "DÉBITO/PIX" em vez de "VR" — a palavra "pix" no comentário
# entre parênteses batia com o nome "DÉBITO/PIX", e "DÉBITO..." vem antes de
# "VR" alfabeticamente, então o antigo `return` no primeiro match da lista
# escolhia errado mesmo "VR" estando antes no texto.
# ---------------------------------------------------------------------------

_FORMAS_TESTE = [
    {"id": 1, "nome": "DÉBITO/PIX"},
    {"id": 2, "nome": "VR"},
    {"id": 3, "nome": "CRÉDITO"},
]


def test_forma_pagamento_vence_quem_aparece_primeiro_no_texto():
    forma = extrair_forma_pagamento(
        "VR 94 mercado café da manha (reembolso pix)", _FORMAS_TESTE
    )
    assert forma["nome"] == "VR"


def test_forma_pagamento_pix_isolado_ainda_funciona():
    forma = extrair_forma_pagamento("50 mercado pix", _FORMAS_TESTE)
    assert forma["nome"] == "DÉBITO/PIX"


def test_forma_pagamento_sem_menção_devolve_none():
    assert extrair_forma_pagamento("50 mercado", _FORMAS_TESTE) is None
