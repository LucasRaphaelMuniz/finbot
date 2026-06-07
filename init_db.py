"""
init_db.py — Faz o seed de categorias via SDK do Supabase.

Antes de rodar este script, crie as tabelas no SQL Editor do Supabase
(https://supabase.com/dashboard → seu projeto → SQL Editor) com o SQL abaixo:

------------------------------------------------------------
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
    data               TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sessoes (
    id             SERIAL PRIMARY KEY,
    usuario_id     INT REFERENCES usuarios(id) ON DELETE CASCADE,
    etapa          TEXT,
    valor_temp     DECIMAL,
    categoria_temp INT,
    forma_temp     INT,
    criado_em      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expira_em      TIMESTAMP WITH TIME ZONE
);
------------------------------------------------------------

Depois execute:
    python init_db.py
"""

from dotenv import load_dotenv
from db import supabase

load_dotenv()

CATEGORIAS = [
    "Mercado", "Combustível", "Restaurante", "Farmácia",    "Lazer", "Educação", "Saúde", "Transporte", "Outros",
]


def main():
    print("Inserindo categorias...")
    supabase.table("categorias").upsert(
        [{"nome": cat} for cat in CATEGORIAS],
        on_conflict="nome",
    ).execute()
    print("Banco inicializado com sucesso.")


if __name__ == "__main__":
    main()
