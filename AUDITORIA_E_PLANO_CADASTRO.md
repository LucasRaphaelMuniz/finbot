# Auditoria do finbot + Plano: cadastro/vínculo web↔WhatsApp e tutorial de 1º login

> Análise de 11/07/2026, código atual (backend Flask + finbot-web Next.js).
> Documento de planejamento — **nada foi alterado no código**.

---

## Parte 1 — Auditoria: gaps e falhas encontrados

### 🔴 F1 — CRÍTICO: o merge por telefone que você quer **já existe no código, mas nunca funciona**

O `services/onboarding.py` já tenta exatamente o que você pediu:

```python
# Reaproveita usuario pré-existente pelo telefone (já usava o bot
# antes de criar conta web) em vez de duplicar...
cur.execute("SELECT * FROM usuarios WHERE telefone = %s", (telefone,))
```

Só que os dois lados falam formatos diferentes:

| Origem | O que salva em `usuarios.telefone` |
|---|---|
| Bot (webhook → `_normalizar_jid`) | `5544912345678@s.whatsapp.net` |
| Web (`/api/onboarding`, form CompletarCadastro) | `44912345678` (cru, como digitado) |

O `SELECT ... WHERE telefone = %s` **nunca encontra** o usuário do bot. Resultado em cascata:

1. Pessoa que já usava o bot cria conta web → sistema cria **usuário duplicado + grupo novo vazio**, em vez de puxar o cadastro existente.
2. Pessoa que se cadastrou primeiro no web e depois manda "oi" no WhatsApp → webhook procura pelo JID, não acha o registro web → cria **segundo usuário**, e os gastos do WhatsApp caem num limbo separado do dashboard dela. Os dados divergem para sempre.
3. O mesmo bug existe em `services/convites.py:aceitar_convite` (busca por `telefone_final` cru) e em `POST /api/grupo/membros` (web): membro adicionado pela web fica com telefone cru → **o bot nunca reconhece as mensagens dele**.

Não existe nenhuma função de normalização compartilhada: `_normalizar_jid` vive em `app.py`, `_normalizar_telefone` vive em `handler.py`, e **nenhum service/route da API web usa qualquer uma das duas**.

### 🔴 F2 — GRAVE: falha de segurança na sua proposta de merge (e no código atual)

Sua proposta — "solicita o número e, se já possui cadastro, puxa tudo fazendo merge" — sem verificação de posse do número significa: **qualquer pessoa digita o telefone de um terceiro no cadastro web e ganha acesso ao histórico financeiro completo do grupo dele** (gastos, entradas, membros, limites). O código atual já tem essa exposição (mitigada apenas pelo F1, que quebra o merge por acidente). Corrigir o F1 sem adicionar verificação **transforma o bug em vulnerabilidade explorável**.

Solução obrigatória: OTP via WhatsApp — o bot envia um código de 6 dígitos para o número informado (via Evolution API, que já está integrada), e a pessoa digita o código no web. Só então o merge acontece. Detalhado na Parte 2.

### 🟠 F3 — `DELETE /api/conta` não exige senha no backend

A reautenticação por senha da exclusão de conta é feita **só no frontend** (`conta/page.jsx` chama `signInWithPassword` antes do DELETE). Qualquer requisição com um JWT válido (token vazado, XSS, extensão maliciosa) apaga o grupo inteiro sem senha — a rota `DELETE /api/conta` só checa o Bearer token. O comentário em `services/conta.py` diz que "o backend não tem como validar a senha do Supabase" — tem sim: o backend pode chamar o endpoint `POST /auth/v1/token?grant_type=password` do Supabase (server-side) com email+senha recebidos no body antes de executar a exclusão.

### 🟠 F4 — `PUT /api/grupo/membros/:id` aceita qualquer telefone, sem normalizar nem tratar colisão

`usuarios.telefone` é `UNIQUE`. Editar um membro pela web com um telefone que já existe estoura violação de UNIQUE → erro 500 genérico. E como não normaliza (F1), editar o telefone de um membro pela web **quebra o vínculo dele com o bot**.

### 🟡 F5 — Tutorial de primeiro login web: inexistente

Após o `CompletarCadastro`, a pessoa cai no dashboard vazio, sem saber que o próximo passo é falar com o bot no WhatsApp. Não há welcome, checklist nem indicação do número do bot. (No bot, o onboarding guiado + tutorial já existem e estão bons — o gap é só no web.)

