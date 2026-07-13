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
