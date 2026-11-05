import styled, { css, keyframes } from "styled-components";

// Estilos de Lançamentos (redesign de 05/11/2026, fase 2) — mesma
// linguagem visual do Início: blocos em `surface` sobre `bg`, linhas com
// avatar de categoria, cabeçalho de dia com o saldo.

const tom = ({ theme }) => css`
  &[data-tom="entrada"] { color: ${theme.colors.success}; }
  &[data-tom="muted"] { color: ${theme.colors.textMuted}; }
`;

export const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: ${({ theme }) => theme.spacing(3)};
  margin-bottom: ${({ theme }) => theme.spacing(5)};
`;

export const Titulo = styled.h1`
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.01em;
`;

// ---- busca + filtros --------------------------------------------------------

export const Barra = styled.div`
  display: flex;
  gap: ${({ theme }) => theme.spacing(2)};
  margin-bottom: ${({ theme }) => theme.spacing(3)};
`;

export const Busca = styled.div`
  position: relative;
  flex: 1;
  min-width: 0;

  svg {
    position: absolute;
    left: 12px;
    top: 50%;
    transform: translateY(-50%);
    color: ${({ theme }) => theme.colors.textMuted};
    pointer-events: none;
  }

  input {
    width: 100%;
    height: 40px;
    padding: 0 ${({ theme }) => theme.spacing(3)} 0 36px;
    background: ${({ theme }) => theme.colors.surface};
    border: 1px solid ${({ theme }) => theme.colors.border};
    border-radius: ${({ theme }) => theme.radius.md};
    color: ${({ theme }) => theme.colors.text};
    font-size: 14px;
  }

  input:focus {
    outline: 2px solid ${({ theme }) => theme.colors.primary};
    outline-offset: -1px;
  }
`;

export const MaisFiltrosBtn = styled.button`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 40px;
  padding: 0 ${({ theme }) => theme.spacing(3)};
  background: ${({ theme }) => theme.colors.surface};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.md};
  color: ${({ theme }) => theme.colors.text};
  font-size: 14px;
  white-space: nowrap;

  &[aria-expanded="true"] {
    border-color: ${({ theme }) => theme.colors.primary};
  }

  /* no celular fica só o ícone (+ contador) pra caber ao lado da busca */
  @media (max-width: 480px) {
    font-size: 0;
    gap: 4px;
  }
`;

export const Contador = styled.span`
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: ${({ theme }) => theme.colors.primarySolid};
  color: white;
  font-size: 11px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
`;

export const ChipsLinha = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: ${({ theme }) => theme.spacing(2)} ${({ theme }) => theme.spacing(4)};
  margin-bottom: ${({ theme }) => theme.spacing(4)};

  /* celular: cada grupo rola na horizontal em vez de quebrar em 3 linhas.
     nowrap obrigatório: coluna com wrap dimensiona a linha pelo conteúdo
     e os chips empurravam a página pra 409px. */
  @media (max-width: 640px) {
    flex-direction: column;
    flex-wrap: nowrap;
  }
`;

export const Chips = styled.div`
  display: flex;
  gap: ${({ theme }) => theme.spacing(2)};

  @media (max-width: 640px) {
    overflow-x: auto;
    scrollbar-width: none;
    margin: 0 -${({ theme }) => theme.spacing(4)};
    padding: 0 ${({ theme }) => theme.spacing(4)};

    &::-webkit-scrollbar {
      display: none;
    }
  }
`;

export const Chip = styled.button`
  flex-shrink: 0;
  min-height: 34px;
  padding: 0 ${({ theme }) => theme.spacing(3)};
  border-radius: 999px;
  border: 1px solid ${({ theme }) => theme.colors.border};
  background: transparent;
  color: ${({ theme }) => theme.colors.textMuted};
  font-size: 13px;
  font-weight: 500;

  &:hover {
    color: ${({ theme }) => theme.colors.text};
  }

  &[aria-pressed="true"] {
    background: ${({ theme }) => theme.colors.primarySolid};
    border-color: ${({ theme }) => theme.colors.primarySolid};
    color: white;
  }
`;

export const Filtros = styled.div`
  display: flex;
  align-items: flex-end;
  gap: ${({ theme }) => theme.spacing(3)};
  flex-wrap: wrap;
  padding: ${({ theme }) => theme.spacing(4)};
  margin-bottom: ${({ theme }) => theme.spacing(4)};
  background: ${({ theme }) => theme.colors.surface};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.lg};

  small {
    flex-basis: 100%;
    font-size: 12px;
    color: ${({ theme }) => theme.colors.textMuted};
  }
`;

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

export const LimparBtn = styled.button`
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: ${({ theme }) => theme.spacing(2)};
  background: transparent;
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: 999px;
  padding: 6px 12px;
  color: ${({ theme }) => theme.colors.text};
  font-size: 13px;
`;