### 🟡 F6 — Corrida no `completar_onboarding`

A idempotência é por `SELECT` antes do `INSERT` — dois requests simultâneos (duplo clique real, não F5) passam ambos pelo SELECT. O UNIQUE de `auth_user_id` derruba o segundo com 500 em vez de retornar o existente. Baixa probabilidade, correção barata (capturar `UniqueViolation` e re-selecionar, ou `ON CONFLICT`).

### 🟡 F7 — Webhook aberto sem `EVOLUTION_WEBHOOK_SECRET`

`validar_apikey` retorna `True` se o secret não estiver configurado (fail-open, decisão documentada). Aceitável em dev; em produção (Railway) deveria ser fail-closed — recusar tudo e logar erro de config, ou no mínimo um check no startup.

### 🟡 F8 — Front não valida/mascara o telefone

Os inputs de telefone (`CompletarCadastro`, editar membro) aceitam qualquer string. Com F1 corrigido no backend, ainda vale máscara + validação no front para reduzir erro de digitação (DDD ausente, número com 8 dígitos sem o 9).

### Pontos menores (registrar, não urgente)

- `sessao.py` interpola `timeout_minutos` via f-string no SQL. Hoje só recebe int de código interno — seguro, mas não-idiomático; usar `make_interval(mins => %s)`.
- `POST /api/gastos` não valida que `categoria_id` pertence ao grupo (ou é global) — cross-tenant fraco: permite gravar gasto com categoria personalizada de outro grupo.
- Dedup de comprovante por `telefone:valor` (sem cupom) dá falso positivo para dois gastos legítimos de mesmo valor em 10 min — o usuário recebe aviso e pode digitar manual, então é tolerável, mas vale monitorar.
- `init_db.py` e `database/migrations/` convivem — risco de schema divergir. Consolidar em migrations (001 sendo o schema base).
- `_handle_unexpected_error` re-checa `isinstance(err, AppError)` — inalcançável (Flask despacha o handler mais específico primeiro). Cosmético.

### O que está bem (não mexer)

Multi-tenant por `grupo_id` consistente nos services web; whitelist de campos editáveis em gastos; `AppError` + errorhandler central conforme CLAUDE.md; hardening do webhook (rate limit, dedup persistido, comparação constant-time); exclusão LGPD com trilha master/membro e ordem de FKs correta; guard de rota + contrato `sem_grupo` entre layout e API.

---

## Parte 2 — Plano de execução

Ordem pensada para: fundação (normalização) primeiro, porque F1 bloqueia tudo; depois verificação/merge; tutorial por último (depende do fluxo novo estar no ar).

### Fase A — Normalização única de telefone (corrige F1, F4, F8) — *fundação*

**A1. Criar `utils/telefone.py`** — módulo único, canônico:
- `normalizar(telefone) -> str | None`: qualquer entrada (`44912345678`, `+55 (44) 91234-5678`, JID) → formato canônico `5544912345678@s.whatsapp.net`. Consolida a lógica hoje duplicada em `app.py:_normalizar_jid` e `handler.py:_normalizar_telefone` (incluindo a correção do 9º dígito).
- `exibir(telefone) -> str`: JID → `+55 44 91234-5678` para UI.
- Decisão de design: **manter o JID como formato canônico de armazenamento** (não migrar para E.164). Motivo: é o formato que o webhook já usa em todo lookup quente; migrar o canônico inverteria o custo (mexer no caminho crítico do bot para poupar 4 call-sites da web).

**A2. Aplicar em todos os pontos de entrada web**: `services/onboarding.py`, `services/convites.py` (gerar com telefone pré-vinculado e aceitar), `services/grupos.py:adicionar_membro` e `atualizar_membro`, sempre com rejeição (`AppError 400 "telefone_invalido"`) se `normalizar()` retornar None. Em `atualizar_membro`, capturar violação de UNIQUE → `AppError 400 "telefone_em_uso"` (corrige F4).

**A3. `app.py` e `handler.py` passam a importar de `utils/telefone.py`** — remove a duplicação. Os testes existentes de parser/handler continuam valendo; adicionar `tests/test_telefone.py` com os formatos da docstring atual.

