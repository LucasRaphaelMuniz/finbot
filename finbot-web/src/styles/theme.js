// styles/theme.js — tokens de design compartilhados entre componentes
// styled-components. Cores neutras + 1 cor de destaque; ajustar depois da
// síntese visual da Fase 0 (docs/benchmarking.md) quando as telas da Fase 5
// forem desenhadas de verdade.
const theme = {
  colors: {
    bg: "#0f1115",
    surface: "#171a21",
    surfaceAlt: "#1f232c",
    border: "#2a2f3a",
    text: "#e8eaed",
    textMuted: "#9aa0ac",
    primary: "#4f8cff",
    success: "#3ec97c",
    warning: "#f2b84b",
    danger: "#f2545b",
  },
  radius: {
    sm: "6px",
    md: "10px",
    lg: "16px",
  },
  spacing: (n) => `${n * 4}px`,
  font: {
    family: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
  },
};

export default theme;
