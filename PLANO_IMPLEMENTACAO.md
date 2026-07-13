# Plano de Execução — Finbot SaaS (roadmap completo, Fases 0–7)

## Contexto

O `PLANO_EXECUCAO.md` é o documento de design já aprovado pelo Lucas (11/07/2026): 7 fases, decisões D1–D6 adotadas, D7 (gateway) adiada, nenhuma pendência aberta. Este plano traduz aquele roadmap em execução concreta no código. O projeto hoje é Flask flat (tudo na raiz), psycopg 3 direto no Postgres (Supabase via `DATABASE_URL`), Evolution API como canal WhatsApp, OpenAI para Vision/Whisper, zero testes, deploy Railway via gunicorn/Nixpacks.

**Estilo de trabalho:** cada fase termina num checkpoint com confirmação do Lucas antes da próxima (design incremental). Migração para o padrão do `CLAUDE.md` (routes/services/providers) é incremental — módulo migra quando for tocado (D2).

**Trabalho em:** `D:\finbot` (branch nova por fase, ex.: `fase-1-parser`).

---

## Fase 0 — Benchmarking (sem código)

- Pesquisar UX de ZapGastos, Mobills, Organizze, MeuDinheiro (validar substituto do GuiaBolso, descontinuado): telas de resumo/dashboard, despesas fixas, importação de fatura.
- Entregável: `docs/benchmarking.md` — por app, 3–5 padrões observados + 1 decisão de layout derivada. Orienta Fases 5–6.
- Ferramentas: WebSearch/WebFetch.

## Fase 1 — Harness de testes + parser BR

**Bug alvo:** `_VALOR_RE` em `parser.py` (`\d{1,6}(?:[.,]\d{1,2})?`) faz `1.103,04` virar R$ 1,10.

- `requirements.txt`: + `pytest`, `pytest-mock`. Criar `pytest.ini` ou config em `pyproject.toml`.
- `tests/test_parser.py`: `"1.103,04"→1103.04`, `"50"→50.0`, `"50,90"→50.9`, `"R$ 1.234,56"→1234.56`, `"1103.04"→1103.04` (D1: `.` + exatamente 2 dígitos no fim = decimal), `"1.103"→1103.0` (milhar), valores >6 dígitos, palavras numéricas (`_palavras_para_numero` existente).
- `parser.py::extrair_valor`: reescrever com normalização BR — se tem `,`: remove `.` (milhar), troca `,`→`.`; se só `.`: decimal apenas quando seguido de exatamente 2 dígitos no fim, senão milhar.
- `tests/test_ai_valor.py`: caminho `valor` string do Vision → texto sintético → parser (onde o bug aparece com comprovantes). Mockar OpenAI.
- **Verificação:** `pytest` verde; teste manual no bot com `1.103,04`.

**Checkpoint 1** → confirmar com Lucas antes da Fase 2.

## Fase 2 — Migrações de banco (bloco único)

- Criar `database/migrations/001..007_*.sql` + runner `database/migrate.py` (tabela `schema_migrations`, aplica em ordem, idempotente). Substitui os `ALTER ... IF NOT EXISTS` improvisados do `init_db.py`.
- SQL exato já especificado no `PLANO_EXECUCAO.md` §Fase 2:
  - 001 `categorias.grupo_id` (NULL = global) + índice único `(COALESCE(grupo_id,0), LOWER(nome))`
  - 002 `formas_pagamento.dia_fechamento`
  - 003 `compras_parceladas` + `gastos.{compra_parcelada_id, parcela_num, competencia}`
  - 004 `despesas_fixas` + `gastos.despesa_fixa_id` + índice único anti-duplicação por mês
  - 005 `entradas`
  - 006 `usuarios.auth_user_id` (UUID) + `convites`
  - 007 `planos` + `assinaturas`
- Backfill: `UPDATE gastos SET competencia = DATE_TRUNC('month', data) WHERE competencia IS NULL`.
- **Verificação:** rodar `migrate.py` em banco de dev/staging (não direto em produção — combinar com Lucas como testar), conferir schema, rodar bot existente sem regressão.

