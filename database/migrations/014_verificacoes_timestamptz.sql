-- 014: converte as colunas de instante de verificacoes_telefone para
-- TIMESTAMPTZ.
--
-- Por quê: a 012 criou criado_em/expira_em/verificado_em como TIMESTAMP
-- (sem fuso), mas services/verificacao.py trabalha inteiro em
-- datetime.now(timezone.utc) (com fuso). O Postgres aceita gravar um
-- timestamptz numa coluna timestamp (converte pela timezone da sessão),
-- porém devolve naive na leitura — e aí `expira_em < agora` explode com
-- "can't compare offset-naive and offset-aware datetimes" (visto em
-- produção em 15/07/2026, rota /api/verificacao/confirmar).
--
-- Corrigir no schema (e não com .replace(tzinfo=...) no Python) elimina a
-- classe inteira do bug: TIMESTAMPTZ sempre volta aware, qualquer
-- comparação futura com datetimes UTC do Python já funciona.
--
-- USING ... AT TIME ZONE 'UTC': os valores existentes foram gravados por
-- sessões em UTC (Supabase default + psycopg enviando UTC), então o
-- horário armazenado JÁ É UTC — só falta declarar isso.

ALTER TABLE verificacoes_telefone
    ALTER COLUMN criado_em     TYPE TIMESTAMPTZ USING criado_em     AT TIME ZONE 'UTC',
    ALTER COLUMN expira_em     TYPE TIMESTAMPTZ USING expira_em     AT TIME ZONE 'UTC',
    ALTER COLUMN verificado_em TYPE TIMESTAMPTZ USING verificado_em AT TIME ZONE 'UTC';
