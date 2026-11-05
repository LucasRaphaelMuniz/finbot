// test-utils.jsx — `render` do Testing Library já envolvido no
// ThemeProvider do styled-components. Sem isso todo componente estilizado
// que lê `theme.spacing(...)`/`theme.colors` quebra no Jest com
// "theme.spacing is not a function" (as telas rodam dentro do
// ThemeRegistry no app, mas o teste renderiza a página solta).
import { render } from "@testing-library/react";
import { ThemeProvider } from "styled-components";
import { getTheme } from "@/styles/theme";

function ComTema({ children }) {
  return <ThemeProvider theme={getTheme("dark")}>{children}</ThemeProvider>;
}

function renderComTema(ui, options) {
  return render(ui, { wrapper: ComTema, ...options });
}

export * from "@testing-library/react";
export { renderComTema as render };
