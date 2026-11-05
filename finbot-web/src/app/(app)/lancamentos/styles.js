import styled from "styled-components";

export const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: ${({ theme }) => theme.spacing(3)};
  margin-bottom: ${({ theme }) => theme.spacing(5)};
`;

export const Abas = styled.div`
  display: inline-flex;
  margin-bottom: ${({ theme }) => theme.spacing(4)};
  gap: ${({ theme }) => theme.spacing(1)};
  background: ${({ theme }) => theme.colors.surfaceAlt};
  border-radius: ${({ theme }) => theme.radius.sm};
  padding: 4px;
`;

export const Aba = styled.button`
  background: ${({ theme, $ativa }) => ($ativa ? theme.colors.primarySolid : "transparent")};
  color: ${({ theme, $ativa }) => ($ativa ? "white" : theme.colors.textMuted)};
  border: none;
  border-radius: ${({ theme }) => theme.radius.sm};
  padding: ${({ theme }) => theme.spacing(2)} ${({ theme }) => theme.spacing(4)};
  cursor: pointer;
  font-weight: 500;
`;

export const Filtros = styled.div`
  display: flex;
  align-items: flex-end;
  gap: ${({ theme }) => theme.spacing(3)};
  flex-wrap: wrap;
  margin-bottom: ${({ theme }) => theme.spacing(4)};
`;

// Label + select de um filtro. flex-basis 200px / máx 280px: no desktop
// cabem lado a lado; abaixo de ~440px cada um ocupa a linha inteira.
export const FiltroCampo = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing(1)};
  flex: 1 1 200px;
  max-width: 280px;

  label {
    font-size: 13px;
    color: ${({ theme }) => theme.colors.textMuted};
  }

  @media (max-width: 480px) {
    max-width: none;
  }
`;

export const BotaoNovo = styled.button`
  background: ${({ theme }) => theme.colors.primarySolid};
  color: white;
  border: none;
  border-radius: ${({ theme }) => theme.radius.sm};
  padding: ${({ theme }) => theme.spacing(2.5)} ${({ theme }) => theme.spacing(4)};
  font-weight: 600;
  cursor: pointer;

  &:hover {
    opacity: 0.9;
  }
`;

export const Form = styled.form`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing(4)};
  // width (não min-width): preenche o Box do Modal em vez de impor um piso
  // de 320px que podia estourar a largura do Box em telas bem estreitas
  // (ver components/Modal/styles.js).
  width: 100%;
`;

// Field saiu daqui — essa versão só estilizava o <label>, não o <input>
// (diferente de components/AuthCard/styles.js, que também estiliza input),
// e era a causa do campo Descrição aparecer sem estilo (fundo branco
// padrão do browser) no modal de lançamento. page.jsx agora importa Field
// de @/components/AuthCard/styles, igual formas/categorias/fixas já faziam.

export const ToggleTipo = styled.div`
  display: flex;
  gap: ${({ theme }) => theme.spacing(2)};
`;

export const ToggleBtn = styled.button`
  flex: 1;
  padding: ${({ theme }) => theme.spacing(2)};
  border-radius: ${({ theme }) => theme.radius.sm};
  border: 1px solid ${({ theme, $ativo }) => ($ativo ? theme.colors.primary : theme.colors.border)};
  background: ${({ theme, $ativo }) => ($ativo ? theme.colors.surfaceAlt : "transparent")};
  cursor: pointer;
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
  padding: ${({ theme }) => theme.spacing(2.5)};
  font-weight: 600;
  cursor: pointer;

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
`;
