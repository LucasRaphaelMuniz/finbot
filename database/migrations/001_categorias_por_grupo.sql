-- 001: categorias por grupo
-- Categorias deixam de ser globais únicas: cada grupo pode ter as suas.
-- grupo_id NULL = categoria padrão global (fallback para todos os grupos).

ALTER TABLE categorias ADD COLUMN IF NOT EXISTS grupo_id INT REFERENCES grupos(id) ON DELETE CASCADE;

ALTER TABLE categorias DROP CONSTRAINT IF EXISTS categorias_nome_key;

CREATE UNIQUE INDEX IF NOT EXISTS uq_categoria_grupo_nome
    ON categorias (COALESCE(grupo_id, 0), LOWER(nome));
