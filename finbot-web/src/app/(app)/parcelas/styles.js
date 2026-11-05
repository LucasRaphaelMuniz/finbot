import styled, { keyframes } from "styled-components";

// Parcelas futuras (redesign de 05/11/2026, fase 3).

export const Header = styled.div`
  margin-bottom: ${({ theme }) => theme.spacing(5)};
`;

export const Titulo = styled.h1`
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.01em;
`;

export const Subtitulo = styled.p`
  font-size: 13px;
  color: ${({ theme }) => theme.colors.textMuted};
  margin-top: 4px;
`;

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
  }
`;

const superficie = ({ theme }) => `
  background: ${theme.colors.surface};
  border: 1px solid ${theme.colors.border};
  border-radius: ${theme.radius.lg};
`;

// ---- linha do tempo -----------------------------------------------------------

export const Bloco = styled.section`
  ${superficie}
  padding: ${({ theme }) => theme.spacing(5)};
  margin-bottom: ${({ theme }) => theme.spacing(4)};

  @media (max-width: 640px) {
    padding: ${({ theme }) => theme.spacing(4)};
  }
`;

export const BlocoTitulo = styled.h2`
  font-size: 16px;
  font-weight: 600;
  margin-bottom: ${({ theme }) => theme.spacing(4)};
`;

// Colunas de mês lado a lado; no celular rola na horizontal dentro do bloco.
export const LinhaMeses = styled.div`
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: minmax(72px, 1fr);
  gap: ${({ theme }) => theme.spacing(2)};
  overflow-x: auto;
  padding-bottom: 4px;
`;

export const Mes = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  min-width: 0;
`;

export const MesValor = styled.span`
  font-size: 11px;
  color: ${({ theme }) => theme.colors.textMuted};
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
`;

export const MesBarra = styled.div`
  width: 100%;
  max-width: 40px;
  height: 96px;
  display: flex;
  align-items: flex-end;
  border-radius: 6px;
  background: ${({ theme }) => theme.colors.surfaceAlt};
  overflow: hidden;
`;

export const MesBarraCheia = styled.div`
  width: 100%;
  border-radius: 6px 6px 0 0;
  background: ${({ theme }) => theme.colors.primary};
`;

export const MesNome = styled.span`
  font-size: 12px;
  font-weight: 600;
`;

export const MesFim = styled.span`
  font-size: 11px;
  font-weight: 600;
  padding: 0 6px;
  border-radius: 999px;
  color: ${({ theme }) => theme.colors.success};
  border: 1px solid ${({ theme }) => theme.colors.success};
`;

// ---- lista ------------------------------------------------------------------------

export const Lista = styled.div`
  ${superficie}
  overflow: clip;

  ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }
`;

export const Item = styled.li`
  padding: ${({ theme }) => theme.spacing(4)};

  & + & {
    border-top: 1px solid ${({ theme }) => theme.colors.border};
  }
`;

export const ItemTopo = styled.div`
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: ${({ theme }) => theme.spacing(3)};
`;

export const ItemTitulo = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  font-size: 14px;
  font-weight: 500;
  overflow-wrap: anywhere;
`;

export const ItemValor = styled.span`
  font-size: 15px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
`;

export const Progresso = styled.div`
  height: 6px;
  margin: ${({ theme }) => theme.spacing(2)} 0;
  border-radius: 999px;
  background: ${({ theme }) => theme.colors.surfaceAlt};
  overflow: hidden;
`;

export const ProgressoCheio = styled.div`
  height: 100%;
  border-radius: 999px;
  background: ${({ theme }) => theme.colors.primary};
`;

export const ItemMeta = styled.div`
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 2px ${({ theme }) => theme.spacing(3)};
  font-size: 12px;
  color: ${({ theme }) => theme.colors.textMuted};
  font-variant-numeric: tabular-nums;

  strong {
    color: ${({ theme }) => theme.colors.text};
  }
`;

export const Selo = styled.span`
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 500;
  padding: 1px 6px;
  border-radius: 999px;
  border: 1px solid ${({ theme }) => theme.colors.border};
  color: ${({ theme }) => theme.colors.textMuted};
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
