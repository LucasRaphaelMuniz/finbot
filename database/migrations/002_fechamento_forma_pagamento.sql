-- 002: fechamento de cartão por forma de pagamento
-- dia_fechamento define em qual competência um gasto de cartão cai
-- (compra após o fechamento -> competência seguinte, ver 003).

ALTER TABLE formas_pagamento ADD COLUMN IF NOT EXISTS dia_fechamento SMALLINT
    CHECK (dia_fechamento BETWEEN 1 AND 31);
