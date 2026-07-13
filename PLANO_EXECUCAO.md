# Plano de Execução — Finbot SaaS

> Baseado em `finbot-saas-prompt-final.md` + análise do código atual (11/07/2026).
> Documento de planejamento — nada foi alterado no código.

---

## 1. Diagnóstico do código atual (o que o plano precisa considerar)

| Item do escopo | Estado atual no código |
|---|---|
| Parser numérico | **Bug confirmado**: `_VALOR_RE` em `parser.py:8` captura `\d{1,6}([.,]\d{1,2})?` e troca `,`→`.`. Input `1.103,04` casa `"1.10"` → registra **R$ 1,10**. Também falha em `1.103` (milhar) e em valores > 6 dígitos. |
| Categorias | **Globais**: tabela `categorias(id, nome UNIQUE)` sem `grupo_id`. `get_categorias()` (db.py:93) retorna tudo. Aliases hardcoded em `parser.py:_CAT_ALIASES` e lista hardcoded no prompt Vision (`ai.py:_PROMPT_COMPROVANTE`). |
| Parcelamento | Inexistente. `gastos` não tem campos de parcela. |
| Despesas fixas / data de corte | Inexistente. `formas_pagamento` não tem `dia_fechamento`. Não há scheduler. |
| Onboarding | **Já existe** fluxo guiado completo (`handler.py:_processar_onboarding`): nome → grupo → membros → formas. O MD trata como inexistente — o que falta é o *tutorial fixo* estilo `_tutorial_grupo()` no fim, não o onboarding em si. |
| Fallback IA + timeout 5min | Timeout já existe (`sessoes.expira_em`, default 5 min; sessão expirada nunca insere nada — comportamento já é "cancelamento seguro"). O que **não** existe: IA interpretando comando não reconhecido e etapa de confirmação explícita. Hoje comando não reconhecido cai em `_processar_input_livre`. |
| Grupo familiar ≠ grupo WhatsApp | Modelo de dados já é independente (`grupos` no banco, vínculo por telefone via `vincular`/`grupo add`). `app.py` inclusive responde dentro de grupos reais de WhatsApp (`@g.us`) — ver gap G7. |
| Entradas/receitas | **Inexistente**. Só há `gastos`. O MD pede CRUD de "despesas/entradas" no web, mas o backend não tem o conceito. |
| Web / Auth | Inexistente. `usuarios` não tem e-mail/senha (só telefone). |
| SaaS / planos | Inexistente. |
| Testes | Zero testes. Nenhuma dependência de teste em `requirements.txt`. |
| Código morto | `notificar.py` usa Twilio, mas `twilio` não está em `requirements.txt` e nada importa o módulo — canal ativo é Evolution API. Remover ou reativar conscientemente. |

---

## 2. Roadmap por fases

Ordem pensada para: (a) destravar risco cedo (parser + testes antes de tudo), (b) migrações de banco em bloco único antes das regras, (c) web só depois do backend estável, (d) monetização por último, sobre base multi-tenant já endurecida.

### Fase 0 — Benchmarking de mercado (sem código)

**Objetivo:** síntese curta de UX de ZapGastos (principal), Mobills, Organizze, GuiaBolso*, MeuDinheiro para orientar layout das Fases 5–6.

*GuiaBolso foi descontinuado/absorvido pelo PicPay — validar se ainda serve como referência ou substituir (ex.: Mobizzy, Wallet).

- Escopo: telas de **resumo/dashboard**, **cadastro de despesas fixas**, **importação de fatura**.
- Entregável: `docs/benchmarking.md` — por app: 3-5 padrões observados + 1 decisão de layout derivada.
- Arquivos do projeto: nenhum.

### Fase 1 — Harness de testes + correção do parser

**Objetivo:** pytest instalado e parser corrigido com testes cobrindo formato brasileiro, antes de mexer em qualquer regra de negócio.

