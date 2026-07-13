import styled from "styled-components";

export const Card = styled.div`
  background: ${({ theme }) => theme.colors.surface};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.lg};
  padding: ${({ theme }) => theme.spacing(5)};
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing(1)};
`;

export const Label = styled.span`
  font-size: 13px;
  color: ${({ theme }) => theme.colors.textMuted};
`;

export const Valor = styled.span`
  font-size: 24px;
  font-weight: 700;
  color: ${({ theme, $tom }) =>
    $tom === "erro" ? theme.colors.danger :
    $tom === "sucesso" ? theme.colors.success :
    theme.colors.text};
`;
