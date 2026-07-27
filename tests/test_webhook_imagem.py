"""
tests/test_webhook_imagem.py — comportamento de /webhook para imageMessage
em grupo SEM legenda (mudança de 24/07/2026, ver app.py).

Antes: imagem sem legenda em grupo era descartada ANTES de chamar a Vision
(nenhuma chance de virar gasto, mesmo sendo comprovante de verdade — era
exatamente o caso do Lucas: nota fiscal solta no grupo "Despesas Casa").

Depois: sempre chama a Vision; só fica calado se ela não achar valor
(provável papo/meme) — com legenda ou em 1:1, sempre responde.

Tudo que toca banco (get_or_create_usuario, categorias, duplicata, rate
limit) e rede (Evolution, Vision) é mockado — este teste valida só a
lógica de decisão em app.py, não integração de verdade.
"""

import app as app_module


PAYLOAD_BASE = {
    "event": "messages.upsert",
    "data": {
        "key": {
            "remoteJid": "120363012345678901@g.us",
            "fromMe": False,
            "participantAlt": "5544912345678@s.whatsapp.net",
        },
        "message": {
            "imageMessage": {
                "mimetype": "image/jpeg",
                "caption": "",
            }
        },
    },
}


def _payload(caption=""):
    import copy
    p = copy.deepcopy(PAYLOAD_BASE)
    p["data"]["message"]["imageMessage"]["caption"] = caption
    return p


def _stub_infra(monkeypatch, dados_vision, lanca=None):
    """Troca tudo que toca banco/rede por dublês; captura a mensagem
    enviada (se houver) numa lista pra o teste inspecionar."""
    enviados = []

    monkeypatch.setattr(app_module, "validar_apikey", lambda header: True)
    monkeypatch.setattr(app_module, "passou_rate_limit", lambda telefone: True)
    monkeypatch.setattr(app_module, "baixar_midia", lambda data: b"fake-bytes")
    monkeypatch.setattr(
        app_module, "get_or_create_usuario",
        lambda telefone: ({"id": 1}, False),
    )
    monkeypatch.setattr(app_module, "get_categorias_usuario", lambda uid: [])
    monkeypatch.setattr(
        app_module, "verificar_e_marcar_duplicata",
        lambda telefone, valor, numero_cupom: False,
    )

    if lanca:
        def _analisar(*a, **k):
            raise lanca
        monkeypatch.setattr(app_module, "analisar_comprovante", _analisar)
    else:
        monkeypatch.setattr(app_module, "analisar_comprovante", lambda *a, **k: dados_vision)

    monkeypatch.setattr(
        app_module, "processar_mensagem",
        lambda telefone, texto: "✅ Gasto registrado.",
    )
    monkeypatch.setattr(
        app_module, "enviar_mensagem",
        lambda jid, texto: enviados.append(texto),
    )
    return enviados


def test_grupo_sem_legenda_com_valor_reconhecido_registra_e_responde(monkeypatch):
    """O caso do Lucas: nota fiscal solta no grupo, sem legenda. Antes
    nem chegava a chamar a Vision; agora deve processar e responder."""
    enviados = _stub_infra(
        monkeypatch,
        dados_vision={"valor": 77.98, "descricao": "farmácia", "categoria_sugerida": "Saúde",
                      "forma_pagamento": "cartão", "numero_cupom": "123"},
    )
    client = app_module.app.test_client()

    resp = client.post("/webhook", json=_payload(caption=""))

    assert resp.status_code == 200
    assert len(enviados) == 1
    assert "Comprovante lido pela IA" in enviados[0]


def test_grupo_sem_legenda_sem_valor_fica_calado(monkeypatch):
    """Foto solta que a Vision não reconhece como comprovante (provável
    meme/papo do grupo) — não deve virar spam de 'não consegui ler'."""
    enviados = _stub_infra(monkeypatch, dados_vision={"valor": None})
    client = app_module.app.test_client()

    resp = client.post("/webhook", json=_payload(caption=""))

    assert resp.status_code == 200
    assert enviados == []


def test_grupo_com_legenda_sem_valor_ainda_avisa(monkeypatch):
    """Legenda é sinal explícito de intenção — mesmo sem achar valor,
    continua respondendo (comportamento já existente, não deve regredir)."""
    enviados = _stub_infra(monkeypatch, dados_vision={"valor": None})
    client = app_module.app.test_client()

    resp = client.post("/webhook", json=_payload(caption="oi"))

    assert resp.status_code == 200
    assert len(enviados) == 1
    assert "Não consegui identificar" in enviados[0]


def test_grupo_sem_legenda_erro_na_vision_fica_calado(monkeypatch):
    """Exceção na Vision (ex: API fora do ar) numa foto solta sem legenda
    também não deve virar alarde pro grupo inteiro."""
    enviados = _stub_infra(monkeypatch, dados_vision=None, lanca=RuntimeError("boom"))
    client = app_module.app.test_client()

    resp = client.post("/webhook", json=_payload(caption=""))

    assert resp.status_code == 200
    assert enviados == []


def test_direto_1a1_sem_valor_sempre_avisa(monkeypatch):
    """Fora de grupo, o filtro nunca se aplicou — continua sempre
    respondendo, com ou sem valor reconhecido."""
    enviados = _stub_infra(monkeypatch, dados_vision={"valor": None})
    client = app_module.app.test_client()

    payload = _payload(caption="")
    payload["data"]["key"] = {
        "remoteJid": "5544912345678@s.whatsapp.net",
        "fromMe": False,
    }

    resp = client.post("/webhook", json=payload)

    assert resp.status_code == 200
    assert len(enviados) == 1
    assert "Não consegui identificar" in enviados[0]
