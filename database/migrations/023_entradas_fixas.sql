-- 023: entradas fixas/recorrentes (pedido do Lucas em 18/07/2026 — salário
-- cai todo mês, não faz sentido digitar de novo).
--
-- Espelho de despesas_fixas (004): tabela-modelo + lançador mensal
-- idempotente. Um boolean em `entradas` não bastaria — a linha da entrada
-- é UMA ocorrência; pra "cair todo mês" precisa de um modelo que o
-- lançador consulta (services/entradas_fixas.py, mesmo ciclo diário do
-- app.py que lança despesas fixas).
--
-- Diferenças conscientes vs despesas_fixas: sem categoria_id nem
-- forma_pagamento_id (entrada não tem — decisão da Fase 3.5/G1), sem
-- competência (entrada usa `data`; salário não tem fatura), sem
-- valor_pendente (reajuste "só mês que vem" pra salário não teve demanda —
-- se surgir, copiar o padrão da migração 017).

CREATE TABLE IF NOT EXISTS entradas_fixas (
    id             SERIAL PRIMARY KEY,
    grupo_id       INT REFERENCES grupos(id),
    usuario_id     INT REFERENCES usuarios(id),
    descricao      TEXT NOT NULL,
    valor          DECIMAL NOT NULL,
    dia_lancamento SMALLINT NOT NULL CHECK (dia_lancamento BETWEEN 1 AND 31),
    ativa          BOOLEAN DEFAULT TRUE
);

ALTER TABLE entradas ADD COLUMN IF NOT EXISTS entrada_fixa_id INT REFERENCES entradas_fixas(id);

-- Trava anti-duplicação: no máximo 1 lançamento por entrada fixa por mês.
-- Cast ::timestamp pela mesma razão do uq_despesa_fixa_mes (004): garante a
-- sobrecarga IMMUTABLE de DATE_TRUNC exigida em expressão de índice.
CREATE UNIQUE INDEX IF NOT EXISTS uq_entrada_fixa_mes
    ON entradas (entrada_fixa_id, DATE_TRUNC('month', data::timestamp))
    WHERE entrada_fixa_id IS NOT NULL;