- `requirements.txt`: adicionar `pytest` (e `pytest-mock`).
- Criar `tests/test_parser.py`: casos `"1.103,04"→1103.04`, `"50"→50.0`, `"50,90"→50.9`, `"R$ 1.234,56"→1234.56`, `"1103.04"→1103.04` (ambíguo — ver decisão D1), palavras numéricas, valores com mais de 6 dígitos.
- `parser.py`: reescrever `extrair_valor` com normalização BR explícita:
  - `,` presente → `,` é decimal, `.` é milhar (remove pontos, troca vírgula).
  - só `.` → decidir por heurística (D1).
- `ai.py`: o prompt Vision já pede formato correto, mas adicionar teste do caminho `valor` string → `texto_sintetico` → parser (é onde o bug se manifesta com comprovantes).
- Aproveitar a fase para iniciar a estrutura do `CLAUDE.md`: criar `tests/` e mover parser para `services/parser.py` **ou** manter flat e migrar na Fase 3 (decisão D2).

**Tabelas:** nenhuma.

### Fase 2 — Migrações de banco (bloco único)

**Objetivo:** todo `CREATE/ALTER` necessário pelas fases 3–6 num único conjunto de migrações versionadas, para não ficar alterando schema a cada fase.

- Criar `database/migrations/` com arquivos SQL numerados (`001_categorias_por_grupo.sql`, ...) + runner simples em `database/migrate.py` (substitui a seção de `ALTER` improvisada do `init_db.py`).

Migrações:

```sql
-- 001: categorias por grupo
ALTER TABLE categorias ADD COLUMN grupo_id INT REFERENCES grupos(id) ON DELETE CASCADE;
ALTER TABLE categorias DROP CONSTRAINT categorias_nome_key;
CREATE UNIQUE INDEX uq_categoria_grupo_nome ON categorias (COALESCE(grupo_id, 0), LOWER(nome));
-- categorias com grupo_id NULL = padrão global (fallback)

-- 002: fechamento de cartão por forma de pagamento
ALTER TABLE formas_pagamento ADD COLUMN dia_fechamento SMALLINT
    CHECK (dia_fechamento BETWEEN 1 AND 31);

-- 003: parcelamento
CREATE TABLE compras_parceladas (
    id SERIAL PRIMARY KEY,
    usuario_id INT REFERENCES usuarios(id),
    grupo_id INT REFERENCES grupos(id),
    forma_pagamento_id INT REFERENCES formas_pagamento(id),
    categoria_id INT REFERENCES categorias(id),
    descricao TEXT,
    valor_total DECIMAL NOT NULL,
    parcelas INT NOT NULL,
    data_compra DATE DEFAULT NOW()
);
ALTER TABLE gastos ADD COLUMN compra_parcelada_id INT REFERENCES compras_parceladas(id);
ALTER TABLE gastos ADD COLUMN parcela_num INT;
ALTER TABLE gastos ADD COLUMN competencia DATE;  -- mês a que o gasto pertence (≠ data)

-- 004: despesas fixas
CREATE TABLE despesas_fixas (
    id SERIAL PRIMARY KEY,
    grupo_id INT REFERENCES grupos(id),
    usuario_id INT REFERENCES usuarios(id),
    categoria_id INT REFERENCES categorias(id),
    forma_pagamento_id INT REFERENCES formas_pagamento(id),
    descricao TEXT NOT NULL,
    valor DECIMAL NOT NULL,
    dia_lancamento SMALLINT NOT NULL CHECK (dia_lancamento BETWEEN 1 AND 31),
    ativa BOOLEAN DEFAULT TRUE
);
ALTER TABLE gastos ADD COLUMN despesa_fixa_id INT REFERENCES despesas_fixas(id);
-- trava anti-duplicação: 1 lançamento por despesa fixa por mês
CREATE UNIQUE INDEX uq_despesa_fixa_mes ON gastos (despesa_fixa_id, DATE_TRUNC('month', competencia))
    WHERE despesa_fixa_id IS NOT NULL;

-- 005: entradas/receitas (gap não coberto pelo MD — ver G1)
CREATE TABLE entradas (
    id SERIAL PRIMARY KEY,
    usuario_id INT REFERENCES usuarios(id),
    grupo_id INT REFERENCES grupos(id),
    descricao TEXT,
    valor DECIMAL NOT NULL,
    data DATE DEFAULT NOW()
);

-- 006: contas web + convites (Fase 4)
ALTER TABLE usuarios ADD COLUMN auth_user_id UUID UNIQUE;  -- FK lógica p/ Supabase Auth
CREATE TABLE convites (
    id SERIAL PRIMARY KEY,
    grupo_id INT REFERENCES grupos(id),
    codigo TEXT UNIQUE NOT NULL,        -- curto, legível (ex: FIN-8K3M2P)
    criado_por INT REFERENCES usuarios(id),
    telefone TEXT,                      -- opcional: pré-vincula número ao gerar
    expira_em TIMESTAMP,                -- default NOW() + 7 dias
    usado_em TIMESTAMP,
    usado_por INT REFERENCES usuarios(id)
);

-- 007: SaaS (Fase 6)
CREATE TABLE planos (
    id SERIAL PRIMARY KEY,
    nome TEXT UNIQUE,          -- basic | plus | master | unlimited
    max_membros INT,           -- 1 | 2 | 5 | 10 (soft limit do unlimited)
    preco_mensal DECIMAL, preco_semestral DECIMAL, preco_anual DECIMAL
);
CREATE TABLE assinaturas (
    id SERIAL PRIMARY KEY,
    grupo_id INT REFERENCES grupos(id) UNIQUE,
    plano_id INT REFERENCES planos(id),
    status TEXT DEFAULT 'trial',   -- trial | ativa | inadimplente | cancelada
    ciclo TEXT,                    -- mensal | semestral | anual
    gateway_customer_id TEXT, gateway_subscription_id TEXT,
    inicio TIMESTAMP DEFAULT NOW(), proximo_vencimento TIMESTAMP
);
```

