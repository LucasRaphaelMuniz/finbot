import styled from "styled-components";

export const Table = styled.table`
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
`;

export const Th = styled.th`
  text-align: left;
  padding: ${({ theme }) => theme.spacing(2)} ${({ theme }) => theme.spacing(3)};
  color: ${({ theme }) => theme.colors.textMuted};
  border-bottom: 1px solid ${({ theme }) => theme.colors.border};
  font-weight: 500;
`;

export const Td = styled.td`
  padding: ${({ theme }) => theme.spacing(2)} ${({ theme }) => theme.spacing(3)};
  border-bottom: 1px solid ${({ theme }) => theme.colors.border};
`;

export const Tr = styled.tr`
  &:hover {
    background: ${({ theme }) => theme.colors.surfaceAlt};
  }
`;

export const AcoesTd = styled(Td)`
  display: flex;
  gap: ${({ theme }) => theme.spacing(2)};
  justify-content: flex-end;
`;

export const AcaoBtn = styled.button`
  background: transparent;
  border: none;
  color: ${({ theme, $perigo }) => ($perigo ? theme.colors.danger : theme.colors.primary)};
  cursor: pointer;
  font-size: 13px;

  &:hover {
    text-decoration: underline;
  }
`;
