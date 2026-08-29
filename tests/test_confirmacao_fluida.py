"""
tests/test_confirmacao_fluida.py — três estados na confirmação (24/07/2026).

Pedido do Lucas: "faça de forma que a utilização do usuário seja fluida".

O comportamento antigo era binário: afirmativo exato executa, TODO o resto
cancela. Este arquivo trava o comportamento novo — afirmativo executa,
negativo cancela, e ambíguo PRESERVA a sessão perguntando de novo (o caso
que antes fazia a pessoa perder o registro por responder "ok").

Banco e sessão são mockados; o que está sob teste é só a árvore de decisão
de handler.py, não persistência.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import handler


@pytest.fixture
def sessao_mock(monkeypatch):
    """Captura se deletar_sessao foi chamada — é o sinal observável de
    'a sessão foi encerrada' (executou ou cancelou) vs 'foi preservada'
    (perguntou de novo)."""
    estado = {"deletada": False}
    monkeypatch.setattr(handler, "deletar_sessao", lambda uid: estado.__setitem__("deletada", True))
    return estado


# ---------------------------------------------------------------------------
# Confirmação de COMANDO (grupo add, forma add, ...) — a de maior risco:
# altera grupo/membros/formas, e desfazer é caro.
# ---------------------------------------------------------------------------

_SESSAO_COMANDO = {
    "etapa": "aguardando_confirmacao_comando",
    "dados_temp": {"comando_sugerido": "grupo add 44912345678"},
}


def test_comando_afirmativo_executa(monkeypatch, sessao_mock):
    executados = []
    monkeypatch.setattr(
        handler, "_despachar_comando",
        lambda uid, cmd: executados.append(cmd) or "✅ adicionado!",
    )
    monkeypatch.setattr(handler, "get_dados_temp", lambda s: s["dados_temp"])

    resposta = handler._processar_confirmacao_comando(1, _SESSAO_COMANDO, "pode")

    assert executados == ["grupo add 44912345678"]
    assert resposta == "✅ adicionado!"
    assert sessao_mock["deletada"] is True


def test_comando_negativo_cancela_sem_executar(monkeypatch, sessao_mock):
    executados = []
    monkeypatch.setattr(
        handler, "_despachar_comando",
        lambda uid, cmd: executados.append(cmd) or "não deveria executar",
    )
    monkeypatch.setattr(handler, "get_dados_temp", lambda s: s["dados_temp"])

    resposta = handler._processar_confirmacao_comando(1, _SESSAO_COMANDO, "não")

    assert executados == []
    assert "nada foi executado" in resposta.lower()
    assert sessao_mock["deletada"] is True


def test_comando_ambiguo_chama_ia_e_devolve_lembrete_sem_executar(monkeypatch, sessao_mock):
    """Revisão de 29/08/2026 do comportamento de 24/07 (ver
    handler.py:_fora_do_esperado para o histórico completo da decisão):
    resposta ambígua NUNCA mais fica em silêncio — a IA é chamada pra
    decidir, e só devolve "" pra ruído óbvio (parser.parece_ruido). Uma
    frase real como "e aí, quanto ficou?" não é ruído, então cai na IA; se
    a IA não reconhecer nada (indefinido), o bot devolve um lembrete em vez
    de silêncio, e a sessão continua VIVA (a pessoa ainda pode responder
    *sim* depois, timeout de 5 min encerra sozinho)."""
    executados = []
    monkeypatch.setattr(
        handler, "_despachar_comando",
        lambda uid, cmd: executados.append(cmd) or "não deveria executar",
    )
    monkeypatch.setattr(handler, "get_dados_temp", lambda s: s["dados_temp"])
    monkeypatch.setattr(handler, "get_categorias", lambda uid: [])
    monkeypatch.setattr(handler, "get_formas_pagamento", lambda uid: [])
    monkeypatch.setattr(
        handler, "interpretar_mensagem",
        lambda texto, categorias, formas: {"intencao": "indefinido"},
    )

    resposta = handler._processar_confirmacao_comando(1, _SESSAO_COMANDO, "e aí, quanto ficou?")

    assert executados == []
    assert resposta != ""                    # nunca mais silêncio
    assert sessao_mock["deletada"] is False  # sessão VIVA


def test_comando_novo_durante_confirmacao_abandona_e_processa(monkeypatch, sessao_mock):
    """O buraco de "ignorar sempre" (aconteceu no print do Lucas): mandar
    um COMANDO NOVO com pergunta em aberto não pode sumir no silêncio —
    senão a pessoa digita duas vezes sem saber por quê."""
    despachados = []

    def _fake_despachar(uid, cmd):
        despachados.append(cmd)
        # 1ª chamada = o comando pendente (não deve acontecer aqui);
        # a que interessa é o comando NOVO que a pessoa acabou de mandar.
        return "📊 saldo aqui"

    monkeypatch.setattr(handler, "_despachar_comando", _fake_despachar)
    monkeypatch.setattr(handler, "get_dados_temp", lambda s: s["dados_temp"])

    resposta = handler._processar_confirmacao_comando(1, _SESSAO_COMANDO, "saldo")

    assert despachados == ["saldo"]          # o NOVO, não "grupo add ..."
    assert resposta == "📊 saldo aqui"
    assert sessao_mock["deletada"] is True   # sessão abandonada


@pytest.mark.parametrize("resposta_usuario", ["sim", "ok", "pode", "isso", "blz", "👍", "manda"])
def test_comando_aceita_variacoes_de_sim(monkeypatch, sessao_mock, resposta_usuario):
    """Regressão do atrito original: antes só 4 strings exatas executavam."""
    executados = []
    monkeypatch.setattr(
        handler, "_despachar_comando",
        lambda uid, cmd: executados.append(cmd) or "✅ ok",
    )
    monkeypatch.setattr(handler, "get_dados_temp", lambda s: s["dados_temp"])

    handler._processar_confirmacao_comando(1, _SESSAO_COMANDO, resposta_usuario)

    assert executados == ["grupo add 44912345678"], resposta_usuario


def test_comando_invalido_no_despacho_nao_trava_usuario(monkeypatch, sessao_mock):
    """Salvaguarda: prefixo passou na validação de ai_fallback mas a sintaxe
    completa não bate em nada — não pode devolver None pro webhook."""
    monkeypatch.setattr(handler, "_despachar_comando", lambda uid, cmd: None)
    monkeypatch.setattr(handler, "get_dados_temp", lambda s: s["dados_temp"])

    resposta = handler._processar_confirmacao_comando(1, _SESSAO_COMANDO, "sim")

    assert "não consegui executar" in resposta.lower()
    assert sessao_mock["deletada"] is True


# ---------------------------------------------------------------------------
# Confirmação de GASTO deduzido pela IA (valor incerto — por isso confirma)
# ---------------------------------------------------------------------------

_SESSAO_GASTO = {
    "etapa": "aguardando_confirmacao_ia",
    "valor_temp": 50.0,
    "categoria_temp": 1,
    "forma_temp": 10,
    "dados_temp": {"descricao": "remedio", "parcelas": None},
}


def test_gasto_negativo_cancela(monkeypatch, sessao_mock):
    registrados = []
    monkeypatch.setattr(
        handler, "_registrar_e_confirmar",
        lambda *a, **k: registrados.append(a) or "não deveria registrar",
    )
    monkeypatch.setattr(handler, "get_dados_temp", lambda s: s["dados_temp"])

    resposta = handler._processar_confirmacao_ia(1, _SESSAO_GASTO, "nao")

    assert registrados == []
    assert "nada foi registrado" in resposta.lower()
    assert sessao_mock["deletada"] is True


def test_gasto_ruido_puro_ainda_fica_em_silencio(monkeypatch, sessao_mock):
    """"kkkk" sozinho continua sendo o único caso que não gasta 1 chamada
    de LLM (parser.parece_ruido) — ver test_comando_ambiguo_chama_ia_... pro
    caso de mensagem ambígua com conteúdo real, que agora chama a IA."""
    registrados = []
    monkeypatch.setattr(
        handler, "_registrar_e_confirmar",
        lambda *a, **k: registrados.append(a) or "não deveria registrar",
    )
    monkeypatch.setattr(handler, "get_dados_temp", lambda s: s["dados_temp"])

    resposta = handler._processar_confirmacao_ia(1, _SESSAO_GASTO, "kkkk")

    assert registrados == []
    assert resposta == ""
    assert sessao_mock["deletada"] is False


def test_gasto_ambiguo_com_conteudo_chama_ia_e_devolve_lembrete(monkeypatch, sessao_mock):
    registrados = []
    monkeypatch.setattr(
        handler, "_registrar_e_confirmar",
        lambda *a, **k: registrados.append(a) or "não deveria registrar",
    )
    monkeypatch.setattr(handler, "get_dados_temp", lambda s: s["dados_temp"])
    monkeypatch.setattr(handler, "get_categorias", lambda uid: [])
    monkeypatch.setattr(handler, "get_formas_pagamento", lambda uid: [])
    monkeypatch.setattr(
        handler, "interpretar_mensagem",
        lambda texto, categorias, formas: {"intencao": "indefinido"},
    )

    resposta = handler._processar_confirmacao_ia(1, _SESSAO_GASTO, "e aí, quanto ficou?")

    assert registrados == []
    assert resposta != ""
    assert sessao_mock["deletada"] is False


def test_gasto_afirmativo_registra(monkeypatch, sessao_mock):
    registrados = []
    monkeypatch.setattr(handler, "get_dados_temp", lambda s: s["dados_temp"])
    monkeypatch.setattr(handler, "get_categorias", lambda uid: [{"id": 1, "nome": "Farmácia"}])
    monkeypatch.setattr(handler, "get_formas_pagamento", lambda uid: [{"id": 10, "nome": "Cartão"}])
    monkeypatch.setattr(
        handler, "_registrar_e_confirmar",
        lambda uid, forma, cat, valor, desc, **k: registrados.append((valor, cat["nome"], forma["nome"])) or "✅ ok",
    )

    resposta = handler._processar_confirmacao_ia(1, _SESSAO_GASTO, "isso mesmo")

    assert registrados == [(50.0, "Farmácia", "Cartão")]
    assert resposta == "✅ ok"
    assert sessao_mock["deletada"] is True


# ---------------------------------------------------------------------------
# _parece_nova_intencao — decide entre ficar em silêncio e abandonar a
# pergunta pendente. Conservador de propósito: na dúvida, silêncio (que
# preserva a sessão) em vez de descartar um registro em andamento.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("texto", [
    "saldo", "resumo", "gastos", "ajuda",
    "saldo cartão", "forma add Nubank 2000", "categoria listar",
    "fixa listar", "grupo", "grupo add 44912345678", "limite cartão 3000",
    "excluir ultimo", "editar ultimo 45,90", "apelido Lucas",
    # linguagem natural (parece_comando_natural)
    "Adiciona a forma de pgto teste com limite de 2999",
    "cria uma categoria chamada Pets",
])
def test_reconhece_nova_intencao(texto):
    assert handler._parece_nova_intencao(texto) is True, texto


@pytest.mark.parametrize("texto", [
    "",
    "   ",
    "1",            # resposta a menu numerado — NÃO é intenção nova
    "3",
    "kkkk",
    "hmm",
    "deixa eu ver",
    "quanto ficou?",
    "ta",
    "50",           # número solto dentro de um menu é escolha, não gasto novo
])
def test_nao_confunde_ruido_com_nova_intencao(texto):
    assert handler._parece_nova_intencao(texto) is False, texto


def test_fora_do_esperado_ruido_fica_em_silencio_sem_apagar_sessao(monkeypatch, sessao_mock):
    assert handler._fora_do_esperado(1, "kkkk") == ""
    assert sessao_mock["deletada"] is False


def test_fora_do_esperado_gasto_novo_cai_no_input_livre(monkeypatch, sessao_mock):
    """Comando natural que não bate em _despachar_comando (devolve None)
    tem que seguir pro fluxo de gasto, não sumir."""
    monkeypatch.setattr(handler, "_despachar_comando", lambda uid, m: None)
    monkeypatch.setattr(handler, "_processar_input_livre", lambda uid, m: "✅ registrado")

    resposta = handler._fora_do_esperado(1, "cria uma categoria chamada Pets")

    assert resposta == "✅ registrado"
    assert sessao_mock["deletada"] is True


def test_fora_do_esperado_indefinido_devolve_lembrete_sem_silencio(monkeypatch, sessao_mock):
    """29/08/2026: mensagem que não é ruído nem intenção reconhecida pela
    IA nunca mais fica muda — devolve um lembrete e preserva a sessão."""
    monkeypatch.setattr(handler, "get_categorias", lambda uid: [])
    monkeypatch.setattr(handler, "get_formas_pagamento", lambda uid: [])
    monkeypatch.setattr(
        handler, "interpretar_mensagem",
        lambda texto, categorias, formas: {"intencao": "indefinido"},
    )

    resposta = handler._fora_do_esperado(1, "e aí, quanto ficou?")

    assert resposta != ""
    assert sessao_mock["deletada"] is False


def test_fora_do_esperado_ia_reconhece_intencao_abandona_sessao(monkeypatch, sessao_mock):
    """Caso real que motivou a mudança (print do Lucas): "qual foi o último
    dia que abasteci o carro?" com uma sessão pendente não pode sumir — a
    IA reconhece 'consulta_dados' e o bot responde com o dado, abandonando
    a pergunta pendente (mesmo raciocínio de intenção nova já existente)."""
    categoria = {"id": 7, "nome": "Combustível"}
    monkeypatch.setattr(handler, "get_categorias", lambda uid: [categoria])
    monkeypatch.setattr(handler, "get_formas_pagamento", lambda uid: [])
    monkeypatch.setattr(
        handler, "interpretar_mensagem",
        lambda texto, categorias, formas: {"intencao": "consulta_dados", "categoria": categoria},
    )
    monkeypatch.setattr(
        handler, "get_ultimo_gasto_por_categoria",
        lambda uid, categoria_id: {"valor": 94.0, "data": "2026-08-20", "categoria_nome": "Combustível"},
    )

    resposta = handler._fora_do_esperado(1, "qual foi o último dia que abasteci o carro?")

    assert "Combustível" in resposta
    assert sessao_mock["deletada"] is True
