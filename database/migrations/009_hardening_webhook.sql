-- 009: hardening do webhook (Fase 7 do PLANO_EXECUCAO.md)
--
-- Substitui os caches em memória do app.py (_cupons_recentes) por tabelas
-- de verdade — o cache em memória não sobrevive a restart nem funciona
-- corretamente com 2+ workers gunicorn (cada worker tem sua própria cópia
-- do dict, então 2 requisições concorrentes em workers diferentes não se
-- veem e a duplicata passa).

-- Dedup de comprovante: chave = "telefone:numero_cupom" ou "telefone:valor"
-- (mesma lógica de app.py:_e_duplicata, só que agora persistida).
CREATE TABLE IF NOT EXISTS comprovantes_processados (
    id            SERIAL PRIMARY KEY,
    chave         TEXT UNIQUE NOT NULL,
    processado_em TIMESTAMP DEFAULT NOW()
);

-- Rate limit por telefone: janela fixa de 1 minuto, reseta a contagem
-- quando a janela expira (ver services/webhook_seguranca.py).
CREATE TABLE IF NOT EXISTS rate_limit_webhook (
    telefone       TEXT PRIMARY KEY,
    janela_inicio  TIMESTAMP NOT NULL DEFAULT NOW(),
    contagem       INT NOT NULL DEFAULT 0
);
