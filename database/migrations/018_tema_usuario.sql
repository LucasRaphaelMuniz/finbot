-- 018: tema (dark/light) salvo por conta, não por navegador
-- Segue o mesmo padrão de tutorial_web_visto_em (migração 013): flag no
-- próprio usuário, consultada por GET /api/conta/eu.
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS tema TEXT NOT NULL DEFAULT 'dark'
    CHECK (tema IN ('dark', 'light'));
