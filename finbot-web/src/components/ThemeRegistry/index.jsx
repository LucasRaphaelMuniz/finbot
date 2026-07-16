"use client";

// components/ThemeRegistry — separado do layout raiz (Server Component) só
// porque ThemeProvider/createGlobalStyle precisam de "use client".
//
// Dark/light por conta (pedido do Lucas): o estado "tema" mora aqui, não em
// useAuth — ThemeRegistry fica ACIMA de AuthProvider na árvore (ver
// app/layout.jsx), então não tem como ler sessão/usuário aqui dentro. Quem
// sincroniza com o valor salvo no banco é (app)/layout.jsx (dentro do
// AuthProvider), chamando o `setTema` exposto por este contexto depois que
// GET /api/conta/eu responde.
//
// Decisão de design: guarda uma cópia em localStorage (chave TEMA_KEY) só
// pra pintar a tela certa já no primeiro render — sem isso, todo carregamento
// começaria sempre no tema escuro (valor inicial "dark" no useState) e daria
// um flash visível pra quem prefere claro, até o GET /conta/eu voltar.
// localStorage aqui é cache de UI, não a fonte de verdade — o banco continua
// sendo o dono do dado (por isso "salvo por perfil": segue a conta entre
// dispositivos, localStorage só evita o flash local).
import { createContext, useContext, useEffect, useState } from "react";
import { ThemeProvider } from "styled-components";
import { getTheme } from "@/styles/theme";
import GlobalStyle from "@/styles/global";

const TEMA_KEY = "finbot_tema";
const TemaContext = createContext(null);

function lerTemaCache() {
  if (typeof window === "undefined") return "dark";
  const salvo = window.localStorage.getItem(TEMA_KEY);
  return salvo === "light" || salvo === "dark" ? salvo : "dark";
}

export default function ThemeRegistry({ children }) {
  // Lazy initializer: roda só no primeiro render, evita 1 render extra com
  // "dark" antes de trocar pro valor cacheado.
  const [tema, setTemaState] = useState(lerTemaCache);

  function setTema(novoTema) {
    setTemaState(novoTema);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(TEMA_KEY, novoTema);
    }
  }

  return (
    <TemaContext.Provider value={{ tema, setTema }}>
      <ThemeProvider theme={getTheme(tema)}>
        <GlobalStyle />
        {children}
      </ThemeProvider>
    </TemaContext.Provider>
  );
}

export function useTema() {
  const ctx = useContext(TemaContext);
  if (!ctx) {
    throw new Error("useTema precisa estar dentro de <ThemeRegistry>");
  }
  return ctx;
}
