"use client";

// components/Sidebar — navegação principal do (app)/layout.jsx. Rotas
// espelham 1:1 as telas da Fase 5 do PLANO_EXECUCAO.md.
import { usePathname } from "next/navigation";
import Link from "next/link";
import { Nav, Logo, ItemLink } from "./styles";

const ITENS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/lancamentos", label: "Lançamentos" },
  { href: "/fixas", label: "Despesas fixas" },
  { href: "/importacao", label: "Importação" },
  { href: "/grupo", label: "Grupo" },
  { href: "/formas", label: "Formas de pagamento" },
  { href: "/categorias", label: "Categorias" },
  { href: "/planos", label: "Planos" },
  { href: "/conta", label: "Conta" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <Nav>
      <Logo>💰 Finbot</Logo>
      {ITENS.map((item) => (
        <Link key={item.href} href={item.href} passHref legacyBehavior>
          <ItemLink $ativo={pathname?.startsWith(item.href)}>{item.label}</ItemLink>
        </Link>
      ))}
    </Nav>
  );
}
