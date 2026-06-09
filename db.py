import os
from datetime import datetime, timezone
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY"),
)

FORMAS_PADRAO = [
    ("Cartão",       3000.00),
    ("Pix/Dinheiro", 1500.00),
    ("Ticket",        600.00),
]


def _inicio_mes() -> str:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


# ---------------------------------------------------------------------------
# Usuários
# ---------------------------------------------------------------------------

def get_or_create_usuario(telefone: str):
    """Retorna (usuario_dict, is_new). Cria formas de pagamento padrão no 1.º acesso."""
    res = supabase.table("usuarios").select("*").eq("telefone", telefone).execute()
    if res.data:
        return res.data[0], False

    novo = supabase.table("usuarios").insert({"nome": telefone, "telefone": telefone}).execute().data[0]
    uid = novo["id"]

    for nome, limite in FORMAS_PADRAO:
        supabase.table("formas_pagamento").insert({
            "usuario_id": uid,
            "nome": nome,
            "limite_mensal": limite,
        }).execute()

    return novo, True


# ---------------------------------------------------------------------------
# Categorias e formas de pagamento
# ---------------------------------------------------------------------------

def get_categorias():
    return supabase.table("categorias").select("*").order("nome").execute().data


def get_formas_pagamento(usuario_id: int):
    return supabase.table("formas_pagamento").select("*").eq("usuario_id", usuario_id).order("nome").execute().data


# ---------------------------------------------------------------------------
# Gastos
# ---------------------------------------------------------------------------

def registrar_gasto(usuario_id: int, forma_id: int, categoria_id: int,
                    valor: float, descricao: str):
    res = supabase.table("gastos").insert({
        "usuario_id": usuario_id,
        "forma_pagamento_id": forma_id,
        "categoria_id": categoria_id,
        "valor": valor,
        "descricao": descricao,
    }).execute()
    return res.data[0]


# ---------------------------------------------------------------------------
# Saldo
# ---------------------------------------------------------------------------

def get_saldo_forma(usuario_id: int, forma_id: int):
    """Retorna dict com gasto_mes, limite_mensal, nome."""
    fp_res = supabase.table("formas_pagamento").select("*").eq("id", forma_id).eq("usuario_id", usuario_id).execute()
    if not fp_res.data:
        return None
    fp = fp_res.data[0]

    gastos = supabase.table("gastos").select("valor") \
        .eq("forma_pagamento_id", forma_id) \
        .eq("usuario_id", usuario_id) \
        .gte("data", _inicio_mes()) \
        .execute().data

    gasto_mes = sum(g["valor"] for g in gastos)
    return {"nome": fp["nome"], "limite_mensal": fp["limite_mensal"], "gasto_mes": gasto_mes}


def get_saldo_todas_formas(usuario_id: int):
    fps = supabase.table("formas_pagamento").select("*").eq("usuario_id", usuario_id).order("nome").execute().data
    gastos = supabase.table("gastos").select("valor, forma_pagamento_id") \
        .eq("usuario_id", usuario_id) \
        .gte("data", _inicio_mes()) \
        .execute().data

    gastos_por_forma: dict[int, float] = {}
    for g in gastos:
        fid = g["forma_pagamento_id"]
        gastos_por_forma[fid] = gastos_por_forma.get(fid, 0) + g["valor"]

    return [{
        "id": fp["id"],
        "nome": fp["nome"],
        "limite_mensal": fp["limite_mensal"],
        "gasto_mes": gastos_por_forma.get(fp["id"], 0),
    } for fp in fps]


# ---------------------------------------------------------------------------
# Resumo mensal
# ---------------------------------------------------------------------------

def get_resumo_mes(usuario_id: int):
    gastos = supabase.table("gastos") \
        .select("valor, categorias(nome), formas_pagamento(nome)") \
        .eq("usuario_id", usuario_id) \
        .gte("data", _inicio_mes()) \
        .execute().data

    totais: dict[tuple, float] = {}
    for g in gastos:
        key = (g["categorias"]["nome"], g["formas_pagamento"]["nome"])
        totais[key] = totais.get(key, 0) + g["valor"]

    resultado = [{"categoria": k[0], "forma": k[1], "total": v} for k, v in totais.items()]
    return sorted(resultado, key=lambda x: x["total"], reverse=True)


# ---------------------------------------------------------------------------
# Limite
# ---------------------------------------------------------------------------

def atualizar_limite(usuario_id: int, forma_nome: str, novo_limite: float) -> bool:
    res = supabase.table("formas_pagamento") \
        .update({"limite_mensal": novo_limite}) \
        .eq("usuario_id", usuario_id) \
        .ilike("nome", f"%{forma_nome}%") \
        .execute()
    return len(res.data) > 0


# ---------------------------------------------------------------------------
# Parceiro (notificações)
# ---------------------------------------------------------------------------

def get_usuario(usuario_id: int):
    res = supabase.table("usuarios").select("*").eq("id", usuario_id).execute()
    return res.data[0] if res.data else None


def get_parceiro_telefone(usuario_id: int):
    res = supabase.table("usuarios").select("parceiro_telefone").eq("id", usuario_id).execute()
    if res.data:
        return res.data[0].get("parceiro_telefone")
    return None


def set_parceiro_telefone(usuario_id: int, telefone: str):
    supabase.table("usuarios").update({"parceiro_telefone": telefone}).eq("id", usuario_id).execute()
