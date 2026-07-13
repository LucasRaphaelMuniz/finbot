"""
services/planos.py — leitura de planos/assinatura (Fase 4.3 do
PLANO_EXECUCAO.md; a Fase 6 é quem faz seed dos planos e a tela real).
Migração 007 já criou as tabelas com preços NULL (P6: definição futura) —
esta camada só lê o que existir, sem lógica de enforcement de limite ainda
(isso é Fase 6: services/grupos.py::adicionar_membro ganha o limite do plano
como ponto único de checagem, bot e web).
"""

from db import get_conn, _get_grupo_id


def listar_planos() -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM planos ORDER BY max_membros")
            return [dict(r) for r in cur.fetchall()]


def obter_assinatura(usuario_id: int) -> dict | None:
    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        if not gid:
            return None
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM assinaturas WHERE grupo_id = %s", (gid,))
            row = cur.fetchone()
            return dict(row) if row else None
