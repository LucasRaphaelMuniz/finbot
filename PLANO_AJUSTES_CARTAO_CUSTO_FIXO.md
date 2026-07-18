# Plano — Custo Fixo, provisionamento de cartão, limite rotativo e WhatsApp no cadastro

## Status (17/07/2026): código implementado, falta rodar em produção

Tudo abaixo (A–E) está escrito e testado localmente (119 testes, `pytest tests/`).
O que falta é ação manual do Lucas, porque a sandbox não alcança o Supabase:

1. `python -m database.migrate` — aplica 019/020/021 (adiciona dia_vencimento,
   recalcula competência de gastos de cartão existentes, cria faturas_pagas
   com backfill de meses passados como pagos).
2. `python scripts/migrar_custo_fixo.py <usuario_id>` — interativo, pergunta
   quais despesas fixas migram pra "Custo Fixo" e oferece criar a categoria
   "Assinaturas".
3. Web: preencher `dia_vencimento` de cada cartão em Formas de pagamento
   (novo campo, só aparece quando dia_fechamento está preenchido) — sem
   isso o sistema usa o fallback (vencimento no mês seguinte ao fechamento).
4. Deploy do finbot-web (Next.js) e do backend Flask no Railway pra essas
   mudanças valerem no bot e na web.

Definido com Lucas em 17/07/2026. Decisões já tomadas:
- Fixas de débito/PIX viram forma "Custo Fixo"; **assinaturas no cartão (seguro, Netflix...) mantêm a forma do cartão** — precisam continuar contando limite e caindo na fatura.
- Backfill completo do histórico (dashboards de meses passados vão mudar — aceito).
- Limite do cartão modelado como **rotativo real** (ciclo aberto + fatura fechada não paga), com marcação de "fatura paga".

---

## A. Forma de pagamento "Custo Fixo"

**O que é:** fixas pagas por débito automático/PIX passam a apontar para uma forma "Custo Fixo" (sem `limite_mensal`, sem `dia_fechamento`), em vez de "PIX". Fixas pagas no cartão **não mudam**.

**Falha conceitual assumida:** `formas_pagamento` responde "como foi pago", não "que tipo de gasto é" — o sistema já distingue fixo×variável por `gastos.despesa_fixa_id`. "Custo Fixo" aqui é um rótulo de visualização que o Lucas quer nos relatórios por forma. Registrado para não parecer acidente depois.

**Execução (dados, não schema):**
1. Criar forma "Custo Fixo" no grupo do Lucas.
2. `UPDATE despesas_fixas SET forma_pagamento_id = <custo_fixo>` só nas fixas escolhidas (lista a confirmar — ver Pendências).
3. Backfill: `UPDATE gastos SET forma_pagamento_id = <custo_fixo> WHERE despesa_fixa_id IN (...)`.

Via `scripts/migrar_custo_fixo.py` (roda local com `.env`): lista as fixas, pede confirmação de quais migrar, executa em transação. Não é migração versionada — é dado de uma conta, não schema do produto.

---

## B. Provisionamento do cartão (competência = mês do pagamento)

**Problema atual:** `calcular_competencia` só empurra pro mês seguinte compras **depois** do fechamento. Compra dia 10, fechamento dia 25 → competência do mês corrente; mas essa fatura só é paga no mês seguinte. Orçamento/saldo mostram o gasto num mês em que ele não sai do caixa.

**Regra nova:** competência de gasto no cartão = **mês do vencimento da fatura** em que a compra caiu.

1. Migração `019`: `ALTER TABLE formas_pagamento ADD COLUMN dia_vencimento INT` (só faz sentido para formas com `dia_fechamento`).
2. `calcular_competencia(data, dia_fechamento, dia_vencimento)`:
   - determina a fatura pelo `dia_fechamento` (regra atual);
   - mês de pagamento: se `dia_vencimento > dia_fechamento`, o vencimento é no mesmo mês do fechamento; senão, no mês seguinte. Fallback sem `dia_vencimento`: mês seguinte ao fechamento (caso mais comum no Brasil).
   - Sem `dia_fechamento` (PIX/débito/Custo Fixo): mês da compra, como hoje.
3. Migração `020` (backfill): desloca a competência dos gastos existentes de formas com `dia_fechamento` conforme a regra nova. Cobre avulsos, parcelas de parcelamento e fixas de cartão de uma vez — todos gravam `competencia` pela mesma função.
4. Propagação automática: `registrar_gasto`, `parcelamento`, `despesas_fixas` (cron e confirmação manual) já chamam `calcular_competencia` — mudam junto. `somar_meses` das parcelas continua válido.
5. Atualizar testes: `test_parcelamento`, `test_despesas_fixas` e criar casos para `dia_vencimento`.

**Efeito colateral desejado:** saldo/resumo/dashboard filtram por competência — passam a mostrar o cartão provisionado no mês do pagamento sem nenhuma mudança adicional.

