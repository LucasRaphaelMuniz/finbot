import styled from "styled-components";

export const Overlay = styled.div`
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
`;

export const Box = styled.div`
  background: ${({ theme }) => theme.colors.surface};
  border: 1px solid ${({ theme }) => theme.colors.border};
  border-radius: ${({ theme }) => theme.radius.lg};
  padding: ${({ theme }) => theme.spacing(6)};
  // min-width:320px fixo brigava com max-width:90vw em telas bem estreitas
  // (abaixo de ~356px, 90vw < 320px — o conteúdo interno com seu próprio
  // min-width, ex: Form de lançamento, tinha que estourar um dos dois).
  // width: min(...) elimina o conflito: nunca passa de 480px, mas também
  // nunca passa de 90vw, sem impor um mínimo que a viewport não tenha
  // como cumprir. Modais mais largos (ex: futuro conteúdo maior) ainda
  // cabem porque isso é só a base — quem quiser mais largura sobrescreve
  // via minWidth inline, como já acontecia antes.
  width: min(480px, 90vw);
  max-height: 85vh;
  overflow-y: auto;
`;

export const Titulo = styled.h2`
  font-size: 16px;
  margin-bottom: ${({ theme }) => theme.spacing(4)};
`;
