import styled, { keyframes } from "styled-components";

// Despesas fixas (redesign de 05/11/2026, fase 3) — mesma linguagem de
// Lançamentos: lista em `surface`, linha inteira clicável abrindo o painel.

export const Header = styled.div`
  display: flex;
  align-items: flex-start;
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

export const Subtitulo = styled.p`
  font-size: 13px;
  color: ${({ theme }) => theme.colors.textMuted};
  margin-top: 4px;
`;

export const NovoBtn = styled.button`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 40px;
  padding: 0 ${({ theme }) => theme.spacing(4)};
  background: ${({ theme }) => theme.colors.primarySolid};
  color: white;
  border: none;
  border-radius: ${({ theme }) => theme.radius.md};
  font-weight: 600;
  font-size: 14px;
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

export const Lista = styled.div`
  background: ${({ theme }) => theme.colors.surface};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.lg};
  overflow: clip;

  ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }
`;

export const Linha = styled.li`
  & + & {
    border-top: 1px solid ${({ theme }) => theme.colors.border};
  }
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

// "Folhinha" de calendário com o dia do mês — a coluna que ordena a lista.
export const DiaBadge = styled.span`
  width: 44px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 4px 0;
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.sm};
  line-height: 1.1;

  small {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: ${({ theme }) => theme.colors.textMuted};
  }

  span {
    font-size: 17px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
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

  @media (max-width: 480px) {
    display: none;
  }
`;

export const LinhaTexto = styled.div`
  flex: 1;
  min-width: 0;
`;

export const LinhaTitulo = styled.div`
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

export const Progresso = styled.div`
  height: 4px;
  max-width: 220px;
  margin-top: 6px;
  border-radius: 999px;
  background: ${({ theme }) => theme.colors.surfaceAlt};
  overflow: hidden;
`;

export const ProgressoCheio = styled.div`
  height: 100%;
  border-radius: 999px;
  background: ${({ theme }) => theme.colors.primary};
`;

export const Valor = styled.span`
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  font-size: 14px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
`;

export const ValorNovo = styled.small`
  font-size: 11px;
  font-weight: 400;
  color: ${({ theme }) => theme.colors.warning};
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

// ---- painel ------------------------------------------------------------------

export const Form = styled.form`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing(4)};
  width: 100%;
`;

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
`;

export const RemoverBtn = styled.button`
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
