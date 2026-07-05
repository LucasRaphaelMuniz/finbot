"""
init_db.py — Cria tabelas e faz o seed de categorias.
Execute uma vez antes de subir o servidor:

    python init_db.py
"""

import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id       SERIAL PRIMARY KEY,
    nome     TEXT,
    telefone TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS formas_pagamento (
    id            SERIAL PRIMARY KEY,
    usuario_id    INT REFERENCES usuarios(id) ON DELETE CASCADE,
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
    criado_em      TIMESTAMP DEFAULT NOW(),
    expira_em      TIMESTAMP
);
"""

CATEGORIAS = [
    "Mercado", "Combustível", "Restaurante", "Farmácia",
    "Lazer", "Educação", "Saúde", "Transporte", "Outros",
]


def main():
    conn = psycopg.connect(os.getenv("DATABASE_URL"))
    cur  = conn.cursor()

    print("→ Criando tabelas...")
    cur.execute(SCHEMA)

    print("→ Inserindo categorias...")
    for cat in CATEGORIAS:
        cur.execute(
            "INSERT INTO categorias (nome) VALUES (%s) ON CONFLICT (nome) DO NOTHING",
            (cat,),
        )

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Banco inicializado com sucesso.")


if __name__ == "__main__":
    main()