// ---- totais -------------------------------------------------------------------

export const Resumo = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: ${({ theme }) => theme.spacing(2)} ${({ theme }) => theme.spacing(6)};
  margin-bottom: ${({ theme }) => theme.spacing(4)};
`;

export const ResumoItem = styled.div`
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 13px;

  span {
    color: ${({ theme }) => theme.colors.textMuted};
  }

  strong {
    font-size: 15px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    ${tom}
  }
`;

// ---- lista agrupada por dia -----------------------------------------------------

export const Lista = styled.div`
  background: ${({ theme }) => theme.colors.surface};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.lg};
  /* clip (não hidden): hidden vira contêiner de rolagem e mata o sticky
     do cabeçalho de dia */
  overflow: clip;
`;

export const Dia = styled.section`
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  & + & {
    border-top: 1px solid ${({ theme }) => theme.colors.border};
  }
`;

export const DiaTopo = styled.div`
  position: sticky;
  top: 0;
  z-index: 1;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: ${({ theme }) => theme.spacing(2)} ${({ theme }) => theme.spacing(4)};
  background: ${({ theme }) => theme.colors.surfaceAlt};
  font-size: 12px;
  font-weight: 600;
  color: ${({ theme }) => theme.colors.textMuted};
  font-variant-numeric: tabular-nums;

  h2 {
    font-size: inherit;
    font-weight: inherit;
  }

  span {
    ${tom}
  }
`;

export const Linha = styled.li`
  & + & {
    border-top: 1px solid ${({ theme }) => theme.colors.border};
  }

  .conteudo {
    display: flex;
    align-items: center;
    gap: ${({ theme }) => theme.spacing(3)};
    padding: ${({ theme }) => theme.spacing(3)} ${({ theme }) => theme.spacing(4)};
  }

  ${({ $atenuada }) => $atenuada && css`opacity: 0.6;`}
`;

export const LinhaBtn = styled.button`
  width: 100%;
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing(3)};
  padding: ${({ theme }) => theme.spacing(3)} ${({ theme }) => theme.spacing(4)};
  background: transparent;
  border: none;
  border-radius: 0;
  color: inherit;
  text-align: left;
  font: inherit;
  cursor: pointer;

  &:hover {
    background: ${({ theme }) => theme.colors.surfaceAlt};
  }

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.primary};
    outline-offset: -2px;
  }
`;

export const Avatar = styled.span`
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
`;

export const LinhaTexto = styled.div`
  flex: 1;
  min-width: 0;
`;

export const LinhaTitulo = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
`;

export const LinhaMeta = styled.div`
  font-size: 12px;
  color: ${({ theme }) => theme.colors.textMuted};
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-top: 2px;
`;

export const Selo = styled.span`
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 500;
  padding: 1px 6px;
  border-radius: 999px;
  border: 1px dashed ${({ theme }) => theme.colors.textMuted};
  color: ${({ theme }) => theme.colors.textMuted};
`;

export const Valor = styled.span`
  font-size: 14px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  ${tom}
`;

export const Vazio = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  text-align: center;
  padding: ${({ theme }) => theme.spacing(10)} ${({ theme }) => theme.spacing(4)};
  font-size: 14px;

  span {
    color: ${({ theme }) => theme.colors.textMuted};
  }
`;

const pulsar = keyframes`
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
`;

export const SkeletonLinha = styled.div`
  height: 14px;
  margin: 22px ${({ theme }) => theme.spacing(4)};
  border-radius: 6px;
  background: ${({ theme }) => theme.colors.surfaceAlt};
  animation: ${pulsar} 1.4s ease-in-out infinite;

  @media (prefers-reduced-motion: reduce) {
    animation: none;
  }
`;

// ---- painel de edição -----------------------------------------------------------

export const PainelValor = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing(3)};

  strong {
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -0.02em;
    font-variant-numeric: tabular-nums;
    ${tom}
  }
`;

export const PainelInfo = styled.p`
  font-size: 13px;
  color: ${({ theme }) => theme.colors.textMuted};
  margin-top: ${({ theme }) => theme.spacing(2)};
`;

export const Form = styled.form`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing(4)};
  width: 100%;
  margin-top: ${({ theme }) => theme.spacing(5)};
`;

// Field vem de @/components/AuthCard/styles (estiliza label + input).

export const Erro = styled.div`
  color: ${({ theme }) => theme.colors.danger};
  font-size: 13px;
`;

export const SalvarBtn = styled.button`
  flex: 1;
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

export const ExcluirBtn = styled.button`
  background: transparent;
  color: ${({ theme }) => theme.colors.danger};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.sm};
  padding: ${({ theme }) => theme.spacing(2.5)} ${({ theme }) => theme.spacing(4)};
  font-weight: 500;

  &:hover {
    border-color: ${({ theme }) => theme.colors.danger};
  }
`;
