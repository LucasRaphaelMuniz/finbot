-- 026: lançamento antecipado de despesas fixas (pedido do Lucas, 18/07/2026:
-- "não quero os lançamentos futuros como previsto — quero que fiquem igual
-- compra parcelada, pois já é certeza que vou pagar").
--
-- O lançador (services/despesas_fixas.py) passa a criar o gasto REAL da
-- competência do mês seguinte com antecedência, em vez de deixar só a linha
-- sintética "fixa (previsto)" da listagem. Isso cria um problema novo que
-- esta tabela resolve: se o usuário EXCLUIR esse gasto futuro, o lançador
-- (que roda todo dia + na subida do processo) recriaria a linha no dia
-- seguinte — a exclusão seria desfeita silenciosamente.
--
-- Solução: tombstone. Ao excluir um gasto vindo de despesa fixa com
-- competência do mês atual pra frente (services/gastos.py::remover_gasto),
-- grava-se (despesa_fixa_id, competencia) aqui; o lançador e a projeção
-- ("previsto") pulam essa combinação. Vale só pra AQUELE mês — a fixa
-- continua ativa e lança normalmente nos meses seguintes. Isso também
-- corrige um comportamento antigo: excluir o gasto de uma fixa no mês
-- corrente era desfeito pelo catch-up (hoje.day >= dia_efetivo) na rodada
-- seguinte do lançador.
--
-- `competencia` é sempre normalizada pro dia 1º do mês na gravação — a PK
-- composta então dispensa índice funcional com DATE_TRUNC (e o malabarismo
-- de cast IMMUTABLE da migração 004).

CREATE TABLE IF NOT EXISTS despesas_fixas_supressoes (
    despesa_fixa_id INT  NOT NULL REFERENCES despesas_fixas(id) ON DELETE CASCADE,
    competencia     DATE NOT NULL,
    criado_em       TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (despesa_fixa_id, competencia)
);
