import styled from "styled-components";

export const Box = styled.div`
  position: fixed;
  bottom: ${({ theme }) => theme.spacing(6)};
  right: ${({ theme }) => theme.spacing(6)};
  background: ${({ theme, $tipo }) =>
    $tipo === "erro" ? theme.colors.danger : theme.colors.success};
  color: white;
  padding: ${({ theme }) => theme.spacing(3)} ${({ theme }) => theme.spacing(4)};
  border-radius: ${({ theme }) => theme.radius.md};
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
  z-index: 1000;
`;
