"""
tests/test_webhook_seguranca.py — Fase 7 do PLANO_EXECUCAO.md (hardening).

Cobre só `validar_apikey`, a única função pura de services/webhook_seguranca.py
(sem banco). `verificar_e_marcar_duplicata` e `passou_rate_limit` dependem
de banco e são verificadas manualmente, mesma filosofia dos outros services.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import services.webhook_seguranca as webhook_seguranca


def test_sem_secret_configurado_aceita_qualquer_coisa(monkeypatch):
    monkeypatch.delenv("EVOLUTION_WEBHOOK_SECRET", raising=False)
    assert webhook_seguranca.validar_apikey(None) is True
    assert webhook_seguranca.validar_apikey("qualquer coisa") is True


def test_com_secret_configurado_exige_match_exato(monkeypatch):
    monkeypatch.setenv("EVOLUTION_WEBHOOK_SECRET", "segredo-123")
    assert webhook_seguranca.validar_apikey("segredo-123") is True
    assert webhook_seguranca.validar_apikey("segredo-errado") is False
    assert webhook_seguranca.validar_apikey(None) is False
    assert webhook_seguranca.validar_apikey("") is False


def test_espacos_em_volta_sao_ignorados(monkeypatch):
    monkeypatch.setenv("EVOLUTION_WEBHOOK_SECRET", "segredo-123")
    assert webhook_seguranca.validar_apikey("  segredo-123  ") is True
