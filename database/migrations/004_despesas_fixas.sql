-- 004: despesas fixas
-- Lançador idempotente (Fase 3.3) depende do índice único abaixo para nunca
-- duplicar o lançamento de uma despesa fixa no mesmo mês.

CREATE TABLE IF NOT EXISTS despesas_fixas (
    id                 SERIAL PRIMARY KEY,
    grupo_id           INT REFERENCES grupos(id),
    usuario_id         INT REFERENCES usuarios(id),
    categoria_id       INT REFERENCES categorias(id),
    forma_pagamento_id INT REFERENCES formas_pagamento(id),
    descricao          TEXT NOT NULL,
    valor              DECIMAL NOT NULL,
    dia_lancamento     SMALLINT NOT NULL CHECK (dia_lancamento BETWEEN 1 AND 31),
    ativa              BOOLEAN DEFAULT TRUE
);

ALTER TABLE gastos ADD COLUMN IF NOT EXISTS despesa_fixa_id INT REFERENCES despesas_fixas(id);

-- Trava anti-duplicação: no máximo 1 lançamento por despesa fixa por mês de competência.
--
-- Cast explícito pra ::timestamp (sem fuso) na expressão do índice: sem ele,
-- o Postgres resolve DATE_TRUNC('month', competencia) pra sobrecarga que
-- recebe timestamptz (dependente do fuso da sessão) em vez da que recebe
-- timestamp puro — e essa versão é STABLE, não IMMUTABLE, o que Postgres
-- rejeita em expressão de índice ("functions in index expression must be
-- marked IMMUTABLE"). Com o cast, a sobrecarga escolhida é a IMMUTABLE.
CREATE UNIQUE INDEX IF NOT EXISTS uq_despesa_fixa_mes
    ON gastos (despesa_fixa_id, DATE_TRUNC('month', competencia::timestamp))
    WHERE despesa_fixa_id IS NOT NULL;
