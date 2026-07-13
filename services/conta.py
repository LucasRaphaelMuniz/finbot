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
checkbox "entend