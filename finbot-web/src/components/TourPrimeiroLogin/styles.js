import styled from "styled-components";

export const Passo = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing(2)};
  min-width: 280px;
  max-width: 360px;

  strong {
    font-size: 16px;
  }

  p {
    font-size: 14px;
    opacity: 0.8;
    line-height: 1.5;
  }

  a {
    color: ${({ theme }) => theme.colors.primary};
    font-size: 14px;
    font-weight: 600;
  }
`;

export const Botoes = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: ${({ theme }) => theme.spacing(4)};

  button {
    cursor: pointer;
  }

  button:first-child {
    opacity: 0.6;
    background: transparent;
    border: none;
  }
`;
