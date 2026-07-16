import styled from "styled-components";

export const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: ${({ theme }) => theme.spacing(5)};
`;

// minmax(340px, 1fr) sozinho força cada card a ter NO MÍNIMO 340px — numa
// tela de celular mais estreita que isso (340px + padding da página passa
// da largura de vários aparelhos), o grid empurra conteúdo pra fora em vez
// de encolher, e é isso que corta a tela. minmax(min(340px, 100%), 1fr) é o
// mesmo comportamento no desktop (várias colunas de 340px+), mas nunca deixa
// a coluna passar de 100% do espaço disponível — vira 1 coluna sozinha
// numa tela estreita, sem precisar de media query separada.
export const StatsRow = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(180px, 100%), 1fr));
  gap: ${({ theme }) => theme.spacing(4)};
  margin-bottom: ${({ theme }) => theme.spacing(6)};
`;

export const ChartsGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(340px, 100%), 1fr));
  gap: ${({ theme }) => theme.spacing(5)};
`;

export const ChartCard = styled.div`
  background: ${({ theme }) => theme.colors.surface};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.lg};
  padding: ${({ theme }) => theme.spacing(5)};
`;

export const ChartTitulo = styled.h3`
  font-size: 14px;
  color: ${({ theme }) => theme.colors.textMuted};
  margin-bottom: ${({ theme }) => theme.spacing(3)};
  font-weight: 500;
`;
