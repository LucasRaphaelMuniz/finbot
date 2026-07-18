"""
scripts/migrar_custo_fixo.py — migração de DADOS (não de schema), item A do
PLANO_AJUSTES_CARTAO_CUSTO_FIXO.md.

Cria (ou reaproveita) uma forma de pagamento "Custo Fixo" e realoca pra ela
as despesas fixas pagas por débito/PIX — SEM mexer nas que são pagas no
cartão (assinaturas tipo Netflix/seguro continuam na forma do cartão, que
é quem conta limite e cai na fatura certa via services/competencia.py).
Também cria a categoria "Assinaturas" pra essas fixas de cartão, se ainda
não existir.

Por que é um script e não uma migration numerada: migrations em
database/migrations/ são schema, aplicadas em todo banco (dev/staging/
produção) sempre da mesma forma. Isso aqui é dado de UMA conta específica
(qual fixa é cartão, qual é débito) — decisão que só o dono da conta sabe
responder, por isso é interativo em vez de automático.

Roda LOCAL (não dá pra rodar de dentro da sandbox do Claude — sem rota até
o host do Supabase). Uso:

    python scripts/migrar_custo_fixo.py <usuario_id>

Onde <usuario_id> é o id em `usuarios` (não o telefone) — descubra com:

    SELECT id, nome, telefone FROM usuarios;
"""

import os
import sys

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from db import _get_grupo_id  # noqa: E402
from services.categorias import adicionar_categoria  # noqa: E402


def _conectar():
    return psycopg.connect(os.getenv("DATABASE_URL"), row_factory=dict_row)


def _sim(prompt: str, default: bool) -> bool:
    sufixo = " [S/n] " if default else " [s/N] "
    resp = input(prompt + sufixo).strip().lower()
    if not resp:
        return default
    return resp in ("s", "sim", "y", "yes")


def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/migrar_custo_fixo.py <usuario_id>")
        sys.exit(1)
    usuario_id = int(sys.argv[1])

    conn = _conectar()
    gid = _get_grupo_id(conn, usuario_id)
    cur = conn.cursor()

    cur.execute("SELECT id, nome FROM usuarios WHERE id = %s", (usuario_id,))
    usuario = cur.fetchone()
    if not usuario:
        print(f"❌ usuario_id {usuario_id} não encontrado.")
        sys.exit(1)
    print(f"→ Conta: {usuario['nome']} (usuario_id={usuario_id}, grupo_id={gid})\n")

    # ── 1. Lista despesas fixas ativas ──────────────────────────────────────
    if gid:
        cur.execute(
            """SELECT f.id, f.descricao, f.valor, fp.id AS forma_id, fp.nome AS forma_nome,
                      fp.dia_fechamento
               FROM despesas_fixas f
               LEFT JOIN formas_pagamento fp ON fp.id = f.forma_pagamento_id
               WHERE f.grupo_id = %s AND f.ativa = TRUE ORDER BY f.descricao""",
            (gid,),
        )
    else:
        cur.execute(
            """SELECT f.id, f.descricao, f.valor, fp.id AS forma_id, fp.nome AS forma_nome,
                      fp.dia_fechamento
               FROM despesas_fixas f
               LEFT JOIN formas_pagamento fp ON fp.id = f.forma_pagamento_id
               WHERE f.usuario_id = %s AND f.grupo_id IS NULL AND f.ativa = TRUE
               ORDER BY f.descricao""",
            (usuario_id,),
        )
    fixas = cur.fetchall()

    if not fixas:
        print("Nenhuma despesa fixa ativa encontrada. Nada a fazer.")
        return

    print("Despesas fixas ativas:\n")
    for f in fixas:
        tipo = "💳 cartão" if f["dia_fechamento"] else "🏦 débito/PIX/outro"
        print(f"  [{f['id']}] {f['descricao']} — R$ {f['valor']} — {f['forma_nome'] or '(sem forma)'} ({tipo})")
    print()

    # ── 2. Escolhe quais migram pra "Custo Fixo" ────────────────────────────
    # Sugestão automática: só oferece as que NÃO são de cartão (dia_fechamento
    # NULL) — fixa de cartão precisa continuar contando limite/fatura, migrar
    # ela pra "Custo Fixo" quebraria isso (services/competencia.py só calcula
    # competência de fatura pra forma com dia_fechamento).
    selecionadas = []
    for f in fixas:
        if f["dia_fechamento"]:
            print(f"⏭  '{f['descricao']}' é cartão ({f['forma_nome']}) — pulando (fica como está).")
            continue
        if _sim(f"Migrar '{f['descricao']}' ({f['forma_nome'] or 'sem forma'}) para 'Custo Fixo'?", default=True):
            selecionadas.append(f)

    if not selecionadas:
        print("\nNenhuma fixa selecionada para migrar. Nada a fazer.")
        conn.close()
        return

    # ── 3. Garante a forma "Custo Fixo" ─────────────────────────────────────
    if gid:
        cur.execute(
            "SELECT id FROM formas_pagamento WHERE grupo_id = %s AND LOWER(nome) = 'custo fixo'",
            (gid,),
        )
    else:
        cur.execute(
            "SELECT id FROM formas_pagamento WHERE usuario_id = %s AND grupo_id IS NULL "
            "AND LOWER(nome) = 'custo fixo'",
            (usuario_id,),
        )
    custo_fixo = cur.fetchone()
    if custo_fixo:
        custo_fixo_id = custo_fixo["id"]
        print(f"\n→ Forma 'Custo Fixo' já existe (id={custo_fixo_id}).")
    else:
        cur.execute(
            """INSERT INTO formas_pagamento (usuario_id, grupo_id, nome, limite_mensal, dia_fechamento)
               VALUES (%s, %s, 'Custo Fixo', NULL, NULL) RETURNING id""",
            (usuario_id, gid),
        )
        custo_fixo_id = cur.fetchone()["id"]
        conn.commit()
        print(f"\n→ Forma 'Custo Fixo' criada (id={custo_fixo_id}).")

    # ── 4. Aplica: despesas_fixas + backfill de gastos já lançados ──────────
    ids = [f["id"] for f in selecionadas]
    cur.execute(
        "UPDATE despesas_fixas SET forma_pagamento_id = %s WHERE id = ANY(%s)",
        (custo_fixo_id, ids),
    )
    cur.execute(
        "UPDATE gastos SET forma_pagamento_id = %s WHERE despesa_fixa_id = ANY(%s) RETURNING id",
        (custo_fixo_id, ids),
    )
    gastos_atualizados = cur.fetchall()
    conn.commit()

    print(f"\n✅ {len(ids)} despesa(s) fixa(s) migrada(s) para 'Custo Fixo'.")
    print(f"✅ {len(gastos_atualizados)} gasto(s) já lançado(s) atualizado(s) (backfill).")

    conn.close()

    # ── 5. Categoria "Assinaturas" (pra fixas de cartão) ────────────────────
    if gid and _sim("\nCriar categoria 'Assinaturas' (pra fixas de cartão tipo Netflix/seguro)?", default=True):
        cat = adicionar_categoria(usuario_id, "Assinaturas")
        if cat:
            print("✅ Categoria 'Assinaturas' criada.")
        else:
            print("ℹ️  Categoria 'Assinaturas' já existia (ou nome inválido) — nada feito.")
    elif not gid:
        print("\nℹ️  Conta sem grupo — categoria customizada exige grupo (adicionar_categoria "
              "retorna None sem ele). Crie o grupo primeiro se quiser 'Assinaturas' customizada, "
              "ou use uma categoria padrão existente.")


if __name__ == "__main__":
    main()
