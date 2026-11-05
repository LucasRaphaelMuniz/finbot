import styled from "styled-components";

export const Card = styled.div`
  background: ${({ theme }) => theme.colors.surface};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.lg};
  padding: ${({ theme }) => theme.spacing(5)};
  margin-bottom: ${({ theme }) => theme.spacing(5)};
`;

export const LinhaDuplicata = styled.tr`
  background: ${({ theme, $duplicata }) => ($duplicata ? "rgba(242, 84, 91, 0.08)" : "transparent")};
`;

export const AvisoDuplicata = styled.span`
  color: ${({ theme }) => theme.colors.warning};
  font-size: 12px;
  margin-left: 8px;
`;

export const Campo = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing(1)};

  > label {
    font-size: 13px;
    color: ${({ theme }) => theme.colors.textMuted};
  }
`;

// Input de arquivo nativo, mas com o botão no tema (antes: chip branco do
// SO destoando do tema escuro) e max-width pra o nome do arquivo não
// vazar do card no celular.
export const InputArquivo = styled.input`
  max-width: 100%;
  font-size: 14px;
  color: ${({ theme }) => theme.colors.textMuted};

  &::file-selector-button {
    margin-right: ${({ theme }) => theme.spacing(3)};
    padding: ${({ theme }) => theme.spacing(2)} ${({ theme }) => theme.spacing(3)};
    background: ${({ theme }) => theme.colors.surfaceAlt};
    color: ${({ theme }) => theme.colors.text};
    border: 1px solid ${({ theme }) => theme.colors.border};
    border-radius: ${({ theme }) => theme.radius.sm};
    font: inherit;
    cursor: pointer;
  }

  &:hover::file-selector-button {
    border-color: ${({ theme }) => theme.colors.primary};
  }
`;

export const ErroCampo = styled.p`
  font-size: 13px;
  color: ${({ theme }) => theme.colors.danger};
`;
