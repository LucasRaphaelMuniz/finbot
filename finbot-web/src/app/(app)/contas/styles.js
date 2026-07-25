import styled from "styled-components";

export const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: ${({ theme }) => theme.spacing(3)};
  margin-bottom: ${({ theme }) => theme.spacing(5)};
`;

// 3 colunas como na planilha (Entradas | Não pagos | Pagos). Mesmo truque de
// minmax(min(...), 100%) do dashboard: no celular vira 1 coluna sozinho, sem
// media query, e nunca estoura a largura da tela.
export const Board = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(300px, 100%), 1fr));
  gap: ${({ theme }) => theme.spacing(4)};
  align-items: start;
`;

export const Coluna = styled.section`
  background: ${({ theme }) => theme.colors.surface};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.lg};
  padding: ${({ theme }) => theme.spacing(4)};
  min-height: 160px;
  transition: border-color 120ms, background 120ms;

  /* Realce durante o arraste — só na coluna que aceita o card sendo
     arrastado (o pai controla via $alvo), pra não piscar a tela toda. */
  ${({ $alvo, theme }) =>
    $alvo &&
    `
      border-color: ${theme.colors.primary};
      background: ${theme.colors.surfaceAlt};
    `}
`;

export const ColunaHeader = styled.header`
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: ${({ theme }) => theme.spacing(2)};
  padding-bottom: ${({ theme }) => theme.spacing(3)};
  margin-bottom: ${({ theme }) => theme.spacing(3)};
  border-bottom: 1px solid ${({ theme }) => theme.colors.border};
`;

export const ColunaTitulo = styled.h2`
  font-size: 14px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: ${({ theme }) => theme.colors.textMuted};
`;

export const ColunaTotal = styled.span`
  font-size: 15px;
  font-weight: 600;
  color: ${({ theme, $tom }) =>
    $tom === "sucesso" ? theme.colors.success
      : $tom === "erro" ? theme.colors.danger
      : theme.colors.text};
`;

export const Card = styled.article`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing(3)};
  background: ${({ theme }) => theme.colors.surfaceAlt};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-left: 3px solid
    ${({ theme, $origem }) =>
      $origem === "fatura" ? theme.colors.warning
        : $origem === "previsto" ? theme.colors.border
        : theme.colors.primary};
  border-radius: ${({ theme }) => theme.radius.md};
  padding: ${({ theme }) => theme.spacing(3)};
  margin-bottom: ${({ theme }) => theme.spacing(2)};
  cursor: ${({ $arrastavel }) => ($arrastavel ? "grab" : "default")};
  opacity: ${({ $arrastando, $origem }) =>
    $arrastando ? 0.4 : $origem === "previsto" ? 0.65 : 1};

  &:active {
    cursor: ${({ $arrastavel }) => ($arrastavel ? "grabbing" : "default")};
  }
`;

export const CardInfo = styled.div`
  flex: 1;
  min-width: 0;
`;

export const CardTitulo = styled.div`
  font-size: 14px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
`;

export const CardDetalhe = styled.div`
  font-size: 12px;
  color: ${({ theme }) => theme.colors.textMuted};
  margin-top: 2px;
`;

export const CardValor = styled.button`
  background: none;
  border: 1px dashed
    ${({ theme, $editavel }) => ($editavel ? theme.colors.border : "transparent")};
  border-radius: ${({ theme }) => theme.radius.sm};
  padding: 2px 6px;
  font-size: 14px;
  font-weight: 600;
  font-family: inherit;
  color: ${({ theme }) => theme.colors.text};
  cursor: ${({ $editavel }) => ($editavel ? "text" : "default")};
  text-align: right;
  white-space: nowrap;

  /* Borda tracejada sempre visível (não só no hover) quando editável — em
     toque não existe hover pra revelar que o valor é clicável, e no
     desktop também não devia depender de passar o mouse por cima pra
     descobrir. */
  &:hover {
    border-color: ${({ theme, $editavel }) =>
      $editavel ? theme.colors.primary : "transparent"};
  }
`;

