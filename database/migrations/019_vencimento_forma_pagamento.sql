-- 019: dia de vencimento da fatura por forma de pagamento
--
-- dia_fechamento (002) já resolve em qual fatura uma compra cai. Faltava
-- saber em qual MÊS essa fatura é paga de fato — dia_vencimento resolve
-- isso (ver services/competencia.py, calcular_competencia). Sem
-- dia_vencimento configurado, a regra assume o caso mais comum no Brasil
-- (vencimento no mês seguinte ao fechamento) — não é obrigatório
-- preencher pra continuar funcionando.
ALTER TABLE formas_pagamento ADD COLUMN IF NOT EXISTS dia_vencimento SMALLINT
    CHECK (dia_vencimento BETWEEN 1 AND 31);
