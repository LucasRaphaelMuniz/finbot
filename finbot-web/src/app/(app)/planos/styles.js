import styled from "styled-components";

export const Grid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: ${({ theme }) => theme.spacing(4)};
`;

export const Card = styled.div`
  background: ${({ theme }) => theme.colors.surface};
  border: 2px solid ${({ theme, $atual }) => ($atual ? theme.colors.primary : theme.colors.border)};
  border-radius: ${({ theme }) => theme.radius.lg};
  padding: ${({ theme }) => theme.spacing(5)};
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing(3)};
  position: relative;
`;

export const Selo = styled.span`
  position: absolute;
  top: -10px;
  right: 16px;
  background: ${({ theme }) => theme.colors.primary};
  color: white;
  font-size: 11px;
  padding: 2px 10px;
  border-radius: 999px;
  font-weight: 600;
`;

export const Nome = styled.h3`
  font-size: 18px;
  text-transform: capitalize;
`;

export const Preco = styled.div`
  font-size: 22px;
  font-weight: 700;
  color: ${({ theme }) => theme.colors.textMuted};
`;

export const Membros = styled.p`
  font-size: 13px;
  color: ${({ theme }) => theme.colors.textMuted};
`;

export const BotaoContratar = styled.button`
  margin-top: auto;
  background: transparent;
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.sm};
  padding: ${({ theme }) => theme.spacing(2.5)};
  color: ${({ theme }) => theme.colors.textMuted};
  cursor: not-allowed;
`;
