"use client";

// components/Sidebar — navegação principal do (app)/layout.jsx. Rotas
// espelham 1:1 as telas da Fase 5 do PLANO_EXECUCAO.md.
import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { Nav, Logo, ItemLink, Overlay } from "./styles";

const ITENS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/contas", label: "Contas do mês" },
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

export const ID_MENU = "menu-principal";
const QUERY_GAVETA = "(max-width: 860px)";

// `aberta`/`onFechar` só importam abaixo de 860px (menu gaveta) — no
// desktop a Nav ignora esses props via CSS (ver styles.js) e fica sempre
// visível.
//
// Acessibilidade da gaveta (auditoria de UX, 05/11/2026): ao abrir, o foco
// vai pro link da tela atual; Esc fecha e devolve o foco pro botão ☰
// (quem chama passa `onFechar`, o layout cuida do retorno). Fechada no
// mobile, a Nav fica `inert` — antes, mesmo fora da tela (translateX),
// os 11 links continuavam no Tab e no leitor de tela.
export default function Sidebar({ aberta = false, onFechar }) {
  const pathname = usePathname();
  const navRef = useRef(null);
  const [gaveta, setGaveta] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia(QUERY_GAVETA);
    const atualizar = () => setGaveta(mq.matches);
    atualizar();
    mq.addEventListener("change", atualizar);
    return () => mq.removeEventListener("change", atualizar);
  }, []);

  // `inert` via atributo: React 18 não repassa a prop `inert` pro DOM.
  useEffect(() => {
    const nav = navRef.current;
    if (!nav) return;
    if (gaveta && !aberta) nav.setAttribute("inert", "");
    else nav.removeAttribute("inert");
  }, [gaveta, aberta]);

  useEffect(() => {
    if (!gaveta || !aberta) return undefined;
    const nav = navRef.current;
    (nav?.querySelector('[aria-current="page"]') || nav?.querySelector("a"))?.focus();

    function onKeyDown(e) {
      if (e.key === "Escape") onFechar?.();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [gaveta, aberta, onFechar]);

  return (
    <>
      <Overlay $aberta={aberta} onClick={onFechar} />
      <Nav
        ref={navRef}
        id={ID_MENU}
        aria-label="Menu principal"
        $aberta={aberta}
      >
        <Logo>💰 Finbot</Logo>
        {ITENS.map((item) => {
          const ativo = pathname?.startsWith(item.href);
          return (
            <Link key={item.href} href={item.href} passHref legacyBehavior>
              {/* onClick fecha o menu gaveta ao navegar — no mobile, sem
                  isso a pessoa trocaria de tela com o menu ainda aberto por
                  cima. No desktop é um no-op inofensivo. */}
              <ItemLink $ativo={ativo} aria-current={ativo ? "page" : undefined} onClick={onFechar}>
                {item.label}
              </ItemLink>
            </Link>
          );
        })}
      </Nav>
    </>
  );
}
