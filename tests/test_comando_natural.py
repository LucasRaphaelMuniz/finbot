"""
tests/test_comando_natural.py — parser.parece_comando_natural (24/07/2026).

Bug real (print do Lucas): "Adiciona a forma de pgto teste com limite de
2999" caiu no menu "Qual a forma de pagamento?", como se fosse um gasto de
R$ 2.999,00.

Segunda ocorrência da mesma classe do bug do telefone (44999999999), mas o
corte por quantidade de dígitos NÃO resolve esta: 2999 é plausível como
valor de gasto. O que denuncia que não é gasto é a ESTRUTURA da frase.

O bloco de falsos positivos é o mais importante: um gasto legítimo
classificado como comando manda a pessoa pra uma confirmação estranha em
vez de registrar. Por isso o filtro exige verbo de ação E substantivo do
domínio juntos.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from parser import parece_comando_natural


# ---------------------------------------------------------------------------
# Devem ser reconhecidos como comando (verbo de ação + substantivo do bot)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("texto", [
    # O caso exato do print
    "Adiciona a forma de pgto teste com limite de 2999",
    # O caso do print anterior (já corrigido por outro caminho, mas este
    # filtro também o pega — defesa em profundidade)
    "Adiciona a yasmin no grupo o número dela é 44999999999",
    "adiciona um membro no grupo",
    "adiciona a pessoa teste no grupo",
    "cria uma categoria chamada Pets",
    "criar categoria Assinaturas",
    "cadastra uma despesa fixa de aluguel 1200 dia 5",
    "remove a forma teste",
    "remover a categoria Pets",
    "exclui a despesa fixa do aluguel",
    "aumenta o limite do cartão pra 3000",
    "muda o limite do cartão para 5000",
    "altera meu apelido para Lucas",
    "define meu apelido como Lucas",
    "quero criar uma categoria nova",
    "lista as categorias",
    "mostra o grupo",
    "vincula a yasmin no grupo",
])
def test_reconhece_comando_em_linguagem_natural(texto):
    assert parece_comando_natural(texto) is True, texto


# ---------------------------------------------------------------------------
# NÃO podem ser confundidos com comando — são gastos/entradas legítimos.
# Falso positivo aqui = gasto do dia a dia vira confirmação estranha.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("texto", [
    "50 mercado cartão",
    "gastei 120,90 no restaurante no pix",
    "notebook 1103,04 em 12x no cartão",
    "50 remedio",
    "35 uber",
    "1500 aluguel pix",
    "paguei 200 de gasolina",
    "recebi 2000 de salario",
    "entrada 2000 salário",
    # Verbo de ação SEM substantivo do domínio: "mercado"/"cartão" são
    # nomes de categoria/forma, aparecem em gasto legítimo o tempo todo.
    "adiciona 50 no mercado",
    "coloca 80 no cartao",
    "coloca 50 no pix",
    # Substantivo do domínio SEM verbo de ação
    "qual o limite do cartão?",
    "meu grupo",
    "categoria",
    # Vazio / lixo
    "",
    "   ",
    "kkkk",
])
def test_nao_confunde_gasto_com_comando(texto):
    assert parece_comando_natural(texto) is False, texto


def test_exige_os_dois_sinais_juntos():
    """A regra central: verbo sozinho ou substantivo sozinho não bastam —
    é a combinação que é específica o suficiente pra não pegar gasto."""
    assert parece_comando_natural("adiciona") is False          # só verbo
    assert parece_comando_natural("forma de pagamento") is False  # só substantivo
    assert parece_comando_natural("adiciona uma forma") is True   # os dois


def test_insensivel_a_acento_e_caixa():
    assert parece_comando_natural("ADICIONA A CATEGORIA PETS") is True
    assert parece_comando_natural("cria a despesa fixa") is True
    assert parece_comando_natural("CRIA A DESPESA FIXA") is True


# ---------------------------------------------------------------------------
# Ligação no handler: o filtro é só um PALPITE — quem decide é a IA. Se ela
# discordar, o fluxo de gasto tem que seguir normal com o valor do regex.
# Esta é a garantia que impede o filtro de virar um novo jeito de perder
# gasto legítimo.
# ---------------------------------------------------------------------------

import handler


def test_ia_confirma_comando_desvia_do_fluxo_de_gasto(monkeypatch):
    monkeypatch.setattr(handler, "get_categorias", lambda uid: [])
    monkeypatch.setattr(handler, "get_formas_pagamento", lambda uid: [])
    monkeypatch.setattr(
        handler, "interpretar_mensagem",
        lambda msg, cats, formas: {
            "intencao": "comando",
            "comando_sugerido": "forma add teste 2999",
            "descricao_acao": "Criar a forma de pagamento teste com limite de R$ 2.999,00",
        },
    )
    monkeypatch.setattr(handler, "criar_sessao", lambda *a, **k: None)

    resposta = handler._tentar_comando_natural(1, "Adiciona a forma de pgto teste com limite de 2999")

    assert resposta is not None
    assert "forma add teste 2999" in resposta


def test_ia_discorda_devolve_none_para_seguir_como_gasto(monkeypatch):
    """Falso positivo do filtro barato: a IA olha e diz que não é comando.
    _tentar_comando_natural devolve None, e _processar_input_livre segue com
    o valor que o regex já extraiu — nenhum gasto é perdido."""
    monkeypatch.setattr(handler, "get_categorias", lambda uid: [])
    monkeypatch.setattr(handler, "get_formas_pagamento", lambda uid: [])
    monkeypatch.setattr(
        handler, "interpretar_mensagem",
        lambda msg, cats, formas: {"intencao": "gasto", "valor": 50.0},
    )

    assert handler._tentar_comando_natural(1, "adiciona uma forma 50") is None


def test_ia_indefinida_devolve_none_para_seguir_como_gasto(monkeypatch):
    monkeypatch.setattr(handler, "get_categorias", lambda uid: [])
    monkeypatch.setattr(handler, "get_formas_pagamento", lambda uid: [])
    monkeypatch.setattr(
        handler, "interpretar_mensagem",
        lambda msg, cats, formas: {"intencao": "indefinido"},
    )

    assert handler._tentar_comando_natural(1, "adiciona uma forma 50") is None


def test_pergunta_tambem_desvia(monkeypatch):
    """"como eu crio uma categoria?" tem verbo + substantivo do domínio e
    pode ter número solto — não pode virar gasto."""
    monkeypatch.setattr(handler, "get_categorias", lambda uid: [])
    monkeypatch.setattr(handler, "get_formas_pagamento", lambda uid: [])
    monkeypatch.setattr(
        handler, "interpretar_mensagem",
        lambda msg, cats, formas: {
            "intencao": "pergunta",
            "resposta": "Use *categoria add Nome*.",
        },
    )

    resposta = handler._tentar_comando_natural(1, "como eu crio uma categoria?")

    assert resposta is not None
    assert "categoria add Nome" in resposta
