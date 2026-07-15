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
            # auth_user_id nesse registro. Verificação acima já garante que
            # quem está pedindo isso realmente tem o WhatsApp em mãos.
            cur.execute("SELECT * FROM usuarios WHERE telefone = %s", (telefone,))
            usuario_row = cur.fetchone()

            veio_do_bot = usuario_row is not None

            if usuario_row:
                cur.execute(
                    "UPDATE usuarios SET auth_user_id = %s WHERE id = %s RETURNING *",
                    (auth_user_id, usuario_row["id"]),
                )
                usuario = dict(cur.fetchone())
            else:
                # F6: dois requests concorrentes (duplo clique) podem passar
                # ambos pelo SELECT de `existente` sem achar nada — ON CONFLICT
                # + re-select evita o 500 de UniqueViolation em auth_user_id
                # que acontecia antes (o segundo request recebe o registro que
                # o primeiro acabou de criar, em vez de derrubar).
                cur.execute(
                    "INSERT INTO usuarios (nome, telefone, auth_user_id) VALUES (%s, %s, %s) "
                    "ON CONFLICT (auth_user_id) DO NOTHING RETURNING *",
                    (nome or telefone, telefone, auth_user_id),
                )
                row = cur.fetchone()
                if not row:
                    cur.execute("SELECT * FROM usuarios WHERE auth_user_id = %s", (auth_user_id,))
                    row = cur.fetchone()
                usuario = dict(row)

            uid = usuario["id"]

            # Grupo só é criado se o usuário (novo ou reaproveitado do bot)
            # ainda não tiver um — cobre os 3 cenários do B3: número novo,
            # número do bot sem grupo (ambos precisam de nome_grupo), e
            # número do bot COM grupo (não entra aqui, nome_grupo é ignorado
            # de propósito — o grupo já existe, é o "puxa tudo" do merge).
            if not usuario.get("grupo_id"):
                if not nome_grupo:
                    raise AppError(
                        "Nome do grupo é obrigatório para criar uma conta nova.",
                        400, "campos_obrigatorios",
                    )
                # criador_id (migração 010) marca quem pode apagar o grupo
                # inteiro depois — ver services/conta.py.
                cur.execute(
                    "INSERT INTO grupos (nome, criador_id) VALUES (%s, %s) RETURNING *",
                    (nome_grupo, uid),
                )
                grupo = dict(cur.fetchone())
                cur.execute(
                    "UPDATE usuarios SET grupo_id = %s WHERE id = %s", (grupo["id"], uid)
                )
                usuario["grupo_id"] = grupo["id"]

                for nome_forma, limite in FORMAS_PADRAO:
                    cur.execute(
                        "INSERT INTO formas_pagamento (usuario_id, grupo_id, nome, limite_mensal) "
                        "VALUES (%s, %s, %s, %s)",
                        (uid, grupo["id"], nome_forma, limite),
                    )

            conn.commit()
            usuario["veio_do_bot"] = veio_do_bot

            if veio_do_bot:
                # Defesa em profundidade do F2 (a pessoa fica sabendo se
                # alguém vinculou aquele número) + tutorial reverso (Fase C3).
                enviar_mensagem(
                    telefone,
                    "✅ Sua conta web foi vinculada a este número.\n"
                    "Seus registros (gastos, grupo, formas de pagamento) já aparecem no site.",
                )

            return usuario