**Checkpoint 2.**

## Fase 3 — Regras de negócio no Flask (migração incremental p/ services/)

Ordem interna: 3.1 categorias → 3.2 parcelamento → 3.3 fixas → 3.5 entradas → 3.4 onboarding → 3.6 fallback IA.

- **3.1 Categorias por grupo:** `services/categorias.py` (`get_categorias(grupo_id)` = grupo + globais); comandos `categoria add/remover/listar` em `handler.py`; `_CAT_ALIASES` vira fallback das globais; `ai.py::_PROMPT_COMPROVANTE` recebe lista dinâmica; `comandos.py::cmd_ajuda` atualizado. Globais nunca somem, grupo só oculta (G5).
- **3.2 Parcelamento:** `parser.py` detecta `3x`/`em 3 vezes`/`parcelado em 3`; `services/parcelamento.py` cria compra + N gastos com `parcela_num` e `competencia` pelo `dia_fechamento` (após fechamento → competência seguinte; divisão arredondada, resíduo na 1ª); confirmação "12x de R$ 91,92, 1ª em Agosto"; `excluir ultimo` em parcela → sessão pergunta "só esta × compra inteira" (D3). **Trocar filtros `DATE_TRUNC('month', g.data)` por `competencia` em `db.py` (saldo/resumo)** — muda resultados existentes (P2 aceito), cobrir com testes sobre histórico backfillado.
- **3.3 Despesas fixas:** `services/despesas_fixas.py`; comandos `fixa add Aluguel 1200 dia 5` / `fixa listar` / `fixa remover`; `jobs/lancar_fixas.py` idempotente (protegido pelo índice único), agendado por cron do Railway (D4).
- **3.5 Entradas:** `parser.py` detecta `recebi/entrada/salário/caiu/ganhei` antes do fluxo de gasto; comando `entrada 2000 salário`; `services/entradas.py`; entrada não afeta saldo por forma; `cmd_resumo` ganha linha "Entradas do mês".
- **3.4 Onboarding:** anexar tutorial completo (hoje só em `_tutorial_grupo`) ao final de `_onboarding_resumo` (D5 — manter fluxo guiado).
- **3.6 Fallback IA:** mensagem sem comando/valor → atalho barato primeiro (fuzzy "ajuda" etc.), senão classificação de intenção via OpenAI; gasto deduzido cria sessão `aguardando_confirmacao_ia` (timeout 5 min nativo de `sessoes` já garante cancelamento seguro); só `sim/confirmar` insere.
- **Testes:** `test_parcelamento.py`, `test_despesas_fixas.py` (idempotência), `test_entradas.py`, `test_fallback.py` (nada inserido sem confirmação).
- **Verificação:** pytest + teste manual no WhatsApp de cada fluxo.

**Checkpoint 3** (fase grande — pode ter sub-checkpoints por item, a combinar).

## Fase 4 — Front Next.js + API Flask

- **Backend primeiro:** Blueprints `/api/*` (padrão CLAUDE.md: rota fina → service) conforme tabela do §4.3 do PLANO (onboarding, convites, gastos, entradas, fixas, categorias, formas, grupo, resumo, importação, planos). `middlewares/ensure_authenticated.py` valida JWT do Supabase via JWKS e resolve `usuario`/`grupo_id`; `utils/app_error.py` + errorhandler central; CORS restrito; paginação `?page=&per_page=50`; JSON com `number` ponto decimal (formatação BR no front).
- **Front `finbot-web/`:** Next.js App Router, estrutura exata do §4.1 (rotas `(auth)`: login, cadastro c/ `?convite=`, recuperar/redefinir senha, `convite/[codigo]`; rotas `(app)`: dashboard, lancamentos, fixas, importacao, grupo, formas, categorias, planos, conta). supabase-js **só para auth** (D6); dados via API Flask (`services/api.js` axios + JWT + redirect 401). styled-components, componentes com pasta própria `index.jsx` + `styles.js`.
- **Auth:** fluxos da tabela §4.2 — cadastro sem convite cria grupo+usuário via `POST /api/onboarding`; com convite vincula ao grupo existente via `POST /api/convites/aceitar`; vínculo só-bot por telefone continua funcionando.
- **Antecipar segurança de F7 (bloqueia lançamento):** RLS por `grupo_id` em todas as tabelas de dados + validação apikey/HMAC no `/webhook`.
- **Verificação:** cadastro→onboarding→login→chamada autenticada de ponta a ponta; convite aceito vincula ao grupo certo; 401 sem token.

