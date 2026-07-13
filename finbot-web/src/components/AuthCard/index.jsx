import { Wrap, Card, Logo } from "./styles";

// components/AuthCard — shell compartilhado pelas 4 telas de (auth)/:
// login, cadastro, recuperar-senha, redefinir-senha. Evita repetir o
// container centralizado + logo em cada page.jsx.
export default function AuthCard({ children }) {
  return (
    <Wrap>
      <Card>
        <Logo>💰 Finbot</Logo>
        {children}
      </Card>
    </Wrap>
  );
}
