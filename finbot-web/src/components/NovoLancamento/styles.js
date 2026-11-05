import styled from "styled-components";

export const Form = styled.form`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing(4)};
  width: 100%;
`;

export const ToggleTipo = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: ${({ theme }) => theme.spacing(1)};
  padding: 4px;
  background: ${({ theme }) => theme.colors.surfaceAlt};
  border-radius: ${({ theme }) => theme.radius.sm};
`;

// Gasto ativo pinta de vermelho, entrada de verde — a cor confirma o tipo
// antes de salvar (erro comum: lançar salário como gasto).
export const ToggleBtn = styled.button`
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: ${({ theme }) => theme.spacing(1.5)};
  min-height: 40px;
  border: none;
  border-radius: ${({ theme }) => theme.radius.sm};
  font: inherit;
  font-weight: 500;
  cursor: pointer;
  background: ${({ theme, $ativo }) => ($ativo ? theme.colors.surface : "transparent")};
  color: ${({ theme, $ativo, $tom }) =>
    !$ativo ? theme.colors.textMuted : $tom === "gasto" ? theme.colors.danger : theme.colors.success};
  box-shadow: ${({ $ativo }) => ($ativo ? "0 1px 2px rgba(0,0,0,0.15)" : "none")};
`;

export const Erro = styled.div`
  color: ${({ theme }) => theme.colors.danger};
  font-size: 13px;
`;

export const SalvarBtn = styled.button`
  background: ${({ theme }) => theme.colors.primarySolid};
  color: white;
  border: none;
  border-radius: ${({ theme }) => theme.radius.sm};
  min-height: 44px;
  font: inherit;
  font-weight: 600;
  cursor: pointer;

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
`;
