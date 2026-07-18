-- 020: recalcula competencia dos gastos existentes de cartão para o MÊS DO
-- VENCIMENTO da fatura, em vez do mês da fatura em si (ver 019 e
-- services/competencia.py — decisão P (aceita por Lucas em 17/07/2026):
-- gasto de cartão só sai do caixa quando a fatura é paga, o dashboard
-- estava mostrando ele um mês antes disso).
--
-- Por que isso é só um deslocamento fixo de +1 mês por forma de pagamento,
-- e não precisa recalcular a partir da data de compra: a competência
-- gravada em `gastos.competencia` JÁ é o mês da fatura (calculado por
-- calcular_competencia na 1ª gravação — 002/003). O mês do vencimento é
-- sempre o mês da fatura (se dia_vencimento > dia_fechamento) ou o mês
-- seguinte (se dia_vencimento <= dia_fechamento, ou dia_vencimento não
-- informado — fallback) — essa comparação depende só dos dois campos da
-- forma de pagamento, nunca da data da compra em si. Por isso dá pra
-- aplicar em lote sem reprocessar gasto por gasto.
--
-- Formas sem dia_fechamento (pix/débito/Custo Fixo) não são tocadas —
-- competência delas sempre foi (e continua sendo) o mês da própria compra.
UPDATE gastos g
SET competencia = (DATE_TRUNC('month', g.competencia) + INTERVAL '1 month')::date
FROM formas_pagamento fp
WHERE fp.id = g.forma_pagamento_id
  AND fp.dia_fechamento IS NOT NULL
  AND (fp.dia_vencimento IS NULL OR fp.dia_vencimento <= fp.dia_fechamento);