**Assinaturas (pedido do Lucas):** seguro/Netflix como despesa fixa com `forma_pagamento_id` do cartão já caem na fatura certa com essa regra; parcelados idem via parcelamento. Criar categoria "Assinaturas" para essas fixas (dado, junto do script A).

---

## C. Limite rotativo real

**Problema:** com B, o "gasto do mês" do cartão vira a fatura a pagar — não diz quanto do limite está comprometido agora.

**Modelo:** limite usado = tudo que ainda não foi coberto por fatura paga.

1. Migração `021`: tabela `faturas_pagas (id, forma_pagamento_id, competencia DATE, paga_em TIMESTAMPTZ, UNIQUE(forma_pagamento_id, competencia))`.
2. `limite_usado(forma) = SUM(gastos da forma) − SUM(gastos de competências marcadas como pagas)`. Cobre naturalmente parcelas futuras (comprometem limite, como no cartão real) e fatura fechada não paga.
3. Marcação: comando no bot ("paguei a fatura nubank") + botão na web → INSERT em `faturas_pagas`. Idempotente pelo UNIQUE.
4. Exibição (bot "saldo" + dashboard), por cartão: fatura aberta (competência do próximo vencimento), fatura fechada a pagar (competência do mês corrente sem registro de paga), limite disponível (`limite_mensal − limite_usado`).
5. `pct_limite_medio` do resumo passa a usar `limite_usado` para formas com `dia_fechamento`; formas sem fechamento continuam na regra atual (gasto do mês vs limite).

**Simplificação assumida:** faturas antigas do histórico serão marcadas como pagas em lote no backfill (`INSERT ... SELECT` de competências < mês corrente), senão o limite nasceria "estourado" por dívida que já foi quitada.

---

## D. WhatsApp opcional no cadastro

**Restrição inegociável (F2 da auditoria):** telefone de formulário só é usado após OTP. O campo novo é pré-preenchimento, não substituição da verificação.

1. `cadastro/page.jsx`: campo "WhatsApp (opcional)" com `TelefoneInput`; no submit, salva em `localStorage` (`WHATSAPP_PENDENTE_KEY`, mesmo padrão de `CONVITE_PENDENTE_KEY` para atravessar a confirmação de e-mail).
2. `CompletarCadastro`: se existe número pendente, pré-preenche o passo de telefone (pessoa só clica "Enviar código"). Limpa a chave após verificação.
3. Sem mudança de backend.

---

## E. Bug: forma detectada é descartada no fluxo guiado

**Caso real (17/07/2026):** "VA atualizacao 264" → bot pergunta categoria (correto, não há) e depois pergunta forma — mas "VA" tinha sido detectada.

**Causa:** não é o parser (`extrair_forma_pagamento` retorna VA nesse texto — reproduzido em teste). É o handler: `_processar_input_livre` salva `forma_temp` na sessão, mas o passo `aguardando_categoria` (handler.py:512-520) transiciona incondicionalmente para `aguardando_pagamento` e mostra o menu, ignorando o `forma_temp` salvo.

**Correção:**
1. `aguardando_categoria`: se `sessao["forma_temp"]` existe, registrar direto após a escolha da categoria (mesmo caminho do `aguardando_pagamento`), sem menu de forma.
2. Bugs adjacentes do parser, revelados ao reproduzir:
   - `"50 no credito"` → None: match é sensível a acento ("crédito" no banco vs "credito" digitado) e o grupo de aliases de cartão só se aplica a formas cujo **nome** contém "cart" — "CRÉDITO" fica de fora. Corrigir com normalização de acentos (NFD) nos dois lados e ampliar o gatilho do grupo de aliases.
   - `"vaquinha 30"` → casa falsamente com "VA": substring sem fronteira de palavra. Trocar por comparação de tokens.
3. Descrição perdida no fluxo guiado: `_processar_sessao` registra com `descricao=""` (handler.py:539-540) — o texto original não é guardado na sessão. Salvar a mensagem em `dados_temp` e usá-la no registro ("VA atualizacao 264" deve virar descrição "atualizacao").
4. Testes: casos novos em `tests/` cobrindo os três (forma pré-detectada + acento + fronteira de palavra).

## Ordem de execução

1. **B** (migrações 019/020 + `calcular_competencia` + testes) — base de tudo.
2. **C** (migração 021 + saldo/resumo + comando/botão fatura paga) — depende de B.
3. **A** (script de dados Custo Fixo + categoria Assinaturas) — independente, mas rodar depois de B pra backfillar uma vez só.
4. **E** (bug do fluxo guiado + parser) — independente, pode sair primeiro se quiser hotfix.
5. **D** (front do cadastro) — independente.

Deploy: migrações rodam no Railway via `database/migrate` no deploy; o script A o Lucas roda local (a sandbox do Claude não alcança o host do Supabase).

## Pendências

- Lista de quais fixas são débito/PIX (viram Custo Fixo) vs cartão (ficam como estão).
- `dia_vencimento` de cada cartão cadastrado.
