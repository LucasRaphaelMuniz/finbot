# Padrão de organização de projeto — referência

Referência de estrutura definida por Lucas a partir de dois projetos próprios:

- Backend: https://github.com/LucasRaphaelMuniz/projetoFinalRocketFoodsBackend (Node/Express + Knex/SQLite)
- Frontend: https://github.com/LucasRaphaelMuniz/projetoFinalRocketFoodsFrontend (React + styled-components)

Objetivo: usar essa mesma lógica de separação de responsabilidades em projetos futuros, com prioridade para o **finbot** (Flask/Python).

## O que foi observado nos projetos de referência

**Backend (Express)**, `src/`:
```
configs/        # config isolada (auth.js, upload.js) — nada de env solto no meio do código
controllers/     # 1 classe por recurso, métodos index/show/create/update/delete
database/        # conexão (knex/index.js) + migrations separadas
middlewares/     # ex: ensureAuthenticated.js
providers/       # integrações externas (ex: DiskStorage.js)
routes/          # 1 arquivo de rotas por recurso + index.js agregando tudo
utils/           # AppError.js (erro customizado tratado no middleware global do server.js)
server.js        # monta app, registra middlewares, error handler central
```
Decisões que valem a pena repetir:
- **Erro customizado (`AppError`) + middleware global no `server.js`** — controller só dá `throw new AppError(msg, status)`, não faz `try/catch` de resposta HTTP em todo lugar.
- **Rotas finas**: `routes/*.routes.js` só liga método HTTP → controller. Nenhuma lógica de negócio ali.
- **1 arquivo de config por assunto** (`auth.js`, `upload.js`) em vez de `process.env.X` espalhado pelos controllers.

**Frontend (React)**, `src/`:
```
assets/          # svgs/imagens
components/      # 1 pasta por componente: index.jsx + styles.js separados
hooks/           # ex: auth.jsx (contexto de autenticação)
pages/           # 1 pasta por página: index.jsx + styles.js
routes/          # index.jsx decide AppRoutes vs AuthRoutes conforme sessão
services/        # api.js — instância única do axios
styles/          # theme.js + global.js
```
Decisão que vale a pena repetir: **componente/página sempre em pasta própria com `index.jsx` (lógica/JSX) separado de `styles.js` (styled-components)** — facilita achar e trocar estilo sem mexer em lógica.

## Como isso se traduz para o finbot (Flask)

O finbot hoje é **flat**: `app.py`, `handler.py`, `db.py`, `ai.py`, `parser.py`, `comandos.py`, `sessao.py`, `notificar.py` na raiz, sem pastas. Isso diverge do padrão acima — não vou fingir que já segue. A proposta abaixo é a convenção a aplicar **daqui para frente**, para módulos novos ou quando fizer sentido mover algo existente (migração incremental, não reescrita).

Mapeamento Express/React → Flask:

| Referência              | Equivalente Flask no finbot                                   |
|--------------------------|-----------------------------------------------------------------|
| `configs/`               | `config.py` (ou `configs/` se crescer: `auth.py`, `evolution.py`) |
| `controllers/`           | `services/` — funções/classes com a lógica de negócio, sem tocar em `request`/`response` diretamente |
| `routes/`                | `routes/` com Blueprints Flask — 1 blueprint por recurso, view function fina só chamando o `service` |
| `middlewares/`           | `middlewares/` — decorators (ex: `@ensure_authenticated`) |
| `database/` (+migrations)| `db.py` já existe; se crescer, separar `database/connection.py` + `database/migrations/` |
| `providers/`             | `providers/` — integrações externas (Evolution API, Whisper/Vision, Supabase) |
| `utils/AppError.js`      | `utils/app_error.py` — exceção customizada + `@app.errorhandler` central no `app.py`, em vez de `try/except` retornando JSON em cada função |
| `server.js`              | `app.py` — só cria a app, registra blueprints e o error handler, sem lógica de negócio |

Convenção de nomenclatura a seguir:
- Arquivos e pastas em `snake_case` (padrão Python), não `camelCase`.
- 1 recurso = 1 blueprint + 1 service, nomes espelhados (`routes/pagamentos.py` ↔ `services/pagamentos.py`).
- Erros de negócio sempre via exceção customizada capturada num único `errorhandler`, nunca `return jsonify(erro), 400` espalhado pelo código.

Se o front do finbot vier a ter interface própria em React, replicar o padrão de `components/` e `pages/` com pasta própria + `index.jsx`/`styles.js` (ou `.css` equivalente) observado no projeto de referência.
