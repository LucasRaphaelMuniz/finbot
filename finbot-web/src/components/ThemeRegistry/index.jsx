"use client";

// components/ThemeRegistry — separado do layout raiz (Server Component) só
// porque ThemeProvider/createGlobalStyle precisam de "use client".
import { ThemeProvider } from "styled-components";
import theme from "@/styles/theme";
import GlobalStyle from "@/styles/global";

export default function ThemeRegistry({ children }) {
  return (
    <ThemeProvider theme={theme}>
      <GlobalStyle />
      {children}
    </ThemeProvider>
  );
}