- **Arquivos:** `init_db.py` (absorvido pelas migrações), novo `database/`.
- Backfill: `UPDATE gastos SET competencia = DATE_TRUNC('month', data)` para histórico.

### Fase 3 — Novas regras de negócio no Flask

**Objetivo:** categorias customizáveis, parcelamento, despesas fixas, onboarding com tutorial, fallback de IA. Aproveitar para migrar incrementalmente à estrutura do `CLAUDE.md` (routes/services/providers), já que quase todos os módulos serão tocados.

3.1 **Categorias por grupo**
- `db.py → services/categorias.py`: `get_categorias(grupo_id)` retorna categorias do grupo + globais; CRUD (`categoria add/remover/listar` no bot).
- `parser.py`: `_CAT_ALIASES` vira fallback apenas para as globais; categoria custom casa por nome/fuzzy.
- `ai.py`: prompt Vision passa a receber a lista de categorias do grupo dinamicamente (hoje é hardcoded).
- `handler.py`: novo comando `categoria ...`; `comandos.py`: atualizar `cmd_ajuda`.

3.2 **Parcelamento**
- `parser.py`: detectar padrão `"3x"`, `"em 3 vezes"`, `"parcelado em 3"`.
- `services/parcelamento.py`: cria `compras_parceladas` + N linhas em `gastos`, cada uma com `parcela_num` e `competencia` calculada pelo `dia_fechamento` da forma (compra após o fechamento → 1ª parcela cai na competência seguinte). Divisão: `valor_total/n` arredondado, resíduo na 1ª parcela.
- `handler.py`: confirmação mostrando "12x de R$ 91,92, 1ª parcela em Agosto"; `excluir ultimo` precisa decidir se exclui 1 parcela ou a compra inteira (decisão D3).
- Consultas (`saldo`, `resumo`, `db.py`): trocar filtro `DATE_TRUNC('month', g.data)` por `competencia` — **isso muda o resultado de saldo/resumo existentes**, testar com histórico backfillado.

