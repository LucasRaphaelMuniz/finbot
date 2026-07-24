-- 027: controle de "contas a pagar do mês" (pedido do Lucas, 24/07/2026 —
-- substitui a planilha de junho que ele mantinha à mão).
--
-- CONTEXTO — por que isto NÃO é o retorno da faturas_pagas da migração 021.
--
-- A 021 criou `faturas_pagas` pra calcular LIMITE ROTATIVO: um número
-- derivado ("quanto do limite ainda tenho") que dependia de marcar fatura
-- como paga. A 024 dropou porque o número não respondia a pergunta que o
-- Lucas realmente faz, e o ritual de marcar existia só pra alimentar esse
-- cálculo — trabalho manual sem retorno.
--
-- Aqui o "pago" não alimenta cálculo derivado nenhum: ELE É A RESPOSTA. A
-- pergunta é "o que eu ainda preciso pagar este mês e o que já paguei",
-- que é a única coisa que a planilha do Excel fazia. Mesmo mecanismo,
-- finalidade oposta — por isso o nome é outro (`faturas_pagamentos`), pra
-- quem ler o histórico não achar que a 024 foi revertida.
--
-- MODELO — o board tem DUAS identidades de linha, porque o Excel e o
-- finbot contam a mesma coisa em granularidades diferentes:
--
--   "Internet 99,90"  → 1 linha no Excel = 1 registro em `gastos`
--                       → estado vai em gastos.pago (abaixo)
--   "Cartão BTG 6.000"→ 1 linha no Excel = N registros em `gastos`
--                       → estado vai em faturas_pagamentos, chaveado por
--                         (forma_pagamento_id, competencia)
--
-- Não dá pra unificar em gastos.pago: marcar a fatura como paga exigiria
-- UPDATE em N linhas e ficaria inconsistente assim que um gasto novo caísse
-- naquela competência (fatura "paga" com item não pago dentro).

-- ---------------------------------------------------------------------------
-- Contas que são 1 gasto só (fixa em boleto/débito/pix, ex.: Sanepar, Copel)
-- ---------------------------------------------------------------------------
ALTER TABLE gastos ADD COLUMN IF NOT EXISTS pago    BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE gastos ADD COLUMN IF NOT EXISTS pago_em TIMESTAMPTZ;

-- Índice parcial: a tela de contas filtra sempre por competência e quase
-- sempre quer o que está PENDENTE. Parcial (WHERE NOT pago) em vez de índice
-- cheio porque a coluna é fortemente enviesada — mês fechado fica todo TRUE
-- e essas linhas não interessam mais pra consulta.
CREATE INDEX IF NOT EXISTS ix_gastos_competencia_nao_pago
    ON gastos (competencia) WHERE NOT pago;

-- ---------------------------------------------------------------------------
-- Contas que são a fatura inteira de um cartão
-- ---------------------------------------------------------------------------
-- `valor_pago` fica separado da soma dos gastos DE PROPÓSITO: a fatura pode
-- fechar em 6.000 e ser paga em 5.500 (resto no rotativo). Guardar o valor
-- pago aqui preserva `gastos` intocado — a soma continua sendo a verdade do
-- que foi comprado, e a diferença entre as duas fica visível em vez de
-- sumir dentro de um UPDATE. NULL = pagou o valor cheio da fatura.
--
-- A presença da linha JÁ significa "paga"; não há coluna booleana. Desmarcar
-- é DELETE. Isso evita o estado ambíguo (linha existindo com pago=FALSE) que
-- exigiria decidir se conta como pendente ou como nunca-tocada.
CREATE TABLE IF NOT EXISTS faturas_pagamentos (
    id                 SERIAL PRIMARY KEY,
    forma_pagamento_id INT NOT NULL REFERENCES formas_pagamento(id) ON DELETE CASCADE,
    -- Mês da FATURA (gastos.competencia), não o mês em que ela vence. A
    -- conversão competência -> mês de vencimento é regra de negócio e vive
    -- em services/competencia.py::mes_vencimento, não duplicada no schema.
    competencia        DATE NOT NULL,
    valor_pago         DECIMAL,
    pago_em            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (forma_pagamento_id, competencia)
);
