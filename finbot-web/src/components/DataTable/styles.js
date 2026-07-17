import styled from "styled-components";

// Tabelas com muitas colunas (gastos: Data/Descrição/Categoria/Forma/
// Membro/Origem/Valor + Ações) não cabem numa tela de celular de jeito
// nenhum — sem esse wrapper, width:100% na Table forçava as colunas a
// espremer/sobrepor em vez de simplesmente rolar horizontalmente, que é o
// comportamento esperado numa tabela grande em tela pequena.
export const TableWrap = styled.div`
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
`;

export const Table = styled.table`
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
`;

export const Th = styled.th`
  text-align: left;
  padding: ${({ theme }) => theme.spacing(2)} ${({ theme }) => theme.spacing(3)};
  color: ${({ theme }) => theme.colors.textMuted};
  border-bottom: 1px solid ${({ theme }) => theme.colors.border};
  font-weight: 500;
`;

export const Td = styled.td`
  padding: ${({ theme }) => theme.spacing(2)} ${({ theme }) => theme.spacing(3)};
  border-bottom: 1px solid ${({ theme }) => theme.colors.border};
`;

export const Tr = styled.tr`
  &:hover {
    background: ${({ theme }) => theme.colors.surfaceAlt};
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

  &:hover {
    text-decoration: underline;
  }
`;
