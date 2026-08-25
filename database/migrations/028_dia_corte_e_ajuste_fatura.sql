-- 028: data de corte do mês + valor estimado/ajuste manual de fatura
-- (pedido do Lucas em 25/08/2026)
--
-- Contexto: Lucas recebe dia 25 (ajustável). Ele quer que TUDO que não é
-- cartão (entrada, despesa fixa fora do cartão, gasto avulso fora do
-- cartão) pare de fatiar por mês CALENDÁRIO e passe a fatiar por "mês do
-- pagamento": 25/08 até 25/09 é um mês só, não "agosto fechado". Cartão
-- continua exatamente como já era — só pelo dia_fechamento da própria forma
-- (services/faturas.py, services/competencia.py::calcular_competencia). A
-- prioridade entre os dois vive em services/competencia.py::dia_regra().

-- dia_corte: "dia do pagamento" do usuário. DEFAULT 25 (o que o Lucas usa
-- hoje) pra não deixar ninguém sem valor depois do deploy.
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS dia_corte SMALLINT NOT NULL DEFAULT 25
    CHECK (dia_corte BETWEEN 1 AND 31);

-- entradas ganha competencia própria, espelhando gastos.competencia — sem
-- isso, toda entrada continuaria fatiada por DATE_TRUNC('month', data) (mês
-- calendário) mesmo depois do dia_corte mudar a régua dos gastos. Backfill
-- com o mês calendário da própria data: histórico já lançado continua
-- batendo com o que sempre apareceu (mesma lógica do backfill da migração
-- 003 pra gastos.competencia) — só lançamento NOVO passa a usar dia_corte
-- (services/entradas.py::registrar_entrada).
ALTER TABLE entradas ADD COLUMN IF NOT EXISTS competencia DATE;
UPDATE entradas SET competencia = DATE_TRUNC('month', data)::date WHERE competencia IS NULL;
ALTER TABLE entradas ALTER COLUMN competencia SET NOT NULL;
CREATE INDEX IF NOT EXISTS idx_entradas_competencia ON entradas(competencia);

-- uq_entrada_fixa_mes (migração 023) indexava por `data` — trocado por
-- `competencia` pela mesma razão de uq_despesa_fixa_mes (004) já indexar
-- por competência: o lançador (services/entradas_fixas.py) passou a
-- verificar duplicidade por competência, não por data; o índice único
-- precisa concordar com essa checagem, senão vira uma segunda regra livre
-- pra divergir da que o código usa de verdade.
DROP INDEX IF EXISTS uq_entrada_fixa_mes;
CREATE UNIQUE INDEX IF NOT EXISTS uq_entrada_fixa_mes
    ON entradas (entrada_fixa_id, DATE_TRUNC('month', competencia::timestamp))
    WHERE entrada_fixa_id IS NOT NULL;

-- Ajuste manual da fatura do cartão (pedido do Lucas: "às vezes dá uma
-- pequena diferença por fechamento" — juros, IOF, arredondamento do banco
-- que não vira gasto individual). Soma/subtrai por cima da soma dos gastos
-- daquela competência, sem redistribuir entre eles — mesma filosofia de
-- faturas_pagamentos (migração 027): anota a diferença à parte, não mexe
-- no histórico de compras. UNIQUE por (forma, competência): no máximo 1
-- ajuste por fatura (services/faturas.py faz UPSERT nele).
CREATE TABLE IF NOT EXISTS ajustes_fatura (
    id                 SERIAL PRIMARY KEY,
    forma_pagamento_id INTEGER NOT NULL REFERENCES formas_pagamento(id) ON DELETE CASCADE,
    competencia        DATE NOT NULL,
    valor_ajuste       NUMERIC(12,2) NOT NULL,
    motivo             TEXT,
    criado_em          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (forma_pagamento_id, competencia)
);