3.3 **Despesas fixas**
- `services/despesas_fixas.py` + comandos no bot (`fixa add Aluguel 1200 dia 5`, `fixa listar`, `fixa remover`).
- Lançador: função idempotente `lancar_despesas_fixas_do_mes()` protegida pelo índice único `uq_despesa_fixa_mes`.
- Execução: cron do Railway chamando `python -m jobs.lancar_fixas` diariamente (mais simples e robusto que APScheduler dentro do web process — decisão D4).

3.4 **Onboarding / tutorial**
- Já existe; ajuste: ao final do `_onboarding_resumo`, incluir o tutorial completo (hoje só no fluxo `grupo criar`). Decidir se o fluxo guiado atual permanece ou se simplifica para tutorial fixo + configuração posterior (D5).

3.5 **Entradas/receitas via WhatsApp** *(P1: bot + web)*
- `parser.py`: detectar intenção de entrada por palavras-chave (`recebi`, `entrada`, `salário`, `caiu`, `ganhei`) antes do fluxo de gasto — mesmo padrão de input livre de hoje.
- Comando explícito de fallback: `entrada 2000 salário`.
- `services/entradas.py`: CRUD sobre a tabela `entradas` (migração 005).
- Regra adotada: entrada **não** afeta saldo por forma de pagamento (limite é conceito de gasto); aparece no `resumo` do bot (linha "Entradas do mês") e no resumo analítico web (saldo do mês = entradas − gastos).
- `comandos.py`: `cmd_resumo` ganha total de entradas; `cmd_ajuda` atualizado.

3.6 **Fallback de IA com cancelamento seguro**
- `handler.py`: quando a mensagem não casa comando nem tem valor, chamar `services/ai_fallback.py` (nova função em `ai.py`/provider): classifica intenção (ajuda? gasto malformado? consulta?) e devolve sugestão.
- Se a IA deduzir um gasto: criar sessão `etapa="aguardando_confirmacao_ia"` com `dados_temp` (timeout 5 min já nativo de `sessoes`). Só `sim/confirmar` insere; expirou → nada inserido (mecanismo atual já garante); qualquer outra resposta cancela.
- Custo/latência: 1 chamada de LLM por mensagem não reconhecida — colocar atalho barato antes (fuzzy `"ajuda"/"ajudar"/"ajude"` etc. resolve sem IA).

**Testes da fase:** `tests/test_parcelamento.py`, `tests/test_despesas_fixas.py` (idempotência), `tests/test_fallback.py` (nada inserido sem confirmação).

### Fase 4 — Setup do front-end Next.js + API Flask

**Objetivo:** app web novo em `finbot-web/`, autenticado, falando **exclusivamente com a API Flask** (D6 adotada — supabase-js só para auth; dados nunca direto do banco no browser). RLS habilitada como 2ª camada de defesa.

**4.1 Stack e estrutura de pastas (padrão CLAUDE.md)**

