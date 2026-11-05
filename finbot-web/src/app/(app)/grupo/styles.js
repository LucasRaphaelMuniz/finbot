import styled from "styled-components";

export const Secao = styled.section`
  background: ${({ theme }) => theme.colors.surface};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.lg};
  padding: ${({ theme }) => theme.spacing(5)};
  margin-bottom: ${({ theme }) => theme.spacing(5)};
`;

export const SecaoHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: ${({ theme }) => theme.spacing(4)};
`;

export const Titulo = styled.h2`
  font-size: 16px;
`;

// flex-wrap: no celular o botão desce pra linha de baixo em vez de vazar
// pela borda do card (era o que acontecia com "Salvar" em 375px).
export const NomeGrupoForm = styled.form`
  display: flex;
  flex-wrap: wrap;
  gap: ${({ theme }) => theme.spacing(2)};
  align-items: center;
`;

export const CampoTelefone = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing(1)};
  margin-bottom: ${({ theme }) => theme.spacing(5)};

  > label {
    font-size: 13px;
    color: ${({ theme }) => theme.colors.textMuted};
  }
`;

export const ErroCampo = styled.p`
  font-size: 13px;
  color: ${({ theme }) => theme.colors.danger};
`;

export const InputInline = styled.input`
  flex: 1 1 200px;
  min-width: 0;
  background: ${({ theme }) => theme.colors.surfaceAlt};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.sm};
  padding: ${({ theme }) => theme.spacing(2)} ${({ theme }) => theme.spacing(3)};
`;

export const Botao = styled.button`
  background: ${({ theme }) => theme.colors.primarySolid};
  color: white;
  border: none;
  border-radius: ${({ theme }) => theme.radius.sm};
  padding: ${({ theme }) => theme.spacing(2)} ${({ theme }) => theme.spacing(4)};
  cursor: pointer;
  font-weight: 600;
  white-space: nowrap;

  &:hover:not(:disabled) {
    opacity: 0.9;
  }
`;

export const CodigoBox = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing(3)};
  background: ${({ theme }) => theme.colors.surfaceAlt};
  border-radius: ${({ theme }) => theme.radius.sm};
  padding: ${({ theme }) => theme.spacing(3)};
  font-family: monospace;
`;
