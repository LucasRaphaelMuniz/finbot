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


def _grupo_de(usuario_id: int):
    """Retorna o grupo_id do usuário ou None."""
    res = supabase.table("usuarios").select("grupo_id").eq("id", usuario_id).execute()
    return res.data[0].get("grupo_id") if res.data else None


def _filtro_escopo(query, usuario_id: int, grupo_id):
    """Filtra pelo grupo (contas compartilhadas) ou, sem grupo, pelos dados pessoais."""
    if grupo_id:
        return query.eq("grupo_id", grupo_id)
    return query.eq("usuario_id", usuario_id).is_("grupo_id", "null")


# ---------------------------------------------------------------------------
# Usuários
# ---------------------------------------------------------------------------

def _variantes_telefone(telefone: str) -> list:
    """Variantes de número BR com/sem o nono dígito (whatsapp:+55DD9XXXXXXXX ↔ whatsapp:+55DDXXXXXXXX)."""
    variantes = [telefone]
    prefixo = "whatsapp:+55"
    if telefone.startswith(prefixo):
        resto = telefone[len(prefixo):]
        if len(resto) == 11 and resto[2] == "9":
            variantes.append(prefixo + resto[:2] + resto[3:])
        elif len(resto) == 10:
            variantes.append(prefixo + resto[:2] + "9" + resto[2:])
    return variantes


def buscar_usuario_por_telefone(telefone: str):
    """Busca usuário pelo telefone exato ou pela variante BR com/sem nono dígito."""
    for t in _variantes_telefone(telefone):
        res = supabase.table("usuarios").select("*").eq("telefone", t).execute()
        if res.data:
            return res.data[0]
    return None


def get_or_create_usuario(telefone: str):
    """Retorna (usuario_dict, is_new). Cria formas de pagamento padrão no 1.º acesso."""
    usuario = buscar_usuario_por_telefone(telefone)
    if usuario:
        if usuario["telefone"] != telefone:
            # Cadastro veio de "grupo add" com a variante do nono dígito;
            # o From do Twilio é o endereço real para envio de notificações.
            supabase.table("usuarios").update({"telefone": telefone}).eq("id", usuario["id"]).execute()
            usuario["telefone"] = telefone
        return usuario, False

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
    gid = _grupo_de(usuario_id)
    q = supabase.table("formas_pagamento").select("*")
    return _filtro_escopo(q, usuario_id, gid).order("nome").execute().data


# ---------------------------------------------------------------------------
# Gastos
# ---------------------------------------------------------------------------

def registrar_gasto(usuario_id: int, forma_id: int, categoria_id: int,
                    valor: float, descricao: str, grupo_id: int = None):
    res = supabase.table("gastos").insert({
        "usuario_id": usuario_id,
        "forma_pagamento_id": forma_id,
        "categoria_id": categoria_id,
        "valor": valor,
        "descricao": descricao,
        "grupo_id": grupo_id,
    }).execute()
    return res.data[0]


# ---------------------------------------------------------------------------
# Saldo
# ---------------------------------------------------------------------------

def get_saldo_forma(usuario_id: int, forma_id: int):
    """Retorna dict com gasto_mes, limite_mensal, nome. Soma gastos de todo o grupo, se houver."""
    gid = _grupo_de(usuario_id)
    fp_res = supabase.table("formas_pagamento").select("*").eq("id", forma_id).execute()
    if not fp_res.data:
        return None
    fp = fp_res.data[0]

    q = supabase.table("gastos").select("valor") \
        .eq("forma_pagamento_id", forma_id) \
        .gte("data", _inicio_mes())
    gastos = _filtro_escopo(q, usuario_id, gid).execute().data

    gasto_mes = sum(g["valor"] for g in gastos)
    return {"nome": fp["nome"], "limite_mensal": fp["limite_mensal"], "gasto_mes": gasto_mes}


def get_saldo_todas_formas(usuario_id: int):
    gid = _grupo_de(usuario_id)
    fps = _filtro_escopo(supabase.table("formas_pagamento").select("*"), usuario_id, gid) \
        .order("nome").execute().data
    gastos = _filtro_escopo(
        supabase.table("gastos").select("valor, forma_pagamento_id"), usuario_id, gid
    ).gte("data", _inicio_mes()).execute().data

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
    gid = _grupo_de(usuario_id)
    q = supabase.table("gastos") \
        .select("valor, categorias(nome), formas_pagamento(nome)") \
        .gte("data", _inicio_mes())
    gastos = _filtro_escopo(q, usuario_id, gid).execute().data

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
    gid = _grupo_de(usuario_id)
    q = supabase.table("formas_pagamento") \
        .update({"limite_mensal": novo_limite}) \
        .ilike("nome", f"%{forma_nome}%")
    res = _filtro_escopo(q, usuario_id, gid).execute()
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


