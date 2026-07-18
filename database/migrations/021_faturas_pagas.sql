-- 021: limite rotativo real do cartão (decisão P, aceita por Lucas em
-- 17/07/2026).
--
-- Com 019/020, `gastos.competencia` de cartão passou a ser o mês do
-- VENCIMENTO da fatura — bom pro orçamento (saldo/resumo), mas ruim pra
-- responder "quanto do limite eu já usei": limite usado tem que incluir a
-- fatura fechada ainda não paga E as parcelas futuras de compras
-- parceladas (elas comprometem limite igual num cartão de verdade), coisa
-- que "gasto do mês corrente" sozinho não cobre.
--
-- Modelo: limite_usado = tudo que já foi gasto na forma MENOS o que já foi
-- coberto por fatura marcada como paga aqui. Sem overhead de guardar um
-- "valor da fatura" à parte — soma direto de `gastos` por competência.
CREATE TABLE IF NOT EXISTS faturas_pagas (
    id                 SERIAL PRIMARY KEY,
    forma_pagamento_id INT NOT NULL REFERENCES formas_pagamento(id) ON DELETE CASCADE,
    competencia        DATE NOT NULL,
    paga_em            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (forma_pagamento_id, competencia)
);

-- Backfill: marca como pagas todas as competências de cartão anteriores ao
-- mês corrente. Sem isso, o limite usado nasceria "estourado" contando
-- dívida de meses que na vida real já foram quitados — o histórico
-- existente não tem como saber a data real de pagamento de cada fatura
-- antiga, então a aproximação é "tudo antes de hoje já foi pago".
INSERT INTO faturas_pagas (forma_pagamento_id, competencia, paga_em)
SELECT DISTINCT g.forma_pagamento_id, g.competencia, NOW()
FROM gastos g
JOIN formas_pagamento fp ON fp.id = g.forma_pagamento_id
WHERE fp.dia_fechamento IS NOT NULL
  AND DATE_TRUNC('month', g.competencia) < DATE_TRUNC('month', NOW())
ON CONFLICT (forma_pagamento_id, competencia) DO NOTHING;