```
finbot-web/
├── src/
│   ├── app/                          # App Router — 1 pasta por rota
│   │   ├── layout.jsx                # root: providers (Auth, Theme)
│   │   ├── (auth)/                   # rotas públicas
│   │   │   ├── login/page.jsx
│   │   │   ├── cadastro/page.jsx     # aceita ?convite=CODIGO na URL
│   │   │   ├── recuperar-senha/page.jsx
│   │   │   ├── redefinir-senha/page.jsx
│   │   │   └── convite/[codigo]/page.jsx   # landing do convite → redireciona p/ cadastro com código preenchido
│   │   └── (app)/                    # rotas protegidas (redirect p/ /login sem sessão)
│   │       ├── layout.jsx            # sidebar + header
│   │       ├── dashboard/page.jsx    # resumo analítico (5.2)
│   │       ├── lancamentos/page.jsx  # CRUD gastos + entradas (5.1)
│   │       ├── fixas/page.jsx        # CRUD despesas fixas
│   │       ├── importacao/page.jsx   # upload + revisão de fatura (5.3)
│   │       ├── grupo/page.jsx        # membros, convites, apelidos, telefones
│   │       ├── formas/page.jsx       # formas de pagamento + dia_fechamento
│   │       ├── categorias/page.jsx   # categorias do grupo
│   │       ├── planos/page.jsx       # telas de plano (Fase 6, só UI)
│   │       └── conta/page.jsx        # perfil, troca de senha, exclusão
│   ├── components/                   # pasta própria: index.jsx + styles.js
│   │   ├── Sidebar/  Header/  Modal/  ConfirmDialog/
│   │   ├── DataTable/                # tabela genérica: sort, paginação, ação por linha
│   │   ├── MoneyInput/               # input BR: vírgula decimal, máscara R$
│   │   ├── CategoriaSelect/  FormaSelect/  MesPicker/
│   │   ├── StatCard/  ChartCategoria/  ChartComparativo/  ChartFixoVariavel/
│   │   └── EmptyState/  Loading/  Toast/
│   ├── hooks/
│   │   ├── useAuth.jsx               # contexto: sessão Supabase, user, grupo, signOut
│   │   └── useApi.jsx                # fetch autenticado c/ estados loading/erro
│   ├── services/
│   │   └── api.js                    # instância única (axios) → NEXT_PUBLIC_API_URL, injeta JWT, trata 401 (redirect login)
│   ├── lib/supabase.js               # client Supabase (só auth)
│   ├── styles/theme.js + global.js   # styled-components
│   └── utils/format.js               # _brl, datas pt-BR, competência
├── .env.example                      # NEXT_PUBLIC_SUPABASE_URL/ANON_KEY, NEXT_PUBLIC_API_URL
└── jest.config.js
```

**4.2 Fluxos de autenticação (Supabase Auth — hash/reset nativos, não reinventar)**

| Fluxo | Comportamento |
|---|---|
| Cadastro **sem** convite | e-mail+senha → confirmação de e-mail → `POST /api/onboarding` cria `grupos` + `usuarios` (com `auth_user_id`) + pede nome do grupo e telefone WhatsApp do dono |
| Cadastro **com** convite (P1 revisado: convidado TEM conta web) | campo "código de convite" no formulário (pré-preenchido via `/convite/[codigo]` ou `?convite=`) → `POST /api/convites/aceitar` valida código (existe, não usado, não expirado) → vincula `auth_user_id` ao grupo **existente** (não cria grupo) + telefone; marca `usado_em`/`usado_por` |
| Login/logout | sessão persistida, refresh automático (supabase-js) |
| Recuperar senha | e-mail com link → `/redefinir-senha` |
| Troca de senha logado | em `/conta` |
| Guarda de rota | layout `(app)` verifica sessão; sem sessão → `/login` |

- Convidado que só usa o bot continua possível: vínculo por telefone via bot (`vincular`) segue funcionando sem conta web. Conta web do convidado é **opcional**, habilitada pelo código.

**4.3 Contrato da API Flask (novos Blueprints — padrão CLAUDE.md: rota fina → service)**

Todos sob `/api`, autenticados por JWT do Supabase (`middlewares/ensure_authenticated.py` valida assinatura via JWKS e resolve `usuario`/`grupo_id`; erros via `utils/app_error.py` + errorhandler central).

