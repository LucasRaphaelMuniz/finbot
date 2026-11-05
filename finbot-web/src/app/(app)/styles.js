import styled from "styled-components";
import { ALTURA_BOTTOM_NAV } from "@/components/BottomNav/styles";

export const Shell = styled.div`
  display: flex;
  min-height: 100vh;
`;

export const Coluna = styled.div`
  flex: 1;
  min-width: 0;
`;

// Largura máxima: em monitor largo o conteúdo esticava até a borda e os
// valores à direita ficavam longe demais dos rótulos à esquerda.
export const Main = styled.main`
  padding: ${({ theme }) => theme.spacing(6)};
  max-width: 1200px;

  /* espaço pra BottomNav fixa não cobrir o fim da página */
  @media (max-width: 860px) {
    padding: ${({ theme }) => theme.spacing(4)};
    padding-bottom: calc(${ALTURA_BOTTOM_NAV}px + env(safe-area-inset-bottom) + 24px);
  }
`;
