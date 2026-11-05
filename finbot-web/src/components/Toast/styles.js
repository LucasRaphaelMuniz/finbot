import styled from "styled-components";

export const Box = styled.div`
  position: fixed;
  bottom: ${({ theme }) => theme.spacing(6)};
  right: ${({ theme }) => theme.spacing(6)};
  background: ${({ theme, $tipo }) =>
    $tipo === "erro" ? theme.colors.danger : theme.colors.success};
  /* Branco sobre success/danger ficava entre 2,1:1 e 3,4:1 — texto escuro
     fixo passa de 4:1 nos dois temas. */
  color: ${({ theme, $tipo }) => ($tipo === "erro" && theme.nome === "light" ? "#fff" : "#0f1115")};
  font-weight: 500;
  padding: ${({ theme }) => theme.spacing(3)} ${({ theme }) => theme.spacing(4)};
  border-radius: ${({ theme }) => theme.radius.md};
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
  z-index: 1000;
`;

// Wrapper sempre presente da região aria-live — não ocupa espaço nem
// intercepta clique; o Box (fixed) continua se posicionando sozinho.
export const Regiao = styled.div`
  position: fixed;
  bottom: 0;
  right: 0;
  width: 0;
  height: 0;
  z-index: 1000;
`;
