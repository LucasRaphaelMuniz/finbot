-- 016: ativar/desativar categorias por grupo
--
-- Categoria customizada (grupo_id preenchido) já pertence só a um grupo —
-- flag "ativo" direto na própria linha é seguro, não vaza pra ninguém.
ALTER TABLE categorias ADD COLUMN IF NOT EXISTS ativo BOOLEAN NOT NULL DEFAULT true;

-- Categoria padrão (grupo_id NULL) é compartilhada por TODOS os grupos do
-- SaaS — não dá pra desativar direto na linha (apagaria a categoria da tela
-- de todo mundo, não só de quem clicou). Cada grupo que quiser ocultar uma
-- categoria padrão só pra si ganha uma linha aqui em vez disso.
CREATE TABLE IF NOT EXISTS categorias_ocultas (
    grupo_id     INT NOT NULL REFERENCES grupos(id) ON DELETE CASCADE,
    categoria_id INT NOT NULL REFERENCES categorias(id) ON DELETE CASCADE,
    criado_em    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (grupo_id, categoria_id)
);
