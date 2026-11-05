import styled, { keyframes } from "styled-components";

const entrar = keyframes`
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
`;

const escurecer = keyframes`
  from { opacity: 0; }
  to { opacity: 1; }
`;

export const Fundo = styled.div`
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 90;
  display: flex;
  justify-content: flex-end;
  animation: ${escurecer} 160ms ease-out;

  @media (prefers-reduced-motion: reduce) {
    animation: none;
  }
`;

export const Caixa = styled.div`
  width: min(440px, 100vw);
  height: 100%;
  display: flex;
  flex-direction: column;
  background: ${({ theme }) => theme.colors.surface};
  border-left: 1px solid ${({ theme }) => theme.colors.border};
  box-shadow: -8px 0 24px rgba(0, 0, 0, 0.25);
  animation: ${entrar} 220ms cubic-bezier(0.2, 0.8, 0.2, 1);

  &:focus {
    outline: none;
  }

  @media (prefers-reduced-motion: reduce) {
    animation: none;
  }
`;

export const Topo = styled.div`
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: ${({ theme }) => theme.spacing(3)};
  padding: ${({ theme }) => theme.spacing(5)};
  border-bottom: 1px solid ${({ theme }) => theme.colors.border};
`;

export const Titulo = styled.h2`
  font-size: 17px;
  font-weight: 600;
  overflow-wrap: anywhere;
`;

export const Subtitulo = styled.div`
  font-size: 13px;
  color: ${({ theme }) => theme.colors.textMuted};
  margin-top: 2px;
`;

export const FecharBtn = styled.button`
  width: 36px;
  height: 36px;
  padding: 0;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 1px solid transparent;
  border-radius: ${({ theme }) => theme.radius.sm};
  color: ${({ theme }) => theme.colors.textMuted};

  &:hover {
    color: ${({ theme }) => theme.colors.text};
    border-color: ${({ theme }) => theme.colors.border};
  }
`;

export const Corpo = styled.div`
  flex: 1;
  overflow-y: auto;
  padding: ${({ theme }) => theme.spacing(5)};
`;

export const Rodape = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing(3)};
  padding: ${({ theme }) => theme.spacing(4)} ${({ theme }) => theme.spacing(5)};
  padding-bottom: calc(${({ theme }) => theme.spacing(4)} + env(safe-area-inset-bottom));
  border-top: 1px solid ${({ theme }) => theme.colors.border};
`;
