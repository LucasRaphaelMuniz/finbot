"""
services/onboarding.py — Fase 4.3 do PLANO_EXECUCAO.md, revisado na Fase B
do AUDITORIA_E_PLANO_CADASTRO.md (OTP + merge seguro).

Completa o cadastro de quem se autenticou via Supabase Auth (web) mas ainda
não tem `usuarios`/`grupos` correspondente no banco do finbot. Espelha a
1ª etapa do onboarding do bot (handler.py:_processar_onboarding), mas sem o
vai-e-vem conversacional — o front já manda telefone (e, se for o caso,
nome_grupo) prontos (ver finbot-web/components/CompletarCadastro, Fase B3).
"""

from db import get_conn, FORMAS_PADRAO
from providers.evolution import enviar_mensagem
from services.verificacao import esta_verificado
from utils.app_error import AppError
from utils.telefone import normalizar as normalizar_telefone


def completar_onboarding(auth_user_id: str, nome: str, nome_grupo: str, telefone: str) -> dict:
    """
    Idempotente: se já existe usuario com esse auth_user_id, retorna o
    existente em vez de duplicar (protege contra o front chamar 2x —
    F5/duplo clique enquanto o request anterior ainda está em voo).

    Telefone é normalizado pro mesmo formato JID que o bot usa (Fase A do
    AUDITORIA_E_PLANO_CADASTRO.md, corrige F1).

    Fase B (corrige F2): antes de qualquer merge, exige que o par
    (auth_user_id, telefone) tenha uma verificação de posse confirmada
    (services/verificacao.py) — sem isso, bastaria digitar o número de
    outra pessoa aqui pra herdar o histórico financeiro dela. A exigência
    vale MESMO para número novo (sem usuario existente): evita registrar de
    saída um número de terceiro que só futuramente usaria o bot.

    No merge (usuario já existia via bot), o cadastro do bot é a fonte de
    verdade do que já foi parametrizado — `nome_grupo` do formulário é
    ignorado nesse caminho (nem é exigido). Ao concluir o merge, o backend
    manda uma mensagem proativa pelo bot confirmando o vínculo — defesa em
    profundidade do F2 (a pessoa fica sabendo se alguém vinculou aquele
    número) e fecha o ciclo do tutorial (Fase C3).
    """
    nome = (nome or "").strip()
    nome_grupo = (nome_grupo or "").strip()
    telefone = normalizar_telefone(telefone)
    if not telefone:
        raise AppError("Um WhatsApp válido (com DDD) é obrigatório.", 400, "campos_obrigatorios")

    if not esta_verificado(auth_user_id, telefone):
        raise AppError(
            "Confirme a posse deste WhatsApp antes de continuar (código de verificação).",
            403, "telefone_nao_verificado",
        )

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM usuarios WHERE auth_user_id = %s", (auth_user_id,))
            existente = cur.fetchone()
            if existente:
                return dict(existente)

            # Reaproveita usuario pré-existente pelo telefone (já usava o bot
            # antes de criar conta web) em vez de duplicar — só linka o
            #