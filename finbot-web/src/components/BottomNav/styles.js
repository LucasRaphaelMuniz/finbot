import styled, { css } from "styled-components";

export const ALTURA_BOTTOM_NAV = 64;

export const Barra = styled.nav`
  display: none;

  @media (max-width: 860px) {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    align-items: center;
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 80;
    height: calc(${ALTURA_BOTTOM_NAV}px + env(safe-area-inset-bottom));
    padding-bottom: env(safe-area-inset-bottom);
    background: ${({ theme }) => theme.colors.surface};
    border-top: 1px solid ${({ theme }) => theme.colors.border};
  }
`;

const estiloAba = css`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  height: 100%;
  min-width: 0;
  background: none;
  border: none;
  font: inherit;
  font-size: 11px;
  font-weight: ${({ $ativo }) => ($ativo ? 600 : 400)};
  text-decoration: none;
  cursor: pointer;
  color: ${({ theme, $ativo }) => ($ativo ? theme.colors.primary : theme.colors.textMuted)};
`;

export const AbaLink = styled.a`
  ${estiloAba}
`;

export const Aba = styled.button`
  ${estiloAba}
`;

// "+" central: único botão sólido da barra — é a ação mais frequente.
export const Mais = styled.button`
  justify-self: center;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  border: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: ${({ theme }) => theme.colors.primarySolid};
  color: #fff;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.35);
`;
