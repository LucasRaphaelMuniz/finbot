-- 003: parcelamento + competência
-- competencia = mês a que o gasto pertence (pode diferir da data real da compra,
-- ex.: compra no cartão após o fechamento cai na competência do mês seguinte).
--
-- ATENÇÃO (P2, aceito pelo Lucas em 11/07/2026): trocar os filtros de saldo/resumo
-- de DATE_TRUNC('month', g.data) para competencia MUDA o resultado de consultas
-- existentes para gastos de cartão perto do fechamento. Ver Fase 3.2 do
-- PLANO_EXECUCAO.md — essa mudança de código vem depois, não nesta migração.

CREATE TABLE IF NOT EXISTS compras_parceladas (
    id                 SERIAL PRIMARY KEY,
    usuario_id         INT REFERENCES usuarios(id),
    grupo_id           INT REFERENCES grupos(id),
    forma_pagamento_id INT REFERENCES formas_pagamento(id),
    categoria_id       INT REFERENCES categorias(id),
    descricao          TEXT,
    valor_total         DECIMAL NOT NULL,
    parcelas           INT NOT NULL,
    data_compra        DATE DEFAULT NOW()
);

ALTER TABLE gastos ADD COLUMN IF NOT EXISTS compra_parcelada_id INT REFERENCES compras_parceladas(id);
ALTER TABLE gastos ADD COLUMN IF NOT EXISTS parcela_num INT;
ALTER TABLE gastos ADD COLUMN IF NOT EXISTS competencia DATE;

-- Backfill: histórico existente usa o mês da própria data como competência.
UPDATE gastos SET competencia = DATE_TRUNC('month', data) WHERE competencia IS NULL;
