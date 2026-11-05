import styled from "styled-components";

export const Topo = styled.div`
  margin-bottom: ${({ theme }) => theme.spacing(5)};
`;

export const Titulo = styled.h1`
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.01em;
  margin-bottom: ${({ theme }) => theme.spacing(4)};
`;

// Abas sublinhadas; no celular rolam na horizontal (5 abas não cabem em
// 375px) sem empurrar a largura da página.
export const Abas = styled.nav`
  display: flex;
  gap: ${({ theme }) => theme.spacing(1)};
  border-bottom: 1px solid ${({ theme }) => theme.colors.border};
  overflow-x: auto;
  scrollbar-width: none;

  &::-webkit-scrollbar {
    display: none;
  }

  @media (max-width: 860px) {
    margin: 0 -${({ theme }) => theme.spacing(4)};
    padding: 0 ${({ theme }) => theme.spacing(4)};
  }
`;

export const Aba = styled.a`
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  padding: 0 ${({ theme }) => theme.spacing(3)};
  margin-bottom: -1px;
  border-bottom: 2px solid transparent;
  color: ${({ theme }) => theme.colors.textMuted};
  font-size: 14px;
  font-weight: 500;
  text-decoration: none;
  white-space: nowrap;

  &:hover {
    color: ${({ theme }) => theme.colors.text};
  }

  &[aria-current="page"] {
    color: ${({ theme }) => theme.colors.text};
    border-bottom-color: ${({ theme }) => theme.colors.primary};
    font-weight: 600;
  }

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.primary};
    outline-offset: -2px;
  }
`;

export const Conteudo = styled.div``;
