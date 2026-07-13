import StyledComponentsRegistry from "@/lib/StyledComponentsRegistry";
import ThemeRegistry from "@/components/ThemeRegistry";
import { AuthProvider } from "@/hooks/useAuth";

export const metadata = {
  title: "Finbot",
  description: "Controle financeiro compartilhado, direto do WhatsApp e da web.",
};

// Root layout — só providers (Auth, Theme). Nenhuma lógica de negócio ou
// navegação aqui: isso fica em (auth)/ e (app)/layout.jsx, que decidem o
// que renderizar dependendo de sessão.
export default function RootLayout({ children }) {
  return (
    <html lang="pt-BR">
      <body>
        <StyledComponentsRegistry>
          <ThemeRegistry>
            <AuthProvider>{children}</AuthProvider>
          </ThemeRegistry>
        </StyledComponentsRegistry>
      </body>
    </html>
  );
}
