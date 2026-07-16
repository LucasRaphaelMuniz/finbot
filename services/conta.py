"""
services/conta.py — exclusão de conta (Fase 5.6, reescrita na Fase 7.5 / LGPD
a pedido do Lucas em 11/07/2026: "exclua todas informações da conta ...
somente o usuário master que criou pode excluir, confirmando com a senha
dele e clicando em uma flag concordando que tudo será excluído e não é
reversível").

Duas trilhas, diferentes por design — a distinção é `grupos.criador_id`
(migração 010):

1. MASTER (criou o grupo) OU conta individual (nunca teve grupo, é "dono"
   de si mesmo por definição): exclusão REAL. Apaga todo o histórico
   financeiro do grupo inteiro — gastos, entradas, despesas fixas,
   parcelamentos, importações, formas de pagamento, categorias
   customizadas, convites, assinatura — e os registros de TODOS os membros
   do grupo. Não dá pra apagar "só a parte do master" porque grande parte
   do que existe (saldo, resumo, histórico) é dado agregado do grupo, não
   dele sozinho. Também apaga o login do Supabase Auth DO MASTER (não dos
   outros membros — eles não deram esse consentimento; se algum deles
   logar de novo depois, cai no fluxo de onboarding como conta nova, sem
   nenhum dado antigo).

2. MEMBRO COMUM (tem grupo, mas não foi quem criou): comportamento antigo,
   inalterado — sai do grupo, tem nome/telefone anonimizados, mas os
   gastos/entradas que ele lançou continuam vinculados ao grupo (dado
   compartilhado, interesse legítimo dos demais membros que continuam
   usando o finbot). Login do Supabase Auth não é apagado — mesma razão:
   consentimento de "apagar tudo, sem volta" é privilégio do master.

Reautenticação por senha: o FRONTEND (finbot-web/(app)/conta/page.jsx)
continua chamando supabase.auth.signInWithPassword antes de bater nesta rota
(boa UX — erra a senha, sabe na hora sem round-trip pro backend). Mas desde
a Fase D1 do AUDITORIA_E_PLANO_CADASTRO.md (corrige F3), o BACKEND também
valida a senha server-side (providers/supabase_admin.py:verificar_senha)
antes de excluir — um JWT vazado/XSS não basta mais pra apagar a conta,
porque `excluir_conta` agora exige a senha ser conferida de novo aqui. A
checkbox "entendo que é irreversível" continua só no frontend (é UX, não
segurança — não faz sentido replicar client-side state no backend).
"""

import secrets

from db import get_conn, sair_grupo, _get_grupo_id
from providers.supabase_admin import deletar_usuario_auth, verificar_senha
from utils.app_error import AppError


def _get_criador_id(conn, grupo_id: int):
    with conn.cursor() as cur:
        cur.execute("SELECT criador_id FROM grupos WHERE id = %s", (grupo_id,))
        row = cur.fetchone()
        return row["criador_id"] if row else None


def _get_auth_user_id(usuario_id: int) -> str | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT auth_user_id FROM usuarios WHERE id = %s", (usuario_id,))
            row = cur.fetchone()
            return str(row["auth_user_id"]) if row and row["auth_user_id"] else None


def _anonimizar_usuario(usuario_id: int) -> None:
    """Comportamento antigo (membro comum) — preserva o histórico do grupo."""
    placeholder = f"excluido:{secrets.token_hex(8)}"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE usuarios SET nome = 'Conta excluída', telefone = %s, "
                "auth_user_id = NULL, parceiro_telefone = NULL WHERE id = %s",
                (placeholder, usuario_id),
            )
            conn.commit()


def _apagar_usuario_individual(usuario_id: int) -> None:
    """
    Conta sem grupo — só existe pra usuários antigos do bot que nunca
    rodaram `/grupo criar` (todo cadastro pelo web já cria um grupo de 1
    pessoa em services/onboarding.py). Apaga só os dados dele mesmo; não há
    ninguém mais envolvido.

    Ordem importa: gastos referencia compras_parceladas/despesas_fixas/
    importacoes (FK sem CASCADE) — apaga gastos primeiro pra não travar a
    remoção dessas tabelas. formas_pagamento e sessoes têm CASCADE a partir
    de usuarios, então o DELETE final já resolve as duas sem precisar de
    linha própria aqui.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM gastos WHERE usuario_id = %s", (usuario_id,))
            cur.execute("DELETE FROM compras_parceladas WHERE usuario_id = %s", (usuario_id,))
            cur.execute("DELETE FROM despesas_fixas WHERE usuario_id = %s", (usuario_id,))
            cur.execute("DELETE FROM importacoes WHERE usuario_id = %s", (usuario_id,))
            cur.execute("DELETE FROM entradas WHERE usuario_id = %s", (usuario_id,))
            cur.execute("DELETE FROM usuarios WHERE id = %s", (usuario_id,))
            conn.commit()


def _apagar_grupo_inteiro(grupo_id: int) -> None:
    """
    Exclusão pedida pelo master — apaga o grupo e TUDO que pertence a ele.

    Ordem (children antes de parents, pra não violar FK — várias dessas
    tabelas não têm ON DELETE CASCADE definido, então uma ordem errada
    aqui derruba a transação inteira com erro de integridade referencial):

    1. gastos primeiro — referencia compras_parceladas/despesas_fixas/
       importacoes/formas_pagamento; sendo o lado que referencia, sempre
       pode ser apagado primeiro sem quebrar nada.
    2. compras_parceladas, despesas_fixas, importacoes, entradas — agora
       seguro, nada mais aponta pra eles.
    3. formas_pagamento — só depois de tudo que a referenciava já ter
       sumido.
    4. convites, assinaturas — independentes entre si, mas precisam sumir
       antes de usuarios/grupos (referenciam ambos sem CASCADE).
    5. usuarios — apaga todos os membros do grupo de uma vez.
    6. grupos — por último; categorias customizadas (grupo_id) têm
       ON DELETE CASCADE desde a migração 001, somem sozinhas aqui.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM gastos WHERE grupo_id = %s", (grupo_id,))
            cur.execute("DELETE FROM compras_parceladas WHERE grupo_id = %s", (grupo_id,))
            cur.execute("DELETE FROM despesas_fixas WHERE grupo_id = %s", (grupo_id,))
            cur.execute("DELETE FROM importacoes WHERE grupo_id = %s", (grupo_id,))
            cur.execute("DELETE FROM entradas WHERE grupo_id = %s", (grupo_id,))
            cur.execute("DELETE FROM formas_pagamento WHERE grupo_id = %s", (grupo_id,))
            cur.execute("DELETE FROM convites WHERE grupo_id = %s", (grupo_id,))
            cur.execute("DELETE FROM assinaturas WHERE grupo_id = %s", (grupo_id,))
            cur.execute("DELETE FROM usuarios WHERE grupo_id = %s", (grupo_id,))
            cur.execute("DELETE FROM grupos WHERE id = %s", (grupo_id,))
            conn.commit()


