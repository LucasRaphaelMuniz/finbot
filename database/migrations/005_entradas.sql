-- 005: entradas/receitas
-- Gap não coberto pelo escopo original (G1, resolvido em P1): bot (input livre,
-- mesmo padrão dos gastos) + web. Entrada não afeta saldo por forma de pagamento
-- (limite é conceito de gasto); aparece no resumo do bot e no dashboard web.

CREATE TABLE IF NOT EXISTS entradas (
    id         SERIAL PRIMARY KEY,
    usuario_id INT REFERENCES usuarios(id),
    grupo_id   INT REFERENCES grupos(id),
    descricao  TEXT,
    valor      DECIMAL NOT NULL,
    data       DATE DEFAULT NOW()
);
