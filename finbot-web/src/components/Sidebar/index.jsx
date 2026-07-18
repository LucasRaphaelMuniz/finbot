"use client";

// components/Sidebar — navegação principal do (app)/layout.jsx. Rotas
// espelham 1:1 as telas da Fase 5 do PLANO_EXECUCAO.md.
import { usePathname } from "next/navigation";
import Link from "next/link";
import { Nav, Logo, ItemLink, Overlay } from "./styles";

const ITENS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/lancamentos", label: "Lançamentos" },
  { href: "/fixas", label: "Despesas fixas" },
  { href: "/parcelas", label: "Parcelas futuras" },
  { href: "/importacao", label: "Importação" },
  { href: "/grupo", label: "Grupo" },
  { href: "/formas", label: "Formas de pagamento" },
  { href: "/categorias", label: "Categorias" },
  { href: "/planos", label: "Planos" },
  { href: "/conta", label: "Conta" },
];

// `aberta`/`onFechar` só importam abaixo de 860px (menu gaveta) — no
// desktop a Nav ignora esses props via CSS (ver styles.js) e fica sempre
// visível, então não precisa de estado nenhum lá.
export default function Sidebar({ aberta = false, onFechar }) {
  const pathname = usePathname();

  return (
    <>
      <Overlay $aberta={aberta} onClick={onFechar} />
      <Nav $aberta={aberta}>
        <Logo>💰 Finbot</Logo>
        {ITENS.map((item) => (
          <Link key={item.href} href={item.href} passHref legacyBehavior>
            {/* onClick fecha o menu gaveta ao navegar — no mobile, sem
                isso a pessoa trocaria de tela com o menu ainda aberto por
                cima. No desktop é um no-op inofensivo (onFechar nem é
                passado com sidebar sempre visível). */}
            <ItemLink $ativo={pathname?.startsWith(item.href)} onClick={onFechar}>
              {item.label}
            </ItemLink>
          </Link>
        ))}
      </Nav>
    </>
  );
}
