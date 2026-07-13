import styled from "styled-components";

export const Wrap = styled.div`
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: ${({ theme }) => theme.spacing(4)};
`;

export const Card = styled.div`
  width: 100%;
  max-width: 380px;
  background: ${({ theme }) => theme.colors.surface};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.lg};
  padding: ${({ theme }) => theme.spacing(8)};
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing(4)};
`;

export const Logo = styled.div`
  font-weight: 700;
  font-size: 20px;
  text-align: center;
  margin-bottom: ${({ theme }) => theme.spacing(2)};
`;

export const Field = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing(1)};

  label {
    font-size: 13px;
    color: ${({ theme }) => theme.colors.textMuted};
  }

  input {
    background: ${({ theme }) => theme.colors.surfaceAlt};
    border: 1px solid ${({ theme }) => theme.colors.border};
    border-radius: ${({ theme }) => theme.radius.sm};
    padding: ${({ theme }) => theme.spacing(2.5)} ${({ theme }) => theme.spacing(3)};

    &:focus {
      outline: none;
      border-color: ${({ theme }) => theme.colors.primary};
    }
  }
`;

export const Botao = styled.button`
  background: ${({ theme }) => theme.colors.primary};
  color: white;
  border: none;
  border-radius: ${({ theme }) => theme.radius.sm};
  padding: ${({ theme }) => theme.spacing(2.5)};
  font-weight: 600;
  cursor: pointer;

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  &:hover:not(:disabled) {
    opacity: 0.9;
  }
`;

export const Mensagem = styled.div`
  font-size: 13px;
  color: ${({ theme, $tipo }) =>
    $tipo === "erro" ? theme.colors.danger : theme.colors.success};
`;

export const LinkSecundario = styled.a`
  font-size: 13px;
  color: ${({ theme }) => theme.colors.primary};
  text-align: center;
  cursor: pointer;
`;
