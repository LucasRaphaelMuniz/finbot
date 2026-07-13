"""tests/test_telefone.py — Fase A1 do AUDITORIA_E_PLANO_CADASTRO.md.
Cobre os formatos citados na docstring de utils/telefone.py + os casos que
motivaram a consolidação (F1: bot e web divergiam nesses detalhes)."""

from utils.telefone import normalizar, exibir


def test_normalizar_ddd_sem_codigo_pais_11_digitos():
    assert normalizar("44912345678") == "5544912345678@s.whatsapp.net"


def test_normalizar_ddd_sem_codigo_pais_10_digitos():
    assert normalizar("4432345678") == "554432345678@s.whatsapp.net"


def test_normalizar_com_codigo_pais():
    assert normalizar("5544912345678") == "5544912345678@s.whatsapp.net"


def test_normalizar_com_mais_formatacao():
    assert normalizar("+55 (44) 91234-5678") == "5544912345678@s.whatsapp.net"


def test_normalizar_jid_ja_pronto_passa_direto():
    assert normalizar("5544912345678@s.whatsapp.net") == "5544912345678@s.whatsapp.net"


def test_normalizar_prefixo_whatsapp_colon():
    assert normalizar("whatsapp:+5544912345678") == "5544912345678@s.whatsapp.net"


def test_normalizar_formato_antigo_sem_9_digito_insere_9():
    # 55 + DDD(44) + 8 dígitos locais já começando com 9 (indício de celular
    # em formato antigo, sem a correção de 2016) -> insere outro 9 na
    # frente, formando o local de 9 dígitos '991234567'.
    assert normalizar("554491234567") == "5544991234567@s.whatsapp.net"


def test_normalizar_formato_antigo_fixo_nao_insere_9():
    # Número fixo (8 dígitos, não começa com 9) -> mantém como está
    assert normalizar("554432345678") == "554432345678@s.whatsapp.net"


def test_normalizar_grupo_retorna_none():
    assert normalizar("120363012345678901@g.us") is None


def test_normalizar_lid_retorna_none():
    assert normalizar("123456789@lid") is None


def test_normalizar_vazio_retorna_none():
    assert normalizar("") is None
    assert normalizar(None) is None


def test_normalizar_invalido_retorna_none():
    assert normalizar("123") is None
    assert normalizar("abc") is None


def test_exibir_celular():
    assert exibir("5544912345678@s.whatsapp.net") == "+55 44 91234-5678"


def test_exibir_fixo():
    assert exibir("554432345678@s.whatsapp.net") == "+55 44 3234-5678"


def test_exibir_a_partir_de_entrada_crua():
    assert exibir("44912345678") == "+55 44 91234-5678"


def test_exibir_vazio():
    assert exibir("") == ""
    assert exibir(None) == ""


def test_exibir_entrada_invalida_devolve_original():
    assert exibir("abc") == "abc"
