"""
init_db.py — Bootstrap de banco novo: cria o schema base (pré-migrações),
roda o seed de categorias e em seguida aplica todas as migrações versionadas
de `database/migrations/` via `database/migrate.py`.

Execute uma vez antes de subir o servidor num banco vazio:

    python init_db.py

Para um banco que já tem o schema base (produção, staging existente) e só
precisa das migrações novas, use `python -m database.migrate` diretamente —
rodar init_db.py de novo é seguro (tudo é IF NOT EXISTS / idempotente), mas
desnecessário.

Nota (D4 do AUDITORIA_E_PLANO_CADASTRO.md, ponto menor): este arquivo e
`database/migrations/` convivem hoje — o schema base vive aqui, tudo que
veio depois vive em migrations numeradas. Risco real: alguém altera uma
tabela do schema base sem lembrar que init_db.py também a define, e os dois
lugares divergem silenciosamente pra quem inicializa um banco do zero vs.
quem só aplica migrações num banco existente. A consolidação ideal (mover
todo o schema base pra uma migration 001, e init_db.py virar só um wrapper
que chama `database.migrate`) está fora do escopo desta fase — é uma
mudança que mexe em toda inicialização de banco (dev, staging, produção) e
merece ser feita isolada, testada com um dump real antes de aplicar em
produção, não encaixada de passagem numa fase que já mexeu em cadastro/OTP.
Registrando a decisão aqui pra não se perder.
"""

import os
import psycopg
from dotenv import load_dotenv

from database.migrate import migrar as aplicar_migracoes

load_dotenv()

SCHEMA = """
CREATE TABLE IF NOT EXISTS grupos (
    id   SERIAL PRIMARY KEY,
    nome TEXT
);

CREATE TABLE IF NOT EXISTS usuarios (
    id                SERIAL PRIMARY KEY,
    nome              TEXT,
    telefone          TEXT UNIQUE,
    parceiro_telefone TEXT,
    grupo_id          INT REFERENCES grupos(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS formas_pagamento (
    id            SERIAL PRIMARY KEY,
    usuario_id    INT REFERENCES usuarios(id) ON DELETE CASCADE,
    grupo_id      INT REFERENCES grupos(id) ON DELETE CASCADE,
    nome          TEXT,
    limite_mensal DECIMAL
);

CREATE TABLE IF NOT EXISTS categorias (
    id   SERIAL PRIMARY KEY,
    nome TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS gastos (
    id                 SERIAL PRIMARY KEY,
    usuario_id         INT REFERENCES usuarios(id) ON DELETE CASCADE,
    forma_pagamento_id INT REFERENCES formas_pagamento(id),
    categoria_id       INT REFERENCES categorias(id),
    grupo_id           INT REFERENCES grupos(id) ON DELETE SET NULL,
    valor              DECIMAL,
    descricao          TEXT,
    data               TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sessoes (
    id             SERIAL PRIMARY KEY,
    usuario_id     INT REFERENCES usuarios(id) ON DELETE CASCADE,
    etapa          TEXT,
    valor_temp     DECIMAL,
    categoria_temp INT,
    forma_temp     INT,
    dados_temp     TEXT,
    criado_em      TIMESTAMP DEFAULT NOW(),
    expira_em      TIMESTAMP
);
"""
# Nota: até a Fase 1 deste bootstrap, as colunas grupo_id/parceiro_telefone/dados_temp
# eram adicionadas via ALTER TABLE ... IF NOT EXISTS soltos aqui embaixo. Isso foi
# absorvido: para bancos novos já nascem nas CREATE TABLE acima; para bancos
# existentes que já tinham essas colunas (produção atual), os ALTERs eram no-ops
# de qualquer forma. Novas alterações de schema a partir de agora vão para
# database/migrations/, não para esta string (D2 do PLANO_EXECUCAO.md).

CATEGORIAS = [
    "Mercado", "Combustível", "Restaurante", "Farmácia",
    "Lazer", "Educação", "Saúde", "Transporte", "Outros",
]

# Fase 6 (P6, preço definido pelo Lucas em 11/07/2026) + Fase 6.2:
# max_membros é o que services/grupos.py::adicionar_membro usa pra bloquear
# excedente. "unlimited" com max_membros=10 é "soft limit" (nome do plano
# promete ilimitado, mas o enforcement real trava em 10 — decisão de
# produto, não bug). preco_mensal é o único ciclo definido por ora;
# semestral/anual ficam NULL até existir promoção de ciclo mais longo.
PLANOS = [
    # (nome, max_membros, preco_mensal)
    ("basic", 1, 14.90),
    ("plus", 2, 19.90),
    ("master", 5, 29.90),
    ("unlimited", 10, 49.90),
]


def main():
    conn = psycopg.connect(os.getenv("DATABASE_URL"))
    cur  = conn.cursor()

    print("→ Criando tabelas base (pré-migrações)...")
    cur.execute(SCHEMA)
    conn.commit()
    cur.close()
    conn.close()

    # As migrações (001_categorias_por_grupo) trocam o UNIQUE(nome) de `categorias`
    # por um índice único (COALESCE(grupo_id, 0), LOWER(nome)) — precisam rodar
    # antes do seed abaixo, senão o ON CONFLICT do seed teria como alvo uma
    # constraint que não existe mais em bancos onde as migrações já rodaram.
    print("→ Aplicando migrações...")
    aplicar_migracoes()

    print("→ Inserindo categorias padrão (globais, grupo_id NULL)...")
    conn = psycopg.connect(os.getenv("DATABASE_URL"))
    cur  = conn.cursor()
    for cat in CATEGORIAS:
        cur.execute(
            "INSERT INTO categorias (nome) VALUES (%s) "
            "ON CONFLICT (COALESCE(grupo_id, 0), LOWER(nome)) DO NOTHING",
            (cat,),
        )
    conn.commit()
    cur.close()
    conn.close()

    print("→ Inserindo planos padrão (Fase 6, preços definidos em 11/07/2026)...")
    conn = psycopg.connect(os.getenv("DATABASE_URL"))
    cur  = conn.cursor()
    for nome, max_membros, preco_mensal in PLANOS:
        cur.execute(
            "INSERT INTO planos (nome, max_membros, preco_mensal) VALUES (%s, %s, %s) "
            "ON CONFLICT (nome) DO UPDATE SET max_membros = EXCLUDED.max_membros, "
            "preco_mensal = EXCLUDED.preco_mensal",
            (nome, max_membros, preco_mensal),
        )
    conn.commit()
    cur.close()
    conn.close()
    print("✅ Banco inicializado com sucesso.")


if __name__ == "__main__":
    main()
