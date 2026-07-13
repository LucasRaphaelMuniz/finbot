# Benchmarking de mercado — Fase 0

> Entregável da Fase 0 do `PLANO_EXECUCAO.md`. Pesquisa via busca web (11/07/2026), sem acesso direto aos apps — baseada em documentação oficial, central de ajuda e cobertura de imprensa de cada produto. Objetivo: orientar layout das Fases 5 (telas web) e 6 (SaaS).

## Nota sobre o GuiaBolso

Confirmado: GuiaBolso foi descontinuado em novembro/2022, após ser comprado pelo PicPay em 2021 — todas as funcionalidades (categorização, oferta de crédito, consulta de CPF) foram absorvidas pelo app PicPay. Não serve mais como referência de produto standalone. Substituído nesta pesquisa por **Nubank** (app bancário com controle de gastos nativo, categorização automática e alta base de usuários no Brasil), que é hoje a referência mais citada como sucessora de facto do GuiaBolso.

## ZapGastos (referência principal — mesmo canal WhatsApp do finbot)

- Dashboard web separado do chat: os lançamentos rápidos feitos por WhatsApp viram gráficos numa tela web à parte — o chat é só entrada de dado, a análise vive num painel dedicado.
- "Saldo Previsto": projeção de fim de mês considerando contas fixas que ainda vão vencer e receitas agendadas, não só o saldo atual.
- "Teto por Categoria": limite de gasto por categoria (lazer, alimentação, transporte) com aviso antes de estourar.
- "Score de Saúde": nota única e automática que resume a situação financeira do mês — reduz o dashboard a um número central antes de detalhar.
- Reconciliação automática: gasto lançado por WhatsApp já cai conciliado na fatura do cartão correspondente, sem passo manual de "importar depois".

**Decisão de layout derivada:** o `/dashboard` do finbot-web deve abrir com 1 número-resumo no topo (saldo do mês / status geral) antes dos gráficos detalhados — não jogar o usuário direto em 4 gráficos sem hierarquia. Ver `StatCards` na Fase 5.2, que já cobre isso; adicionar "saldo previsto" (entradas − gastos incluindo fixas ainda não lançadas) como um dos StatCards.

## Mobills

- Dashboard customizável: usuário escolhe o que aparece na tela inicial (contas, cartões, receitas, despesas) em vez de layout fixo.
- Despesas fixas de cartão têm comportamento próprio: não aparecem "fantasma" nos meses seguintes consumindo limite — só materializam na fatura no dia programado.
- Importação de fatura via planilha (Excel/CSV) como caminho manual, complementar à integração bancária automática.
- Separação clara entre "despesa fixa normal" e "despesa fixa de cartão" na edição — evita confundir competência de fatura com data de lançamento.

**Decisão de layout derivada:** na tela `/fixas`, quando a despesa fixa estiver associada a uma forma com `dia_fechamento` (cartão), mostrar explicitamente em qual competência ela vai cair antes de salvar — mesmo aviso que o plano já previu para `/formas` (Fase 5.5), estender para o cadastro de despesa fixa também.

## Organizze

- Relatórios de receita/despesa mensal ficam numa aba própria ("Relatórios"), separada da tela de lançamentos — reforça o mesmo padrão do ZapGastos (lançar ≠ analisar, telas diferentes).
- Despesa fixa é configurada como atributo do lançamento ("Repetir lançamento > fixo > mensal"), não como cadastro separado — fluxo mais raso, mas menos explícito sobre qual é a "regra" fixa vigente.
- Importação de extrato de cartão inclui leitura de notificações do app do banco, além do CSV/PDF tradicional — foge do escopo do finbot, mas confirma que importação de fatura é feature esperada por usuário desse segmento.

**Decisão de layout derivada:** manter a decisão já tomada no plano de despesa fixa como **tabela própria** (`despesas_fixas`), não atributo do lançamento — mais alinhado ao Mobills que ao Organizze, porque o finbot precisa do lançador idempotente (Fase 3.3) e isso exige uma "regra" persistente e editável, não um flag por lançamento.

