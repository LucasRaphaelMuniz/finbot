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

// Popup de detalhe ao clicar numa barra do gráfico "últimos 6 meses"
// (pedido do Lucas, 24/07/2026). Mesmo desenho de components/Modal + lista
// usado em (app)/contas/styles.js pro detalhe de fatura — duplicado aqui
// (poucas linhas) em vez de compartilhado entre páginas, mesmo padrão já
// usado no projeto de cada tela ter seu styles.js próprio.
export const ListaDetalhe = styled.div`
  min-width: 320px;
  max-width: 420px;
  max-height: 50vh;
  overflow-y: auto;
`;

export const ItemDetalhe = styled.div`
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: ${({ theme }) => theme.spacing(3)};
  padding: ${({ theme }) => theme.spacing(2)} 0;
  border-bottom: 1px solid ${({ theme }) => theme.colors.border};
  font-size: 14px;

  &:last-child {
    border-bottom: none;
  }
`;

export const TextoMuted = styled.div`
  font-size: 12px;
  color: ${({ theme }) => theme.colors.textMuted};
  margin-top: 2px;
`;

// Linha clicável de forma de pagamento (24/07/2026, pedido do Lucas: "abre
// primeiro pela forma de pagamento, clicar expande o detalhamento"). Usa
// <button> de propósito (não div+onClick) — foco por teclado e semântica
// de "isto é acionável" de graça.
export const GrupoForma = styled.button`
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: ${({ theme }) => theme.spacing(3)};
  padding: ${({ theme }) => theme.spacing(3)} 0;
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

// Item dentro de um grupo expandido — mesmo desenho de ItemDetalhe, só
// recuado e sem borda própria (a borda de baixo do grupo/último item já
// separa visualmente do próximo grupo).
export const ItemAninhado = styled.div`
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: ${({ theme }) => theme.spacing(3)};
  padding: ${({ theme }) => theme.spacing(2)} 0 ${({ theme }) => theme.spacing(2)} ${({ theme }) => theme.spacing(5)};
  font-size: 13px;

  &:last-child {
    border-bottom: 1px solid ${({ theme }) => theme.colors.border};
  }
`;
