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

// Botão de WhatsApp: usa theme.colors.success (verde já existente na
// paleta) em vez do verde de marca do WhatsApp (#25D366) — mantém o botão
// dentro do design system em vez de introduzir uma cor nova só pra isso.
export const WhatsBotao = styled.a`
  display: inline-flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing(2)};
  background: ${({ theme }) => theme.colors.success};
  color: #0f1115;
  font-weight: 600;
  font-size: 14px;
  border-radius: ${({ theme }) => theme.radius.sm};
  padding: ${({ theme }) => theme.spacing(2.5)} ${({ theme }) => theme.spacing(4)};
  width: fit-content;

  &:hover {
    opacity: 0.9;
  }
`;

export const NumeroBot = styled.span`
  font-size: 13px;
  color: ${({ theme }) => theme.colors.textMuted};
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
