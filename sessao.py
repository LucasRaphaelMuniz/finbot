from datetime import datetime, timezone, timedelta
from db import supabase


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _expira() -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()


def get_sessao_ativa(usuario_id: int):
    """Retorna a sessão ativa (não expirada) mais recente ou None."""
    res = supabase.table("sessoes").select("*") \
        .eq("usuario_id", usuario_id) \
        .gt("expira_em", _now()) \
        .order("criado_em", desc=True) \
        .limit(1) \
        .execute()
    return res.data[0] if res.data else None


def criar_sessao(usuario_id: int, etapa: str,
                 valor_temp=None, categoria_temp=None, forma_temp=None):
    """Deleta sessão existente e cria nova com timeout de 5 minutos."""
    deletar_sessao(usuario_id)
    supabase.table("sessoes").insert({
        "usuario_id": usuario_id,
        "etapa": etapa,
        "valor_temp": valor_temp,
        "categoria_temp": categoria_temp,
        "forma_temp": forma_temp,
        "expira_em": _expira(),
    }).execute()


def atualizar_sessao(usuario_id: int, etapa: str = None,
                     categoria_temp=None, forma_temp=None):
    """Atualiza campos da sessão ativa e renova o timeout."""
    updates: dict = {"expira_em": _expira()}
    if etapa is not None:
        updates["etapa"] = etapa
    if categoria_temp is not None:
        updates["categoria_temp"] = categoria_temp
    if forma_temp is not None:
        updates["forma_temp"] = forma_temp

    supabase.table("sessoes").update(updates) \
        .eq("usuario_id", usuario_id) \
        .gt("expira_em", _now()) \
        .execute()


def deletar_sessao(usuario_id: int):
    supabase.table("sessoes").delete().eq("usuario_id", usuario_id).execute()


def verificar_sessao_expirada(usuario_id: int) -> bool:
    """Retorna True (e deleta) se existe sessão expirada. False se não há nada."""
    res = supabase.table("sessoes").select("id") \
        .eq("usuario_id", usuario_id) \
        .lte("expira_em", _now()) \
        .limit(1) \
        .execute()
    if res.data:
        deletar_sessao(usuario_id)
        return True
    return False