export const ValorRiscado = styled.span`
  display: block;
  font-size: 11px;
  font-weight: 400;
  text-decoration: line-through;
  color: ${({ theme }) => theme.colors.textMuted};
`;

// Botão que faz o mesmo que arrastar. Não é fallback de acessibilidade
// jogado num canto: drag nativo do HTML5 não dispara em toque, então no
// celular ELE é o único caminho — e o app tem menu gaveta mobile, logo é
// usado no celular de verdade.
export const BotaoMover = styled.button`
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: ${({ theme }) => theme.radius.sm};
  border: 1px solid ${({ theme }) => theme.colors.border};
  background: ${({ theme }) => theme.colors.surface};
  cursor: pointer;

  &:hover:not(:disabled) {
    border-color: ${({ theme }) => theme.colors.primary};
  }

  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
`;

// Bolinha preenchida dentro do BotaoMover (pedido do Lucas, 24/07/2026):
// vermelha vazia em não pago, verde com check branco em pago — em vez do
// glifo de texto solto (○/✓) que tinha antes, que dependia da fonte do SO
// pra parecer alguma coisa e ficava pequeno/apagado. Elemento próprio (não
// glifo) dá controle real de tamanho/cor, igual qualquer badge de status.
export const Indicador = styled.span`
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: ${({ theme, $pago }) => ($pago ? theme.colors.success : theme.colors.danger)};
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
`;

export const InputValor = styled.input`
  width: 110px;
  padding: 4px 6px;
  font-size: 14px;
  font-family: inherit;
  text-align: right;
  color: ${({ theme }) => theme.colors.text};
  background: ${({ theme }) => theme.colors.bg};
  border: 1px solid ${({ theme }) => theme.colors.primary};
  border-radius: ${({ theme }) => theme.radius.sm};
`;

export const Vazio = styled.p`
  font-size: 13px;
  color: ${({ theme }) => theme.colors.textMuted};
  text-align: center;
  padding: ${({ theme }) => theme.spacing(6)} 0;
`;

// min/max-width e padding aumentados (pedido do Lucas, 24/07/2026: "esta
// muito colado") — o modal de detalhe de fatura usa a largura padrão de
// Modal (480px) e cabia pouco: item, categoria e valor quase se tocando.
// Aumenta o respiro entre linhas (padding vertical) e a largura útil junto
// com o `largura` maior passado ao <Modal> em DetalheFatura.
export const ListaDetalhe = styled.div`
  min-width: 320px;
  max-width: 560px;
  max-height: 55vh;
  overflow-y: auto;
`;

export const ItemDetalhe = styled.div`
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: ${({ theme }) => theme.spacing(4)};
  padding: ${({ theme }) => theme.spacing(3)} ${({ theme }) => theme.spacing(1)};
  border-bottom: 1px solid ${({ theme }) => theme.colors.border};
  font-size: 14px;
  line-height: 1.6;

  &:last-child {
    border-bottom: none;
  }
`;

// Cabeçalho clicável de um grupo de categoria (classificação por tipo de
// despesa, mesmo pedido). Espelha dashboard/styles.js::GrupoForma — mesmo
// padrão de "linha clicável que expande", só que agrupando por categoria
// em vez de forma de pagamento (aqui já se sabe a forma: é a fatura
// clicada, o que falta discriminar é o tipo de gasto dentro dela).
export const GrupoCategoria = styled.button`
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: ${({ theme }) => theme.spacing(3)};
  padding: ${({ theme }) => theme.spacing(3)} ${({ theme }) => theme.spacing(1)};
  border: none;
  border-bottom: 1px solid ${({ theme }) => theme.colors.border};
  background: none;
  color: ${({ theme }) => theme.colors.text};
  font-family: inherit;
  font-size: 14px;
  font-weight: 600;
  text-align: left;
  cursor: pointer;

  &:hover {
    color: ${({ theme }) => theme.colors.primary};
  }
`;

