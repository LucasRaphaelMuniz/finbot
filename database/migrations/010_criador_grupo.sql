-- 010: dono do grupo (Fase 7.5 revisada — exclusão de conta "de verdade")
--
-- Até aqui não existia distinção entre quem criou o grupo e os demais
-- membros — services/grupos.py tratava todo mundo do mesmo grupo_id como
-- igual (só checava isolamento multi-tenant, nunca "é o dono?"). A nova
-- regra de exclusão de conta (services/conta.py) exige saber quem pode
-- apagar o grupo inteiro: só quem criou.
--
-- Backfill para grupos que já existem hoje (sem essa informação salva em
-- lugar nenhum): assume que o usuário com o MENOR id de cada grupo foi
-- quem criou — critério aceito pelo Lucas em 11/07/2026, correto na
-- prática porque ids são sequenciais por ordem de cadastro.

ALTER TABLE grupos ADD COLUMN IF NOT EXISTS criador_id INT REFERENCES usuarios(id);

UPDATE grupos g
SET criador_id = sub.primeiro_usuario_id
FROM (
    SELECT DISTINCT ON (grupo_id) grupo_id, id AS primeiro_usuario_id
    FROM usuarios
    WHERE grupo_id IS NOT NULL
    ORDER BY grupo_id, id ASC
) sub
WHERE g.id = sub.grupo_id
  AND g.criador_id IS NULL;
