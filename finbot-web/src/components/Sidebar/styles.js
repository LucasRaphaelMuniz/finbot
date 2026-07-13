import styled from "styled-components";

export const Nav = styled.nav`
  width: 220px;
  min-height: 100vh;
  background: ${({ theme }) => theme.colors.surface};
  border-right: 1px solid ${({ theme }) => theme.colors.border};
  padding: ${({ theme }) => theme.spacing(4)};
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing(1)};
`;

export const Logo = styled.div`
  font-weight: 700;
  font-size: 18px;
  margin-bottom: ${({ theme }) => theme.spacing(6)};
`;

export const ItemLink = styled.a`
  padding: ${({ theme }) => theme.spacing(2)} ${({ theme }) => theme.spacing(3)};
  border-radius: ${({ theme }) => theme.radius.sm};
  color: ${({ theme, $ativo }) => ($ativo ? theme.colors.text : theme.colors.textMuted)};
  background: ${({ theme, $ativo }) => ($ativo ? theme.colors.surfaceAlt : "transparent")};
  font-size: 14px;

  &:hover {
    background: ${({ theme }) => theme.colors.surfaceAlt};
    color: ${({ theme }) => theme.colors.text};
  }
`;
