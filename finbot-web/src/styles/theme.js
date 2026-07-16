// styles/theme.js — tokens de design compartilhados entre componentes
// styled-components. Cores neutras + 1 cor de destaque; ajustar depois da
// síntese visual da Fase 0 (docs/benchmarking.md) quando as telas da Fase 5
// forem desenhadas de verdade.
//
// Dark/light (pedido do Lucas, persistido por conta — ver
// components/ThemeRegistry): só a paleta `colors` muda entre os dois temas;
// radius/spacing/font são os mesmos independente do tema, então ficam fora
// do objeto de cores em vez de duplicados nos dois.
const CORES = {
  dark: {
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
  // Não é só inverter bg/text do dark: success/warning/danger do dark são
  // saturados demais pra usar como texto sobre fundo branco (contraste
  // baixo, ex: #f2545b em cima de #fff fica perto do limite de legibilidade)
  // — escurecidos aqui pra continuar legíveis como texto (Erro, badges) e
  // não só como fundo de botão.
  light: {
    bg: "#f4f5f7",
    surface: "#ffffff",
    surfaceAlt: "#eceff3",
    border: "#dbdfe6",
    text: "#181b20",
    textMuted: "#5b6270",
    primary: "#3f7de0",
    success: "#1f9d5e",
    warning: "#b8790a",
    danger: "#d8383f",
  },
};

const BASE = {
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

export function getTheme(nome) {
  return { ...BASE, nome, colors: CORES[nome] || CORES.dark };
}

// Export default mantido pra não quebrar quem ainda importa `theme` direto
// (ex.: uso fora de componente, scripts) — equivale ao tema escuro, que
// sempre foi o único até agora.
const theme = getTheme("dark");

export default theme;