export const ItemAninhado = styled.div`
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: ${({ theme }) => theme.spacing(4)};
  padding: ${({ theme }) => theme.spacing(2.5)} ${({ theme }) => theme.spacing(1)}
    ${({ theme }) => theme.spacing(2.5)} ${({ theme }) => theme.spacing(5)};
  font-size: 13px;
  line-height: 1.6;
  border-bottom: 1px solid ${({ theme }) => theme.colors.border};

  &:last-child {
    border-bottom: none;
  }
`;

// Filtro por categoria (pedido do Lucas: "um filtro ou classificação por
// tipo de despesa") — select simples em vez de botões/chips: a lista de
// categorias é variável e pode crescer, um select escala sem quebrar
// layout. "Todas" (valor "") mostra os grupos; escolher uma categoria
// filtra pra só ela, já expandida (não faz sentido esconder atrás de um
// cabeçalho de grupo quando é o único que sobrou).
export const SeletorCategoria = styled.select`
  background: ${({ theme }) => theme.colors.surfaceAlt};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.sm};
  padding: ${({ theme }) => theme.spacing(2)} ${({ theme }) => theme.spacing(3)};
  font-size: 13px;
  color: ${({ theme }) => theme.colors.text};
  margin-bottom: ${({ theme }) => theme.spacing(3)};

  &:focus {
    outline: none;
    border-color: ${({ theme }) => theme.colors.primary};
  }
`;

export const BotaoNovaEntrada = styled.button`
  width: 100%;
  padding: ${({ theme }) => theme.spacing(3)};
  margin-top: ${({ theme }) => theme.spacing(1)};
  background: none;
  border: 1px dashed ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.md};
  color: ${({ theme }) => theme.colors.textMuted};
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;

  &:hover {
    border-color: ${({ theme }) => theme.colors.primary};
    color: ${({ theme }) => theme.colors.primary};
  }
`;

export const FormNovaEntrada = styled.form`
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: ${({ theme }) => theme.spacing(2)};
  padding: ${({ theme }) => theme.spacing(3)};
  margin-top: ${({ theme }) => theme.spacing(1)};
  background: ${({ theme }) => theme.colors.surfaceAlt};
  border: 1px solid ${({ theme }) => theme.colors.primary};
  border-radius: ${({ theme }) => theme.radius.md};

  button {
    font-size: 13px;
  }
`;

// Campo de descrição do formulário de nova entrada. Antes era um <input>
// cru sem styled-component — só herdava font-family/size/color do reset
// global (global.js só estiliza background/border pra <button>, não pra
// <input>), então ficava com a caixa branca padrão do navegador destoando
// do resto do tema escuro (relato do Lucas, 24/07/2026: "sem estilização").
// Mesmo visual de MoneyInput/styles.js::Input, só que flex em vez de 100%
// (aqui divide a linha com valor/dia/botões, lá é campo único).
export const CampoDescricao = styled.input`
  flex: 1;
  min-width: 100px;
  background: ${({ theme }) => theme.colors.surfaceAlt};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.sm};
  padding: ${({ theme }) => theme.spacing(2.5)} ${({ theme }) => theme.spacing(3)};
  font-size: 13px;
  color: ${({ theme }) => theme.colors.text};

  &:focus {
    outline: none;
    border-color: ${({ theme }) => theme.colors.primary};
  }
`;

// Mesmo problema do CampoDescricao acima: só tinha width/text-align, sem
// nenhuma cor/fundo/borda própria — caía no input branco padrão do SO.
export const CampoDia = styled.input`
  width: 48px;
  text-align: center;
  background: ${({ theme }) => theme.colors.surfaceAlt};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.sm};
  padding: ${({ theme }) => theme.spacing(2.5)} ${({ theme }) => theme.spacing(1)};
  font-size: 13px;
  color: ${({ theme }) => theme.colors.text};

  &:focus {
    outline: none;
    border-color: ${({ theme }) => theme.colors.primary};
  }
`;

export const Resumo = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(180px, 100%), 1fr));
  gap: ${({ theme }) => theme.spacing(4)};
  margin-bottom: ${({ theme }) => theme.spacing(5)};
`;
