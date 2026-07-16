import styled from "styled-components";

// Fundo escurecido atrás do menu gaveta no mobile — clicar nele fecha o
// menu (mesmo padrão do Overlay de components/Modal). Só existe abaixo de
// 860px; no desktop a sidebar é fixa na tela, não precisa de overlay.
export const Overlay = styled.div`
  display: none;

  @media (max-width: 860px) {
    display: ${({ $aberta }) => ($aberta ? "block" : "none")};
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 90;
  }
`;

export const Nav = styled.nav`
  width: 220px;
  min-height: 100vh;
  background: ${({ theme }) => theme.colors.surface};
  border-right: 1px solid ${({ theme }) => theme.colors.border};
  padding: ${({ theme }) => theme.spacing(4)};
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing(1)};

  // Abaixo de 860px, 220px fixos ao lado do conteúdo não cabem numa tela de
  // celular (era isso que "cortava" a tela) — a sidebar vira um menu gaveta
  // que desliza por cima do conteúdo em vez de dividir a largura com ele.
  @media (max-width: 860px) {
    position: fixed;
    inset: 0 auto 0 0;
    z-index: 100;
    transform: translateX(${({ $aberta }) => ($aberta ? "0" : "-100%")});
    transition: transform 0.2s ease;
  }
`;

export const Logo = styled.div`
  font-weight: 700;
  font-size: 18px;
  margin-bottom: ${({ theme }) => theme.spacing(6)};
`;

export const ItemLink = styled.a`
  padding: ${({ theme }) => theme.spacing(2)} ${({ theme }) => theme.spacing(3)};
  border-radius: ${({ theme }) => theme.radius.sm};
  color: ${({ theme, $ativo }) => ($ativo ? theme.colors.text : theme.colors.textMuted)};
  background: ${({ theme, $ativo }) => ($ativo ? theme.colors.surfaceAlt : "transparent")};
  font-size: 14px;

  &:hover {
    background: ${({ theme }) => theme.colors.surfaceAlt};
    color: ${({ theme }) => theme.colors.text};
  }
`;
