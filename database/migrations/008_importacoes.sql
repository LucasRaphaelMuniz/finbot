-- 008: importação de fatura de cartão (Fase 5.3 do PLANO_EXECUCAO.md)
--
-- `linhas` guarda a contagem de gastos criados por essa importação (não a
-- lista em si — os gastos de verdade ficam em `gastos`, ligados por
-- importacao_id; útil pro "desfazer importação" da tela: DELETE FROM gastos
-- WHERE importacao_id = X).
CREATE TABLE IF NOT EXISTS importacoes (
    id                  SERIAL PRIMARY KEY,
    grupo_id            INT REFERENCES grupos(id),
    usuario_id          INT REFERENCES usuarios(id),
    forma_pagamento_id  INT REFERENCES formas_pagamento(id),
    arquivo_nome        TEXT,
    linhas              INT,
    criado_em           TIMESTAMP DEFAULT NOW()
);

ALTER TABLE gastos ADD COLUMN IF NOT EXISTS importacao_id INT REFERENCES importacoes(id);