**A4. Migration `011_normalizar_telefones.sql`** — backfill: normalizar registros existentes criados pela web com telefone cru. Antes do UPDATE, detectar colisão (telefone cru que, normalizado, já existe como JID = par de duplicados do F1) e **listar para decisão manual** — merge automático de dados históricos no SQL é arriscado; provavelmente são poucos casos.

**A5. Front**: máscara/validação de telefone nos 3 inputs (CompletarCadastro ×2, editar membro), num componente `TelefoneInput` próprio (padrão pasta + index.jsx do CLAUDE.md).

### Fase B — Verificação de posse + merge (corrige F2 e entrega o fluxo que você pediu)

**B1. Migration `012_verificacoes_telefone.sql`**:
```sql
CREATE TABLE verificacoes_telefone (
    id           SERIAL PRIMARY KEY,
    auth_user_id UUID NOT NULL,
    telefone     TEXT NOT NULL,          -- já normalizado (JID)
    codigo       TEXT NOT NULL,          -- 6 dígitos, gerado com secrets
    tentativas   INT NOT NULL DEFAULT 0, -- máx 5, depois invalida
    expira_em    TIMESTAMP NOT NULL,     -- NOW() + 10 min
    verificado_em TIMESTAMP
);
```

**B2. Novas rotas** (`routes/verificacao.py` + `services/verificacao.py`, padrão blueprint fino → service):
- `POST /api/verificacao/enviar` `{telefone}` — normaliza, gera código, envia pelo bot via Evolution API (reutilizar `enviar_mensagem` de `app.py` — **mover para `providers/evolution.py`** junto, é integração externa e hoje está no lugar errado segundo o próprio CLAUDE.md). Rate limit: máx 3 envios/número/hora (reusa padrão de `rate_limit_webhook`).
- `POST /api/verificacao/confirmar` `{telefone, codigo}` — valida código/expiração/tentativas, marca `verificado_em`. Resposta inclui `{ja_existia: bool, tem_grupo: bool}` para o front decidir o passo seguinte.

**B3. Reescrever o fluxo do `CompletarCadastro` em 2 passos**:
1. **Passo 1 — telefone**: pede o WhatsApp → `enviar` → tela de código → `confirmar`.
2. **Passo 2 — condicional** ao resultado:
   - `ja_existia && tem_grupo` (seu caso principal): **não pede mais nada**. Chama `POST /api/onboarding` que faz o merge — liga `auth_user_id` ao registro existente, mantém grupo, formas, categorias, histórico. Mostra: "Encontramos seu cadastro do WhatsApp — grupo *X*, N membros, tudo já configurado."
   - `ja_existia && !tem_grupo` (usuário antigo do bot sem grupo): pede só nome do grupo → merge + cria grupo (fluxo atual de `completar_onboarding` já cobre).
   - `!ja_existia`: pede nome do grupo → cria do zero (fluxo atual).
3. Caso de conflito: telefone já tem `auth_user_id` de OUTRA conta → `AppError 409 "telefone_ja_vinculado"` com mensagem orientando a recuperar a senha da conta original.

**B4. Backend do merge** (`services/onboarding.py`):
- `completar_onboarding` passa a **exigir verificação prévia** (checa `verificacoes_telefone.verificado_em` para o par `auth_user_id + telefone`; sem isso, 403). Mesmo para número novo — evita registrar número de terceiro que futuramente usaria o bot.
- No merge com usuário existente: ligar `auth_user_id`, **preservar** nome/grupo/dados do bot (o cadastro do bot é a fonte de verdade do que já foi parametrizado — é o "puxa tudo" que você descreveu). `nome_grupo` do form é ignorado nesse caminho (nem chega a ser pedido, ver B3).
- Corrigir F6 no mesmo commit: `INSERT ... ON CONFLICT (auth_user_id) DO NOTHING` + re-select.
- Mesmo requisito de verificação em `aceitar_convite` quando o telefone vem do formulário (quando vem pré-vinculado no convite, o dono do grupo já atestou o número — dispensa OTP).

**B5. Sentido inverso (web primeiro → WhatsApp depois)**: nenhum código novo — com a Fase A, `get_or_create_usuario(jid)` encontra o registro criado pela web e o bot já cai no fluxo existente. Adicionar teste cobrindo esse caminho (`tests/test_merge_web_bot.py`).

