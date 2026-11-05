import styled from "styled-components";

export const Select = styled.select`
  background: ${({ theme }) => theme.colors.surfaceAlt};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.sm};
  padding: ${({ theme }) => theme.spacing(2.5)} ${({ theme }) => theme.spacing(3)};
  width: 100%;

  &:focus {
    outline: none;
    border-color: ${({ theme }) => theme.colors.primary};
    /* anel de foco: só a borda de 1px mudando de cor era sutil demais */
    box-shadow: 0 0 0 3px ${({ theme }) => theme.colors.primary}59;
  }
`;
