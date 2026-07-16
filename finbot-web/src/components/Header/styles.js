import styled from "styled-components";

export const Bar = styled.header`
  height: 56px;
  border-bottom: 1px solid ${({ theme }) => theme.colors.border};
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: ${({ theme }) => theme.spacing(4)};
  padding: 0 ${({ theme }) => theme.spacing(6)};

  @media (max-width: 860px) {
    padding: 0 ${({ theme }) => theme.spacing(3)};
  }
`;

// Agrupa e-mail + Sair pra funcionar com justify-content: space-between
// (o MenuBtn ocupa a ponta esquerda só no mobile — no desktop ele nem
// renderiza, então esse grupo continua efetivamente colado à direita).
export const Direita = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing(4)};

  span {
    @media (max-width: 480px) {
      /* e-mail comprido não cabe ao lado do botão Sair numa tela pequena */
      display: none;
    }
  }
`;

export const MenuBtn = styled.button`
  display: none;
  background: transparent;
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.sm};
  padding: ${({ theme }) => theme.spacing(1.5)} ${({ theme }) => theme.spacing(2.5)};
  font-size: 18px;
  line-height: 1;
  cursor: pointer;

  @media (max-width: 860px) {
    display: inline-flex;
    align-items: center;
  }
`;

export const SairBtn = styled.button`
  background: transparent;
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.sm};
  padding: ${({ theme }) => theme.spacing(1.5)} ${({ theme }) => theme.spacing(3)};
  cursor: pointer;

  &:hover {
    background: ${({ theme }) => theme.colors.surfaceAlt};
  }
`;