### Fase C — Tutorial de primeiro login web (corrige F5)

**C1. Migration `013_tutorial_web.sql`**: `ALTER TABLE usuarios ADD COLUMN tutorial_web_visto_em TIMESTAMP;`
Decisão: coluna no banco, **não** localStorage — sobrevive a troca de dispositivo/navegador e permite reexibir por suporte. Exposta no `GET /api/grupo` (membros já retornam) ou num `GET /api/conta/eu` leve; marcada via `POST /api/conta/tutorial-visto`.

**C2. Componente `TourPrimeiroLogin`** (pasta própria, padrão CLAUDE.md), renderizado pelo `(app)/layout.jsx` quando `statusGrupo === "ok"` e `tutorial_web_visto_em IS NULL`. Modal/checklist de 4 passos, adaptado ao caminho de entrada:

| Passo | Veio do WhatsApp (merge) | Cadastro novo |
|---|---|---|
| 1 | "Seus dados do bot já estão aqui" — aponta Lançamentos | Salve o número do bot e mande *oi* no WhatsApp (deep link `wa.me/<numero_bot>?text=oi`) |
| 2 | Confira formas de pagamento e limites (tela Formas) | Registre o 1º gasto pelo WhatsApp: *50 mercado cartão* |
| 3 | Explore o dashboard (gráficos por categoria/mês) | Configure formas e limites |
| 4 | Convide alguém pro grupo (tela Grupo → convite) | Convide alguém pro grupo |

Botões "Concluir" e "Pular" — ambos marcam visto. Reexibição: link "rever tutorial" na tela Conta (zera a flag via mesma rota).

O número do bot entra como `NEXT_PUBLIC_BOT_WHATSAPP` no `.env` do web (hoje não existe em lugar nenhum do front).

**C3. Lado bot — fechamento do ciclo**: ao concluir merge (B4), o backend envia UMA mensagem proativa pelo bot: "✅ Sua conta web foi vinculada a este número. Seus registros aparecem em <URL>." Serve de confirmação de segurança (a pessoa fica sabendo se alguém vinculou o número dela — defesa em profundidade do F2) e de tutorial reverso.

### Fase D — Hardening restante da auditoria

- **D1 (F3)**: `DELETE /api/conta` passa a receber `{senha}` e validar server-side contra o Supabase Auth antes de excluir. Front mantém a UX atual, backend deixa de confiar no cliente.
- **D2 (F7)**: startup check — em produção (`RAILWAY_ENVIRONMENT` presente) sem `EVOLUTION_WEBHOOK_SECRET`, logar erro e recusar webhook (fail-closed).
- **D3**: validação de `categoria_id` pertencente ao grupo em `POST/PUT /api/gastos`.
- **D4**: `make_interval` em `sessao.py`; consolidar `init_db.py` → migration 001-base; remover o isinstance morto em `app.py`.

### Ordem, dependências e testes

```
A (normalização)  ──►  B (OTP + merge)  ──►  C (tutorial)
                                   └──►  D (independente, pode paralelo a C)
```

Cada fase com testes antes de seguir: A → `test_telefone.py` + regressão dos existentes; B → `test_verificacao.py`, `test_merge_web_bot.py` (os 3 cenários do B3 + conflito 409 + sentido inverso B5); C → teste de componente do tour (padrão dos `page.test.jsx` existentes). Migrations sempre com backfill validado num dump de produção antes de aplicar.

### Riscos

| Risco | Mitigação |
|---|---|
| Backfill (A4) encontra duplicados web×bot já criados pelo F1 | Script lista pares para decisão manual; não faz merge automático de histórico |
| OTP adiciona atrito no cadastro | Atrito de 1 mensagem, inevitável: sem ele o merge é uma vulnerabilidade (F2). ZapGastos e afins fazem o mesmo |
| Evolution API fora do ar bloqueia cadastro web novo | `enviar` com retry + mensagem clara; cadastro sem verificação **não** prossegue (fail-closed por design) |
| Instância Evolution só envia de UM número — se a pessoa nunca falou com o bot, mensagem proativa pode não entregar | Testar entrega proativa para número frio; se falhar, fallback: fluxo inverso (pessoa manda `verificar ABC123` para o bot) |
