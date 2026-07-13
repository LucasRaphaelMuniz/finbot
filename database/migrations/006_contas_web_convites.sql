-- 006: contas web + convites (Fase 4)
-- auth_user_id é o vínculo lógico com o Supabase Auth (não há FK real cross-schema).
-- Convite permite que um membro adicionado só pelo bot (por telefone) opcionalmente
-- crie uma conta web depois, vinculando-se ao grupo já existente.

ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS auth_user_id UUID UNIQUE;

CREATE TABLE IF NOT EXISTS convites (
    id          SERIAL PRIMARY KEY,
    grupo_id    INT REFERENCES grupos(id),
    codigo      TEXT UNIQUE NOT NULL,        -- curto, legível (ex: FIN-8K3M2P)
    criado_por  INT REFERENCES usuarios(id),
    telefone    TEXT,                        -- opcional: pré-vincula número ao gerar
    expira_em   TIMESTAMP,                   -- default aplicado na criação: NOW() + 7 dias
    usado_em    TIMESTAMP,
    usado_por   INT REFERENCES usuarios(id)
);