def excluir_conta(usuario_id: int, email: str, senha: str) -> dict:
    """
    Ponto de entrada único, chamado por routes/conta.py.

    Fase D1 (corrige F3): valida a senha contra o Supabase Auth ANTES de
    tocar em qualquer dado — sem isso, um Bearer token vazado/roubado (XSS,
    extensão maliciosa) bastava pra apagar o grupo inteiro, porque o
    frontend fazia a reautenticação mas o backend só conferia o JWT.

    Retorna {"grupo_apagado": bool} — o frontend usa isso pra decidir a
    mensagem final ("sua conta foi anonimizada" vs "o grupo inteiro foi
    apagado").
    """
    if not senha or not verificar_senha(email, senha):
        raise AppError("Senha incorreta.", 401, "senha_invalida")

    with get_conn() as conn:
        gid = _get_grupo_id(conn, usuario_id)
        criador_id = _get_criador_id(conn, gid) if gid else None

    eh_master = (gid is None) or (criador_id == usuario_id)

    if not eh_master:
        sair_grupo(usuario_id)
        _anonimizar_usuario(usuario_id)
        return {"grupo_apagado": False}

    auth_user_id = _get_auth_user_id(usuario_id)

    if gid:
        _apagar_grupo_inteiro(gid)
    else:
        _apagar_usuario_individual(usuario_id)

    if auth_user_id:
        deletar_usuario_auth(auth_user_id)

    return {"grupo_apagado": True}


# ---------------------------------------------------------------------------
# Tutorial de primeiro login web (Fase C do AUDITORIA_E_PLANO_CADASTRO.md,
# corrige F5) — flag persistida no banco, não localStorage (sobrevive a
# troca de dispositivo/navegador).
# ---------------------------------------------------------------------------

def get_meu_status(usuario_id: int) -> dict:
    """Usado por GET /api/conta/eu — endpoint leve que o TourPrimeiroLogin
    (finbot-web) consulta ao montar o layout, sem precisar buscar o grupo
    inteiro só pra saber se já viu o tour. `tema` (migração 018) pegou
    carona aqui pelo mesmo motivo: já é consultado 1x por carregamento do
    app, não precisa de rota própria só pra isso."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tutorial_web_visto_em, tema FROM usuarios WHERE id = %s", (usuario_id,)
            )
            row = cur.fetchone()
            return {
                "tutorial_visto": bool(row and row["tutorial_web_visto_em"]),
                "tema": row["tema"] if row else "dark",
            }


def atualizar_tema(usuario_id: int, tema: str) -> dict:
    """Grava a preferência de tema na conta (não em localStorage) — pedido
    explícito do Lucas: precisa seguir o usuário entre dispositivos, não só
    o navegador onde ele clicou o toggle."""
    if tema not in ("dark", "light"):
        raise AppError("tema precisa ser 'dark' ou 'light'.", 400, "tema_invalido")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE usuarios SET tema = %s WHERE id = %s", (tema, usuario_id))
            conn.commit()
    return {"tema": tema}


def marcar_tutorial_visto(usuario_id: int, visto: bool = True) -> dict:
    """visto=False é usado pelo link "rever tutorial" da tela Conta — zera a
    flag pra o TourPrimeiroLogin aparecer de novo no próximo carregamento."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            if visto:
                cur.execute(
                    "UPDATE usuarios SET tutorial_web_visto_em = NOW() WHERE id = %s",
                    (usuario_id,),
                )
            else:
                cur.execute(
                    "UPDATE usuarios SET tutorial_web_visto_em = NULL WHERE id = %s",
                    (usuario_id,),
                )
            conn.commit()
    return {"tutorial_visto": visto}
