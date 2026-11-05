import styled from "styled-components";

export const Bar = styled.header`
  height: 60px;
  border-bottom: 1px solid ${({ theme }) => theme.colors.border};
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: ${({ theme }) => theme.spacing(4)};
  padding: 0 ${({ theme }) => theme.spacing(6)};

  @media (max-width: 860px) {
    height: 52px;
    padding: 0 ${({ theme }) => theme.spacing(4)};
  }
`;

// A marca só aparece no celular: no desktop ela já está no topo da Sidebar.
export const Marca = styled.span`
  font-weight: 700;
  font-size: 17px;
  visibility: hidden;

  @media (max-width: 860px) {
    visibility: visible;
  }
`;

export const Direita = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing(3)};
  min-width: 0;
`;

export const Email = styled.span`
  font-size: 13px;
  color: ${({ theme }) => theme.colors.textMuted};
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;

  @media (max-width: 860px) {
    display: none;
  }
`;

export const NovoBtn = styled.button`
  display: inline-flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing(1.5)};
  min-height: 38px;
  padding: 0 ${({ theme }) => theme.spacing(4)};
  border: none;
  border-radius: ${({ theme }) => theme.radius.sm};
  background: ${({ theme }) => theme.colors.primarySolid};
  color: #fff;
  font: inherit;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;

  &:hover {
    filter: brightness(1.08);
  }

  /* no celular o "+" mora na BottomNav */
  @media (max-width: 860px) {
    display: none;
  }
`;

export const SairBtn = styled.button`
  display: inline-flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing(1.5)};
  min-height: 38px;
  background: transparent;
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.sm};
  padding: 0 ${({ theme }) => theme.spacing(3)};
  color: ${({ theme }) => theme.colors.text};
  font: inherit;
  font-size: 14px;
  cursor: pointer;

  &:hover {
    background: ${({ theme }) => theme.colors.surfaceAlt};
  }

  @media (max-width: 860px) {
    min-height: 44px;
  }
`;