| Recurso | Endpoints | Service |
|---|---|---|
| Onboarding web | `POST /api/onboarding` | `services/onboarding.py` |
| Convites | `GET/POST /api/convites` · `POST /api/convites/aceitar` (público) | `services/convites.py` |
| Gastos | `GET /api/gastos?mes=&categoria=&membro=` · `POST` · `PUT/DELETE /api/gastos/:id` | `services/gastos.py` |
| Entradas | `GET/POST /api/entradas` · `PUT/DELETE /api/entradas/:id` | `services/entradas.py` |
| Fixas | `GET/POST /api/fixas` · `PUT/DELETE /api/fixas/:id` | `services/despesas_fixas.py` |
| Categorias | `GET/POST /api/categorias` · `PUT/DELETE /api/categorias/:id` | `services/categorias.py` |
| Formas | `GET/POST /api/formas` · `PUT/DELETE /api/formas/:id` (inclui `dia_fechamento`) | `services/formas.py` |
| Grupo | `GET /api/grupo` · `PUT /api/grupo` · `POST /api/grupo/membros` · `DELETE /api/grupo/membros/:id` · `PUT /api/grupo/membros/:id` (apelido/telefone) | `services/grupos.py` |
| Resumo | `GET /api/resumo?mes=` (agregados prontos p/ o dashboard: por categoria, comparativo 6 meses, fixo×variável, entradas−gastos) | `services/resumo.py` |
| Importação | `POST /api/importacao/upload` · `POST /api/importacao/confirmar` | `services/importacao.py` |
| Planos | `GET /api/planos` · `GET /api/assinatura` | `services/planos.py` |

- CORS restrito ao domínio do front. Paginação padrão `?page=&per_page=50`. Valores sempre `number` com ponto decimal no JSON; formatação BR é responsabilidade do front (`utils/format.js`).

**Tabelas:** já criadas na Fase 2 (006). RLS: policies por `grupo_id` em todas as tabelas de dados (defesa em profundidade, mesmo com API).

### Fase 5 — Telas web (especificação por tela)

Layout orientado pela síntese da Fase 0. Todas as telas: estado vazio (EmptyState com CTA), loading (skeleton) e erro (Toast).

**5.1 `/lancamentos` — CRUD de gastos e entradas**
- Abas "Gastos" | "Entradas". Filtros: MesPicker (competência), categoria, forma, membro.
- DataTable: data, descrição, categoria, forma, membro, valor, badge de origem (bot/web/importação/fixa/parcela `3/12`).
- Ações por linha: editar (Modal com MoneyInput/CategoriaSelect/FormaSelect), excluir (ConfirmDialog; se parcela → escolher "só esta" × "compra inteira", mesma regra D3 do bot).
- Botão "Novo lançamento": modal único com toggle gasto/entrada; gasto permite "parcelado em N×".

**5.2 `/dashboard` — resumo analítico (leitura, sem edição)**
- Linha de StatCards: entradas do mês, gastos do mês, saldo (entradas−gastos), % dos limites usados.
- ChartCategoria: donut de gastos por categoria no mês.
- ChartComparativo: barras dos últimos 6 meses (entradas × gastos), por competência.
- ChartFixoVariavel: fixo (`despesa_fixa_id IS NOT NULL`) vs variável.
- Tudo de `GET /api/resumo` (1 request; agregação no Flask, não no browser). Gráficos: Recharts.

**5.3 `/importacao` — fatura de cartão**
- Passo 1: upload PDF/CSV (drag-and-drop) + FormaSelect da fatura → `POST /api/importacao/upload`.
- Parse no Flask: CSV determinístico (encoding/separador BR); PDF via OpenAI (prompt novo em `ai.py`) retornando linhas `{data, descricao, valor, categoria_sugerida}`.
- Passo 2: tabela de revisão editável linha a linha (valor, categoria, incluir/excluir checkbox); duplicatas prováveis (mesmo valor+data já no banco) destacadas.
- Passo 3: `POST /api/importacao/confirmar` grava em lote com `importacao_id`. **Nada entra sem essa ação explícita.** Botão "desfazer importação" (deleta pelo `importacao_id`).
- Tabela adicional: `importacoes (id, grupo_id, forma_pagamento_id, arquivo_nome, linhas, criado_em)` + `gastos.importacao_id`.

