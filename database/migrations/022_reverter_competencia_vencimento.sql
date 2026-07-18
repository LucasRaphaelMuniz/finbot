-- 022: REVERTE o deslocamento da 020 (competência de cartão = mês do
-- vencimento) e rebaseia faturas_pagas — decisão revista com o Lucas em
-- 17-18/07/2026.
--
-- Por quê: a 020 fazia a compra de hoje "sumir" das telas do mês corrente
-- (ia direto pro mês do pagamento) — impossível acompanhar o mês. O modelo
-- final é "fatura como conta a pagar": gastos.competencia volta a ser o
-- MÊS DA FATURA (regra da 002/003, só dia_fechamento), e quem provisiona a
-- fatura no mês do vencimento é só o CAIXA (services/resumo.py +
-- services/competencia.py::mes_vencimento) — sem tocar nos gastos.
--
-- CUIDADO com o desfazer cego: entre a aplicação da 020 e esta 022, o
-- código em produção era o ANTIGO (o deploy do modelo-vencimento nunca
-- aconteceu — o push falhou). Gastos criados nesse intervalo já nasceram
-- com competência = mês da fatura (regra antiga/correta) e NÃO podem ser
-- deslocados de volta. Filtro: só desfaz gastos cujo `data` (momento do
-- registro) é anterior ao applied_at da 020 em schema_migrations.
-- Limitação conhecida: importação de fatura grava `data` = data da
-- transação (passado), então uma importação feita DEPOIS da 020 seria
-- deslocada errado por este filtro — não houve importação nesse intervalo
-- (horas, 17/07/2026), risco aceito e documentado.
UPDATE gastos g
SET competencia = (DATE_TRUNC('month', g.competencia) - INTERVAL '1 month')::date
FROM formas_pagamento fp
WHERE fp.id = g.forma_pagamento_id
  AND fp.dia_fechamento IS NOT NULL
  AND (fp.dia_vencimento IS NULL OR fp.dia_vencimento <= fp.dia_fechamento)
  AND g.data < (SELECT applied_at FROM schema_migrations
                WHERE version = '020_competencia_mes_vencimento.sql');

-- Rebaseia faturas_pagas: o backfill da 021 marcou competências sob a
-- semântica antiga (mês do vencimento). Como o código novo nunca foi
-- deployado, NÃO existe marcação manual de fatura paga — todas as linhas
-- são do backfill automático, então apagar tudo e refazer é seguro.
-- Regra nova: fatura de competência F está paga se o VENCIMENTO dela
-- (F, ou F+1 quando dia_vencimento <= dia_fechamento / não informado) já
-- passou do mês corrente. A fatura vencendo NESTE mês fica em aberto —
-- é ela que o usuário marca com "paguei a fatura <forma>".
DELETE FROM faturas_pagas;

INSERT INTO faturas_pagas (forma_pagamento_id, competencia, paga_em)
SELECT DISTINCT g.forma_pagamento_id, DATE_TRUNC('month', g.competencia)::date, NOW()
FROM gastos g
JOIN formas_pagamento fp ON fp.id = g.forma_pagamento_id
WHERE fp.dia_fechamento IS NOT NULL
  AND DATE_TRUNC('month', g.competencia)
      + (CASE WHEN fp.dia_vencimento IS NOT NULL AND fp.dia_vencimento > fp.dia_fechamento
              THEN INTERVAL '0 months' ELSE INTERVAL '1 month' END)
      < DATE_TRUNC('month', NOW())
ON CONFLICT (forma_pagamento_id, competencia) DO NOTHING;