**Checkpoint 4.**

## Fase 5 — Telas web

Conforme §5.1–5.6 do PLANO, layout orientado pelo `docs/benchmarking.md`. Todas com EmptyState/skeleton/Toast.

- `/lancamentos`: abas Gastos|Entradas, filtros (MesPicker por competência, categoria, forma, membro), DataTable com badge de origem, editar/excluir (parcela → "só esta × compra inteira"), modal "Novo lançamento" com toggle e "parcelado em N×".
- `/dashboard`: StatCards (entradas, gastos, saldo, % limites) + donut por categoria + barras 6 meses + fixo×variável — tudo de 1 request `GET /api/resumo` (agregação no Flask), Recharts.
- `/importacao`: upload PDF/CSV → parse no Flask (CSV determinístico; PDF via OpenAI, prompt novo em `ai.py`) → tabela de revisão editável com duplicatas destacadas → confirmação explícita em lote + desfazer por `importacao_id`. Migração extra: tabela `importacoes` + `gastos.importacao_id` (adicionar como `008_importacoes.sql`).
- `/grupo`, `/formas` (com `dia_fechamento` e aviso de competência), `/categorias` (globais = "padrão", ocultável, não deletável), `/conta` (perfil, senha, exclusão LGPD).
- **Verificação:** Jest/RTL nas rotas críticas (revisão de fatura) + navegação manual via browser.

**Checkpoint 5.**

## Fase 6 — Estrutura SaaS (sem gateway — P5)

- Seed `planos` (basic 1 / plus 2 / master 5 / unlimited 10 soft), preços NULL (P6).
- `/planos`: cards, plano atual destacado, contratação desabilitada ("em breve"). Sem checkout; `assinaturas.gateway_*` nulos, status manual.
- Enforcement de limite num único ponto: `services/grupos.py::adicionar_membro` (bot **e** web).
- Downgrade (P3): web exige escolher quem sai; excedentes bloqueados de registrar no bot com mensagem.
- **Verificação:** teste de limite (adicionar membro além do plano falha nos dois canais); fluxo de downgrade.

**Checkpoint 6.**

## Fase 7 — Hardening pré-lançamento

- Duplicata de comprovante: mover `app.py::_cupons_recentes` (memória, quebra com 2 workers gunicorn) para tabela/constraint.
- Rate limiting por telefone; logs estruturados no lugar de `print`.
- **Remover `notificar.py`** (P4 — Twilio fora; canal segue Evolution API). Obs: `twilio` nem está no `requirements.txt`, é código morto seguro de remover.
- Grupos `@g.us`: filtro barato antes de acionar fallback IA/Vision/Whisper (mitigação de custo).
- Política de privacidade + exclusão de conta (LGPD).
- (Webhook auth e RLS já antecipados na Fase 4.)
- **Verificação:** suíte completa pytest + Jest; teste de carga leve no webhook; checklist de segurança.

---

## Referências fixas

- Design/decisões: `PLANO_EXECUCAO.md` (SQL das migrações no §Fase 2; contrato da API no §4.3; telas no §5).
- Convenções de código: `CLAUDE.md` (Blueprints finos → services, `utils/app_error.py`, providers para integrações, front com pasta por componente).
- Módulos atuais (flat, migram quando tocados): `app.py`, `handler.py`, `parser.py`, `db.py`, `ai.py`, `comandos.py`, `sessao.py`, `init_db.py`.

## Fluxo de trabalho

1 branch por fase; pytest verde antes de cada checkpoint; nada aplicado em banco de produção sem combinar; commit/push só quando Lucas pedir. Começar pela **Fase 0** (ou direto na 1, se Lucas preferir pular o benchmarking por ora — perguntar no início da execução).
