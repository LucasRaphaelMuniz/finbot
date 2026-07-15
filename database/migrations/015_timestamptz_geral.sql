-- 015: converte para TIMESTAMPTZ as demais colunas de instante comparadas
-- com datetimes UTC-aware no Python — mesma classe de bug da 014.
--
-- Vistos em produção (15/07/2026):
--   - rate_limit_webhook.janela_inicio: services/webhook_seguranca.py:94
--     compara com datetime.now(timezone.utc) e explodia com "can't compare
--     offset-naive and offset-aware datetimes" — TODA mensagem do bot
--     morria no rate limit a partir da 2ª na janela.
-- Latentes (mesma comparação em Python, ainda sem tráfego que disparasse):
--   - convites.expira_em: services/convites.py:110
--   - comprovantes_processados.processado_em: comparado em SQL (funciona
--     por cast implícito), convertido junto por consistência.
--
-- Mesmo racional da 014: valores existentes foram gravados em UTC
-- (NOW() com timezone da sessão UTC no Supabase), só falta declarar.

ALTER TABLE rate_limit_webhook
    ALTER COLUMN janela_inicio TYPE TIMESTAMPTZ USING janela_inicio AT TIME ZONE 'UTC';

ALTER TABLE comprovantes_processados
    ALTER COLUMN processado_em TYPE TIMESTAMPTZ USING processado_em AT TIME ZONE 'UTC';

ALTER TABLE convites
    ALTER COLUMN expira_em TYPE TIMESTAMPTZ USING expira_em AT TIME ZONE 'UTC',
    ALTER COLUMN usado_em  TYPE TIMESTAMPTZ USING usado_em  AT TIME ZONE 'UTC';
