-- 012: tabela de verificação de posse de telefone via WhatsApp (Fase B do
-- AUDITORIA_E_PLANO_CADASTRO.md, corrige F2 — merge de conta sem provar
-- posse do número era uma vulnerabilidade: bastava digitar o telefone de
-- outra pessoa no cadastro web pra herdar o histórico financeiro dela).
--
-- Coluna `criado_em` foi acrescentada ao schema original do plano (que só
-- tinha id/auth_user_id/telefone/codigo/tentativas/expira_em/verificado_em)
-- — necessária pra aplicar o rate limit de 3 envios/número/hora descrito na
-- Fase B (services/verificacao.py:enviar_codigo). Sem uma coluna de
-- criação separada, não dá pra contar "quantos códigos foram enviados pra
-- esse número na última hora" sem reaproveitar expira_em de um jeito frágil
-- (teria que subtrair EXPIRA_MINUTOS toda hora que a constante mudasse).

CREATE TABLE IF NOT EXISTS verificacoes_telefone (
    id            SERIAL PRIMARY KEY,
    auth_user_id  UUID NOT NULL,
    telefone      TEXT NOT NULL,           -- já normalizado (JID)
    codigo        TEXT NOT NULL,           -- 6 dígitos, gerado com secrets
    tentativas    INT NOT NULL DEFAULT 0,  -- máx 5, depois invalida (ver services/verificacao.py)
    criado_em     TIMESTAMP NOT NULL DEFAULT NOW(),
    expira_em     TIMESTAMP NOT NULL,      -- criado_em + 10 min
    verificado_em TIMESTAMP
);

-- Toda leitura em services/verificacao.py filtra por telefone (rate limit) ou
-- por (auth_user_id, telefone) (confirmar código, checar se já verificou).
CREATE INDEX IF NOT EXISTS idx_verificacoes_telefone_telefone ON verificacoes_telefone (telefone);
CREATE INDEX IF NOT EXISTS idx_verificacoes_telefone_auth_user ON verificacoes_telefone (auth_user_id, telefone);
