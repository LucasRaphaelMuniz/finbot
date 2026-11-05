import styled, { keyframes } from "styled-components";

// Tabelas com muitas colunas (gastos: Data/Descrição/Categoria/Forma/
// Membro/Origem/Valor + Ações) não cabem numa tela de celular de jeito
// nenhum — sem esse wrapper, width:100% na Table forçava as colunas a
// espremer/sobrepor em vez de simplesmente rolar horizontalmente, que é o
// comportamento esperado numa tabela grande em tela pequena.
// Abaixo de 640px a tabela vira lista de cards (auditoria de UX,
// 05/11/2026): com rolagem horizontal, Lançamentos tinha 813px num
// container de 327px — Valor e Editar/Excluir ficavam fora da tela. Cada
// linha vira um card; cada célula, "Rótulo ..... valor" via data-label.
const MOBILE = "@media (max-width: 640px)";

export const TableWrap = styled.div`
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
`;

export const Table = styled.table`
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;

  ${MOBILE} {
    /* display:none (não só visualmente escondido): os botões de ordenar
       virariam paradas de Tab invisíveis. O rótulo de cada valor já vem
       no próprio card, pelo data-label. */
    thead {
      display: none;
    }

    tbody {
      display: flex;
      flex-direction: column;
      gap: ${({ theme }) => theme.spacing(2)};
    }
  }
`;

export const Th = styled.th`
  text-align: ${({ $numerico }) => ($numerico ? "right" : "left")};
  padding: ${({ theme }) => theme.spacing(2)} ${({ theme }) => theme.spacing(3)};
  color: ${({ theme }) => theme.colors.textMuted};
  border-bottom: 1px solid ${({ theme }) => theme.colors.border};
  font-weight: 500;
  user-select: none;

`;

export const Td = styled.td`
  padding: ${({ theme }) => theme.spacing(2)} ${({ theme }) => theme.spacing(3)};
  border-bottom: 1px solid ${({ theme }) => theme.colors.border};
  ${({ $numerico }) => $numerico && `
    text-align: right;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  `}

  ${MOBILE} {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: ${({ theme }) => theme.spacing(3)};
    padding: ${({ theme }) => theme.spacing(1)} 0;
    border-bottom: none;
    text-align: right;

    &::before {
      content: attr(data-label);
      color: ${({ theme }) => theme.colors.textMuted};
      font-size: 13px;
      text-align: left;
      flex-shrink: 0;
    }

    /* célula vazia não vira um "Rótulo" solto no card */
    &:empty {
      display: none;
    }
  }
`;

export const OrdenarBtn = styled.button`
  background: none;
  border: none;
  padding: 0;
  color: inherit;
  font: inherit;
  cursor: pointer;

  &:hover:not(:disabled) {
    color: ${({ theme }) => theme.colors.text};
  }
`;

export const Tr = styled.tr`
  &:hover {
    background: ${({ theme }) => theme.colors.surfaceAlt};
  }

  ${MOBILE} {
    display: block;
    background: ${({ theme }) => theme.colors.surface};
    border: 1px solid ${({ theme }) => theme.colors.border};
    border-radius: ${({ theme }) => theme.radius.md};
    padding: ${({ theme }) => theme.spacing(3)} ${({ theme }) => theme.spacing(4)};

    &:hover {
      background: ${({ theme }) => theme.colors.surface};
    }
  }

  // Linha "prevista, não definitiva" (custo fixo ainda não lançado de
  // verdade pelo cron) — itálico + opacidade reduzida em vez de cor própria,
  // pra continuar legível nos dois temas (dark/light) sem depender de mais
  // uma cor no design system só pra isso.
  ${({ $atenuada }) => $atenuada && `
    font-style: italic;
    opacity: 0.65;
  `}
`;

// Antes tinha display:flex direto aqui — um <td> com display:flex deixa de
// se comportar como table-cell (sai do table-layout normal). Numa linha
// onde essa célula fica vazia (categoria padrão sem Editar/Remover), a
// borda inferior dela não alinha mais com a altura das colunas vizinhas —
// aparece como a linha divisória "quebrando" bem na coluna Ações. Fix:
// <td> continua puro table-cell (border/altura corretos), o flex vai pra
// uma div por dentro.
export const AcoesTd = styled(Td)`
  text-align: right;

  ${MOBILE} {
    display: block;
    margin-top: ${({ theme }) => theme.spacing(2)};
    padding-top: ${({ theme }) => theme.spacing(1)};
    border-top: 1px solid ${({ theme }) => theme.colors.border};

    &::before {
      content: none;
    }
  }
`;

export const AcoesFlex = styled.div`
  display: flex;
  gap: ${({ theme }) => theme.spacing(2)};
  justify-content: flex-end;
`;

export const AcaoBtn = styled.button`
  background: transparent;
  border: none;
  color: ${({ theme, $perigo }) => ($perigo ? theme.colors.danger : theme.colors.primary)};
  cursor: pointer;
  font-size: 13px;

  /* alvo de toque de 44px no celular (no desktop segue link compacto) */
  ${MOBILE} {
    min-height: 44px;
    font-size: 14px;
  }

  &:hover {
    text-decoration: underline;
  }
`;

const pulsar = keyframes`
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
`;

// Barra cinza no lugar do texto enquanto carrega. Só opacity anima; com
// prefers-reduced-motion fica parada.
export const Skeleton = styled.span`
  display: inline-block;
  width: 70%;
  max-width: 140px;
  height: 12px;
  border-radius: 4px;
  background: ${({ theme }) => theme.colors.surfaceAlt};
  animation: ${pulsar} 1.4s ease-in-out infinite;

  @media (prefers-reduced-motion: reduce) {
    animation: none;
  }
`;
