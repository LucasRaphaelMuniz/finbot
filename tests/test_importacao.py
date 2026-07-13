"""
tests/test_importacao.py — Fase 5.3 do PLANO_EXECUCAO.md.

Cobre só a parte determinística/pura de services/importacao.py: parse de
CSV (normalizar_data_importacao, normalizar_valor_importacao, parsear_csv).
A extração via PDF+IA (extrair_linhas_pdf) e a gravação em banco
(confirmar_importacao/remover_importacao) não são cobertas aqui — mesma
filosofia dos outros services (lógica pura tem teste automatizado, IA/banco
é verificado manualmente, e no caso da IA de fatura, nem manualmente ainda
foi — ver aviso em ai.py:extrair_lancamentos_fatura).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.importacao import (
    normalizar_data_importacao,
    normalizar_valor_importacao,
    parsear_csv,
)


# --- normalizar_data_importacao ---------------------------------------------

def test_data_formato_br_barra():
    assert normalizar_data_importacao("15/07/2026") == "2026-07-15"


def test_data_formato_iso():
    assert normalizar_data_importacao("2026-07-15") == "2026-07-15"


def test_data_formato_br_traco():
    assert normalizar_data_importacao("15-07-2026") == "2026-07-15"


def test_data_ano_2_digitos():
    assert normalizar_data_importacao("15/07/26") == "2026-07-15"


def test_data_invalida_retorna_none():
    assert normalizar_data_importacao("não é uma data") is None
    assert normalizar_data_importacao("") is None


# --- normalizar_valor_importacao --------------------------------------------

def test_valor_formato_br():
    assert normalizar_valor_importacao("1.234,56") == 1234.56


def test_valor_formato_us():
    assert normalizar_valor_importacao("1234.56") == 1234.56


def test_valor_com_prefixo_moeda():
    assert normalizar_valor_importacao("R$ 50,00") == 50.0


def test_valor_negativo_com_sinal():
    assert normalizar_valor_importacao("-50,00") == -50.0


def test_valor_negativo_com_parenteses():
    assert normalizar_valor_importacao("(50,00)") == -50.0


def test_valor_invalido_retorna_none():
    assert normalizar_valor_importacao("abc") is None
    assert normalizar_valor_importacao("") is None


# --- parsear_csv --------------------------------------------------------

def test_csv_basico_virgula_utf8():
    conteudo = "data,descricao,valor\n15/07/2026,Mercado,150,90\n".encode("utf-8")
    # nota: "150,90" tem vírgula decimal só no VALOR — CSV com vírgula como
    # separador de coluna E decimal ao mesmo tempo é ambíguo por natureza;
    # este teste usa formato sem essa colisão (ver teste com ';' abaixo).
    conteudo = "data,descricao,valor\n15/07/2026,Mercado,150.90\n".encode("utf-8")
    linhas = parsear_csv(conteudo)
    assert linhas == [
        {"data": "2026-07-15", "descricao": "Mercado", "valor": 150.90, "categoria_sugerida": None}
    ]


def test_csv_separador_ponto_e_virgula_decimal_br():
    conteudo = "data;descricao;valor\n15/07/2026;Restaurante;89,90\n".encode("utf-8")
    linhas = parsear_csv(conteudo)
    assert linhas == [
        {"data": "2026-07-15", "descricao": "Restaurante", "valor": 89.90, "categoria_sugerida": None}
    ]


def test_csv_colunas_em_ingles():
    conteudo = "date,description,amount\n2026-07-15,Groceries,150.90\n".encode("utf-8")
    linhas = parsear_csv(conteudo)
    assert len(linhas) == 1
    assert linhas[0]["valor"] == 150.90


def test_csv_encoding_latin1():
    conteudo = "data;descricao;valor\n15/07/2026;Padaria São José;12,50\n".encode("latin-1")
    linhas = parsear_csv(conteudo)
    assert linhas[0]["descricao"] == "Padaria São José"


def test_csv_linha_invalida_e_descartada_silenciosamente():
    conteudo = (
        "data;descricao;valor\n"
        "15/07/2026;Mercado;100,00\n"
        ";;\n"  # linha vazia — sem data nem valor válidos
        "16/07/2026;Farmácia;40,00\n"
    ).encode("utf-8")
    linhas = parsear_csv(conteudo)
    assert len(linhas) == 2


def test_csv_sem_colunas_esperadas_levanta_erro():
    from utils.app_error import AppError
    conteudo = "coluna_a,coluna_b\n1,2\n".encode("utf-8")
    try:
        parsear_csv(conteudo)
        assert False, "deveria ter levantado AppError"
    except AppError as e:
        assert e.codigo == "csv_colunas_nao_encontradas"
