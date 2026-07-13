// styles/global.js — reset + estilos globais via styled-components
// createGlobalStyle. Importado 1x no layout raiz (app/layout.jsx).
import { createGlobalStyle } from "styled-components";

const GlobalStyle = createGlobalStyle`
  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  html, body {
    background: ${({ theme }) => theme.colors.bg};
    color: ${({ theme }) => theme.colors.text};
    font-family: ${({ theme }) => theme.font.family};
    font-size: 15px;
    line-height: 1.5;
  }

  a {
    color: inherit;
    text-decoration: none;
  }

  button, input, select {
    font-family: inherit;
    font-size: inherit;
    color: inherit;
  }

  /* Estilo padrão pra <button