**5.4 `/grupo`** — nome do grupo, lista de membros (apelido, telefone, tem conta web?), editar apelido/telefone, remover membro, gerar convite (mostra código + link `/convite/CODIGO` p/ copiar), lista de convites pendentes/expirados.

**5.5 `/formas` e `/categorias`** — CRUDs simples em DataTable + Modal; forma tem `limite_mensal` e `dia_fechamento` (select 1–31 com aviso de como afeta a competência); categoria global aparece como "padrão" (ocultável, não deletável — G5).

**5.6 `/conta`** — nome/apelido, e-mail, troca de senha, sair; exclusão de conta (LGPD, F7).

### Fase 6 — Estrutura SaaS (sem gateway por ora — P5)

- Seed `planos` (basic 1 / plus 2 / master 5 / unlimited 10 soft) com preços NULL (P6: definição futura — colunas já existem na migração 007).
- **Sem integração de pagamento nesta fase.** Gateway (D7) adiado; deixar `assinaturas.gateway_*` nulos e status manual (`trial`/`ativa` via seed/admin).
- Tela `/planos`: cards dos 4 planos (nome, limite de membros, preço "em breve" enquanto NULL), plano atual do grupo destacado, botão de contratação **desabilitado** com aviso — só UI, sem checkout.
- Enforcement do limite de membros num único ponto: `services/grupos.py::adicionar_membro` (usado por bot **e** web).
- Downgrade (P3 decidido: **grupo escolhe quem sai**): ao trocar para plano menor com membros excedentes, o web exige seleção de quem permanece antes de concluir; removidos voltam a conta individual (mesma lógica de `sair_grupo`). Enquanto houver excedente, novos registros dos excedentes são bloqueados com mensagem no bot.

### Fase 7 — Hardening e qualidade (pré-lançamento)

- **Webhook sem autenticação** (`/webhook` aceita qualquer POST): validar apikey/HMAC da Evolution API.
- **Duplicata de comprovante em memória** (`app.py:_cupons_recentes`): não sobrevive a restart nem a 2+ workers gunicorn — mover para tabela ou constraint.
- Rate limiting por telefone; logs estruturados no lugar de `print`.
- **Remover `notificar.py`** (decidido em P4: Twilio/API oficial fora do plano, canal permanece Evolution API).
- Grupos reais de WhatsApp permanecem suportados (P4) — mitigar custo de IA: em `@g.us`, não acionar fallback de IA nem Vision/Whisper para mensagens que não parecem gasto/comando (filtro barato antes da chamada de LLM).
- Jest/RTL no Next.js para rotas críticas (revisão de fatura, checkout).
- LGPD: dados financeiros + telefones de terceiros (membro é cadastrado por outra pessoa) — política de privacidade e exclusão de conta.

---

## 3. Gaps do escopo para discutirmos

- **G1 — Entradas/receitas** ✅ *resolvido (P1)*: bot + web, mesmo padrão de input livre dos gastos; não afeta saldo por forma, entra no resumo (detalhe na Fase 3.5).
- **G2 — Competência vs. data:** parcelamento "no mês subsequente" e despesa fixa "na data de corte" só fecham com o conceito de competência + `dia_fechamento` por forma. Isso **muda o cálculo de saldo/resumo atuais** — precisa estar claro que o comportamento do bot vai mudar para gastos de cartão perto do fechamento.
- **G3 — Onboarding duplicado:** o MD pede tutorial fixo, mas já existe onboarding guiado. Manter os dois é redundante; minha recomendação é manter o guiado e anexar o tutorial no fim (D5).
- **G4 — Fallback de IA já meio resolvido:** o timeout de 5 min com cancelamento seguro já é o comportamento nativo de `sessoes`. O trabalho real é a classificação de intenção + etapa de confirmação — bem menor que o MD sugere.
- **G5 — Categorias por grupo × histórico:** gastos antigos apontam para categorias globais. Se o grupo "remove" uma categoria global, o que acontece com o histórico? Proposta: categorias globais nunca somem, grupo só as oculta.
- **G6 — Downgrade de plano** ✅ *resolvido (P3)*: grupo escolhe quem sai (fluxo na Fase 6); excedentes bloqueados de registrar até resolver.
- **G7 — Bot em grupos reais de WhatsApp** ✅ *resolvido (P4)*: mantém suporte a `@g.us` (canal segue Evolution API, sem Twilio/API oficial). Mitigação de custo de IA em grupos incluída na F7.
- **G8 — RLS/segurança antes do web:** expor o Supabase ao browser sem RLS é o maior risco técnico do plano. D6 precisa ser decidido antes de qualquer tela.