def set_nome_usuario(usuario_id: int, nome: str):
    supabase.table("usuarios").update({"nome": nome}).eq("id", usuario_id).execute()


# ---------------------------------------------------------------------------
# Formas de pagamento — gerenciamento
# ---------------------------------------------------------------------------

def adicionar_forma_pagamento(usuario_id: int, nome: str, limite: float = None):
    supabase.table("formas_pagamento").insert({
        "usuario_id": usuario_id,
        "nome": nome,
        "limite_mensal": limite,
        "grupo_id": _grupo_de(usuario_id),
    }).execute()


def remover_forma_pagamento(usuario_id: int, nome_forma: str) -> bool:
    gid = _grupo_de(usuario_id)
    q = supabase.table("formas_pagamento") \
        .delete() \
        .ilike("nome", f"%{nome_forma}%")
    res = _filtro_escopo(q, usuario_id, gid).execute()
    return len(res.data) > 0


# ---------------------------------------------------------------------------
# Grupos (contas compartilhadas)
# ---------------------------------------------------------------------------

def get_grupo(grupo_id: int):
    res = supabase.table("grupos").select("*").eq("id", grupo_id).execute()
    return res.data[0] if res.data else None


def get_membros_grupo(grupo_id: int):
    return supabase.table("usuarios").select("*").eq("grupo_id", grupo_id).order("id").execute().data


def criar_grupo(usuario_id: int, nome: str):
    """Cria o grupo e move as contas do criador (formas e gastos) para ele."""
    grupo = supabase.table("grupos").insert({"nome": nome}).execute().data[0]
    gid = grupo["id"]
    supabase.table("usuarios").update({"grupo_id": gid}).eq("id", usuario_id).execute()
    supabase.table("formas_pagamento").update({"grupo_id": gid}) \
        .eq("usuario_id", usuario_id).is_("grupo_id", "null").execute()
    supabase.table("gastos").update({"grupo_id": gid}) \
        .eq("usuario_id", usuario_id).is_("grupo_id", "null").execute()
    return grupo


def adicionar_membro_grupo(grupo_id: int, telefone: str):
    """Adiciona o usuário do telefone ao grupo, criando-o se necessário.

    Retorna (usuario, ja_estava_em_grupo). Membros novos não recebem formas
    padrão — passam a usar as contas do grupo.
    """
    usuario = buscar_usuario_por_telefone(telefone)
    if usuario:
        if usuario.get("grupo_id"):
            return usuario, True
        supabase.table("usuarios").update({"grupo_id": grupo_id}).eq("id", usuario["id"]).execute()
        return usuario, False

    usuario = supabase.table("usuarios").insert({
        "nome": telefone,
        "telefone": telefone,
        "grupo_id": grupo_id,
    }).execute().data[0]
    return usuario, False


def sair_grupo(usuario_id: int):
    """Remove o usuário do grupo e restaura formas padrão se ele ficou sem nenhuma."""
    supabase.table("usuarios").update({"grupo_id": None}).eq("id", usuario_id).execute()
    pessoais = supabase.table("formas_pagamento").select("id") \
        .eq("usuario_id", usuario_id).is_("grupo_id", "null").execute().data
    if not pessoais:
        for nome, limite in FORMAS_PADRAO:
            supabase.table("formas_pagamento").insert({
                "usuario_id": usuario_id,
                "nome": nome,
                "limite_mensal": limite,
            }).execute()


# ---------------------------------------------------------------------------
# Gastos — gerenciamento
# ---------------------------------------------------------------------------

def get_ultimos_gastos(usuario_id: int, limit: int = 5):
    return supabase.table("gastos") \
        .select("id, valor, data, categorias(nome), formas_pagamento(nome)") \
        .eq("usuario_id", usuario_id) \
        .order("data", desc=True) \
        .limit(limit) \
        .execute().data


def excluir_ultimo_gasto(usuario_id: int):
    res = supabase.table("gastos") \
        .select("id, valor, categorias(nome), formas_pagamento(nome)") \
        .eq("usuario_id", usuario_id) \
        .order("data", desc=True) \
        .limit(1) \
        .execute()
    if not res.data:
        return None
    gasto = res.data[0]
    supabase.table("gastos").delete().eq("id", gasto["id"]).execute()
    return gasto


def editar_ultimo_gasto_valor(usuario_id: int, novo_valor: float) -> bool:
    res = supabase.table("gastos") \
        .select("id") \
        .eq("usuario_id", usuario_id) \
        .order("data", desc=True) \
        .limit(1) \
        .execute()
    if not res.data:
        return False
    supabase.table("gastos").update({"valor": novo_valor}).eq("id", res.data[0]["id"]).execute()
    return True
