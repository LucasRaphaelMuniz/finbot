"""
reset_db.py — Limpa todo o banco e recria do zero.

ATENÇÃO: apaga todos os dados (usuários, gastos, grupos, sessões).
Use apenas para reiniciar os testes.

    python reset_db.py
"""

import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

TRUNCATE = """
TRUNCATE TABLE
    sessoes,
    gastos,
    formas_pagamento,
    usuarios,
    grupos,
    categorias
RESTART IDENTITY CASCADE;
"""

CATEGORIAS = [
    "Mercado", "Combustível", "Restaurante", "Farmácia",
    "Lazer", "Educação", "Saúde", "Transporte", "Outros",
]

# Garante que as colunas novas existam (idempotente)
MIGRATIONS = """
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS parceiro_telefone TEXT;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS grupo_id INT REFERENCES grupos(id) ON DELETE SET NULL;
ALTER TABLE formas_pagamento ADD COLUMN IF NOT EXISTS grupo_id INT REFERENCES grupos(id) ON DELETE CASCADE;
ALTER TABLE gastos ADD COLUMN IF NOT EXISTS grupo_id INT REFERENCES grupos(id) ON DELETE SET NULL;
ALTER TABLE sessoes ADD COLUMN IF NOT EXISTS dados_temp TEXT;
"""


def main():
    conn = psycopg.connect(os.getenv("DATABASE_URL"))
    cur  = conn.cursor()

    print("→ Limpando todos os dados...")
    cur.execute(TRUNCATE)

    print("→ Aplicando migrations (colunas novas)...")
    cur.execute(MIGRATIONS)

    print("→ Inserindo categorias...")
    for cat in CATEGORIAS:
        cur.execute(
            "INSERT INTO categorias (nome) VALUES (%s) ON CONFLICT (nome) DO NOTHING",
            (cat,),
        )

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Banco limpo e pronto para testes!")


if __name__ == "__main__":
    main()