## Nubank (substituto do GuiaBolso)

- "Organizar Gastos": categorização automática divide gastos em Essencial / Livre / Outros, combinando débito e crédito num único total — camada de leitura acima das categorias granulares (mercado, transporte etc.).
- Metas mensais por categoria com indicador visual de progresso, revisado semanalmente pelo próprio app.
- Categorização automática erra com frequência (ex.: presente comprado em supermercado vira "alimentação") — ponto de atenção, não de imitação.

**Decisão de layout derivada:** no `/dashboard`, considerar uma segunda camada de agrupamento (fixo × variável, já previsto na Fase 5.2 como `ChartFixoVariavel`) como o equivalente do "Essencial/Livre/Outros" do Nubank — já coberto pelo plano, sem necessidade de adicionar novo componente.

## Síntese para as Fases 5–6

1. Separar sempre "lançar" de "analisar" em telas distintas — os 3 apps de referência (ZapGastos, Mobills, Organizze) fazem isso; o plano do finbot já segue esse padrão (`/lancamentos` × `/dashboard`).
2. Abrir o dashboard com 1 indicador-resumo (saldo/score) antes dos gráficos — ajuste a incorporar no `/dashboard` (StatCard de saldo previsto).
3. Despesa fixa como cadastro próprio, com competência calculada a partir do `dia_fechamento` quando ligada a cartão — confirma decisão já tomada (tabela `despesas_fixas`), reforça o aviso de competência também no cadastro, não só na tela de formas.
4. Segunda camada de agrupamento fixo×variável no dashboard — já coberta pelo plano (`ChartFixoVariavel`), nenhuma mudança necessária.
5. Nenhum dos 4 apps pesquisados expõe conciliação/importação como fluxo trivial de 1 clique sem revisão — reforça a decisão já tomada na Fase 5.3 (importação em 3 passos com revisão editável e confirmação explícita).

## Fontes

- [ZapGastos — Assistente](https://zapgastos.com/assistente/)
- [ZapGastos — Dashboard de Despesas Pessoais](https://zapgastos.com/blog/dashboard-despesas-pessoais/)
- [Mobills — Como utilizar](https://www.mobills.com.br/blog/mobills/como-utilizar-o-mobills/)
- [Mobills — Despesas fixas de cartão de crédito](https://mobills.zendesk.com/hc/pt-br/articles/4414666860059-Por-que-as-despesas-fixas-do-cart%C3%A3o-de-cr%C3%A9dito-n%C3%A3o-aparecem-nos-pr%C3%B3ximos-meses)
- [Mobills — Como importar despesas de cartão de crédito (YouTube)](https://www.youtube.com/watch?v=IKLliiv_na4)
- [Organizze — Como usar (Canaltech)](https://canaltech.com.br/apps/como-usar-organizze/)
- [Organizze — App de gastos mensais](https://www.organizze.com.br/blog/controle-de-gastos/app-de-gastos-mensais)
- [PicPay — PicPay integra ferramentas do Guiabolso e encerra o app](https://blog.picpay.com/picpay-desliga-guiabolso/)
- [Mobills — Guiabolso vai acabar, e agora?](https://www.mobills.com.br/blog/aplicativos/guiabolso-vai-acabar-e-agora/)
- [ZapGastos — Controle Financeiro Nubank](https://zapgastos.com/blog/controle-financeiro-nubank/)
- [NuCommunity — Chegou o Organizar Gastos](https://comunidade.nubank.com.br/t/chegou-o-organizar-gastos-perfeito-para-as-finan%C3%A7as-%F0%9F%A4%91/456471)
- [NuCommunity — Categorização automática](https://comunidade.nubank.com.br/vida-financeira/post/categorizacao-das-despesas-automaticamente---tem-como-fazer-I1hSSgVyMnLMeQj)