## 4. Decisões (D) — status em 11/07/2026

**D1–D6 adotadas conforme recomendação (aprovado pelo Lucas). D7 permanece aberta — depende da pesquisa da Fase 0.**

| # | Decisão | Opções | Adotado |
|---|---|---|---|
| D1 | `"1103.04"` (ponto como decimal, sem vírgula) | tratar `.` c/ 2 casas como decimal × sempre milhar | `.` seguido de exatamente 2 dígitos no fim = decimal |
| D2 | Quando reestruturar p/ padrão CLAUDE.md | antes (big-bang) × incremental na Fase 3 | Incremental — cada módulo migra quando for tocado |
| D3 | `excluir ultimo` em compra parcelada | excluir 1 parcela × compra inteira | Perguntar ao usuário na hora (sessão de confirmação) |
| D4 | Scheduler das despesas fixas | Railway cron × APScheduler in-process | Railway cron (sobrevive a deploy, sem worker duplicado) |
| D5 | Onboarding | manter guiado + tutorial × só tutorial fixo | Manter guiado + tutorial no final |
| D6 | Web acessa dados via | supabase-js + RLS × API Flask | API Flask — 1 lugar só de regra de negócio (limites de plano, competência), RLS como 2ª camada |
| D7 | Gateway de pagamento | Stripe × Mercado Pago × Abacate/Asaas | **ADIADA (P5)** — Fase 6 entrega só UI e estrutura; decidir quando a monetização entrar |

## 5. Pendências — todas respondidas pelo Lucas em 11/07/2026

| # | Pendência | Decisão |
|---|---|---|
| P1 | Entradas | **Bot (input livre, como gastos hoje) + web** — Fase 3.5 |
| P2 | Competência muda cálculo de saldo/resumo | **Aceito** — Fase 3.2 |
| P3 | Downgrade de plano | **Grupo escolhe quem sai** — Fase 6 |
| P4 | Bot em grupos de WhatsApp | **Mantém** (canal segue Evolution API; sem Twilio/API oficial → `notificar.py` removido na F7) |
| P5 | Gateway de pagamento | **Sem gateway por ora — só a tela de planos** (Fase 6 = UI + estrutura) |
| P6 | Preços dos planos / trial | **Definição futura** — schema pronto (migração 007), preços NULL |

Adicional (11/07): **membro convidado passa a poder ter conta web**, criada com código de convite no cadastro — incorporado na Fase 4.2 e migração 006 (`usado_por`, `telefone`). Vínculo só pelo bot continua possível; conta web do convidado é opcional.

**Nenhuma pendência aberta. Plano pronto para execução a partir da Fase 0/1.**

## 6. Ordem sugerida e dependências

```
F0 (benchmarking) ──────────────┐
F1 (pytest + parser) → F2 (migrações) → F3 (regras Flask) → F4 (web setup) → F5 (telas) → F6 (SaaS) → F7 (hardening*)
                                                  ▲ decisões D1-D5              ▲ D6        ▲ D7
```
*Itens de segurança do F7 que bloqueiam lançamento (webhook aberto, RLS) devem ser antecipados para F4.
