-- 007: SaaS (Fase 6)
-- Sem gateway de pagamento nesta fase (D7 adiada, P5): colunas de preço e de
-- integração com gateway ficam NULL até a monetização entrar. status default
-- 'trial' cobre o fluxo enquanto não há cobrança automática.

CREATE TABLE IF NOT EXISTS planos (
    id             SERIAL PRIMARY KEY,
    nome           TEXT UNIQUE,          -- basic | plus | master | unlimited
    max_membros    INT,                  -- 1 | 2 | 5 | 10 (soft limit do unlimited)
    preco_mensal   DECIMAL,
    preco_semestral DECIMAL,
    preco_anual    DECIMAL
);

CREATE TABLE IF NOT EXISTS assinaturas (
    id                     SERIAL PRIMARY KEY,
    grupo_id               INT REFERENCES grupos(id) UNIQUE,
    plano_id               INT REFERENCES planos(id),
    status                 TEXT DEFAULT 'trial',   -- trial | ativa | inadimplente | cancelada
    ciclo                  TEXT,                    -- mensal | semestral | anual
    gateway_customer_id     TEXT,
    gateway_subscription_id TEXT,
    inicio                 TIMESTAMP DEFAULT NOW(),
    proximo_vencimento     TIMESTAMP
);
