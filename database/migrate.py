"""
database/migrate.py — Runner de migrações versionadas.

Substitui os `ALTER ... IF NOT EXISTS` improvisados que viviam em `init_db.py`.
Cada arquivo `database/migrations/NNN_*.sql` é aplicado uma única vez, em ordem
numérica, dentro de uma transação. O que já foi aplicado fica registrado em
`schema_migrations` — rodar de novo é seguro (idempotente): migrações já
aplicadas são puladas.

Uso:
    python -m database.migrate            # aplica tudo que falta
    python -m database.migrate --status   # só lista o que falta/já aplicado, não aplica nada

IMPORTANTE: usa DATABASE_URL do ambiente (.env). Não aplique direto em produção
sem antes rodar contra uma cópia de dev/staging — combine com o Lucas antes.
"""

import os
import sys
import re
import psycopg
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

_NOME_ARQUIVO_RE = re.compile(r"^(\d+)_.+\.sql$")


def _listar_migrations() -> list[Path]:
    """Retorna os arquivos .sql da pasta migrations, ordenados pelo prefixo numérico."""
    arquivos = []
    for path in MIGRATIONS_DIR.glob("*.sql"):
        m = _NOME_ARQUIVO_RE.match(path.name)
        if not m:
            print(f"⚠️  Ignorando '{path.name}': nome fora do padrão NNN_descricao.sql")
            continue
        arquivos.append((int(m.group(1)), path))
    arquivos.sort(key=lambda t: t[0])
    return [p for _, p in arquivos]


def _garantir_tabela_controle(conn):
    with conn.cursor() as cur:
        cur.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                   version     TEXT PRIMARY KEY,
                   applied_at  TIMESTAMP DEFAULT NOW()
               )"""
        )
    conn.commit()


def _aplicadas(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM schema_migrations")
        return {row[0] for row in cur.fetchall()}


def status():
    conn = psycopg.connect(os.getenv("DATABASE_URL"))
    try:
        _garantir_tabela_controle(conn)
        aplicadas = _aplicadas(conn)
        for path in _listar_migrations():
            marca = "✅ aplicada" if path.name in aplicadas else "⏳ pendente"
            print(f"{marca} — {path.name}")
    finally:
        conn.close()


def migrar():
    conn = psycopg.connect(os.getenv("DATABASE_URL"))
    try:
        _garantir_tabela_controle(conn)
        aplicadas = _aplicadas(conn)
        pendentes = [p for p in _listar_migrations() if p.name not in aplicadas]

        if not pendentes:
            print("✅ Nada a fazer — todas as migrações já foram aplicadas.")
            return

        for path in pendentes:
            print(f"→ Aplicando {path.name}...")
            sql = path.read_text(encoding="utf-8")
            with conn.cursor() as cur:
                try:
                    cur.execute(sql)
                    cur.execute(
                        "INSERT INTO schema_migrations (version) VALUES (%s)",
                        (path.name,),
                    )
                    conn.commit()
                except Exception:
                    conn.rollback()
                    print(f"❌ Falhou em {path.name} — nada foi commitado desta migração.")
                    raise
            print(f"✅ {path.name} aplicada.")

        print(f"✅ {len(pendentes)} migração(ões) aplicada(s) com sucesso.")
    finally:
        conn.close()


if __name__ == "__main__":
    if "--status" in sys.argv:
        status()
    else:
        migrar()
