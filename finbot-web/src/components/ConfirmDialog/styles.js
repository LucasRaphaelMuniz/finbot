import styled from "styled-components";

export const Acoes = styled.div`
  display: flex;
  gap: ${({ theme }) => theme.spacing(2)};
  margin-top: ${({ theme }) => theme.spacing(4)};
  justify-content: flex-end;
`;

// Texto sobre o danger escolhido por tema: no escuro, branco sobre
// #f2545b dava 3,39:1 (texto escuro dá 5,6:1); no claro, branco sobre
// #d8383f já passa (4,6:1) e o escuro não.
export const BotaoPerigo = styled.button`
  background: ${({ theme }) => theme.colors.danger};
  border-color: ${({ theme }) => theme.colors.danger};
  color: ${({ theme }) => (theme.nome === "light" ? "#fff" : "#0f1115")};
  font-weight: 600;

  &:hover:not(:disabled) {
    border-color: ${({ theme }) => theme.colors.text};
  }
`;
