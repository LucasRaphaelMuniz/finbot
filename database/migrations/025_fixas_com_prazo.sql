-- 025: despesas fixas com prazo (custo fixo parcelado — pedido do Lucas em
-- 18/07/2026: "financiamento da casa é um custo fixo, mas tenho um período
-- determinado de pagamento").
--
-- parcelas_total NULL = fixa sem fim (aluguel, internet — comportamento de
-- sempre). Com valor (ex: 48), o lançador conta quantos gastos a fixa já
-- lançou e desativa sozinha (ativa = FALSE) ao atingir o total — sem
-- ritual manual de encerrar. A contagem sai de `gastos` (fonte de
-- verdade), não de um contador próprio que poderia dessincronizar.
ALTER TABLE despesas_fixas ADD COLUMN IF NOT EXISTS parcelas_total INT
    CHECK (parcelas_total IS NULL OR parcelas_total >= 1);
