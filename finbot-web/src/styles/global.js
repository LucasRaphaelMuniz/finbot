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

  /* checkbox/radio "crus" (sem styled-component próprio, ex: os das telas
     Categorias, Formas, Despesas fixas) caem no controle nativo do SO —
     em dark mode isso normalmente já é claro o bastante pra ver, mas fica
     cinza genérico, sem nenhuma relação com a cor do tema. accent-color é
     suportado nos browsers relevantes (Chrome/Edge/Firefox atuais) e
     recolore o controle nativo sem precisar reconstruir checkbox do zero
     com markup/CSS customizado — muito menos código pra um ajuste visual
     pontual. */
  input[type="checkbox"], input[type="radio"] {
    accent-color: ${({ theme }) => theme.colors.primary};
    width: 16px;
    height: 16px;
    cursor: pointer;
  }

  /* Estilo padrão pra <button> "cru" (sem componente estilizado próprio).
     Antes só herdava a cor do texto do tema (quase branca) sem nunca
     definir um background — caía no cinza claro padrão do navegador,
     resultando em texto claro sobre fundo claro (ilegível). Botões que já
     usam um styled-component (ex: SalvarBtn, AcaoBtn) continuam com a
     aparência própria deles — uma classe do styled-components tem mais
     especificidade que este seletor de elemento puro "button", então essa
     regra só entra em ação onde nada mais foi definido. */
  button {
    background: ${({ theme }) => theme.colors.surfaceAlt};
    border: 1px solid ${({ theme }) => theme.colors.border};
    border-radius: ${({ theme }) => theme.radius.sm};
    padding: ${({ theme }) => theme.spacing(2)} ${({ theme }) => theme.spacing(3.5)};
    cursor: pointer;

    &:hover:not(:disabled) {
      border-color: ${({ theme }) => theme.colors.primary};
    }

    &:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
  }
`;

export default GlobalStyle;
