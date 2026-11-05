"use client";

// components/Sidebar — navegação principal do (app)/layout.jsx. Itens e
// grupos vêm de ./itens.js (o mesmo mapa da BottomNav do celular).
import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { GRUPOS_NAV, rotaAtiva } from "./itens";
import { Nav, Logo, LogoMarca, Grupo, GrupoTitulo, ItemLink, Overlay } from "./styles";

export const ID_MENU = "menu-principal";
export const QUERY_GAVETA = "(max-width: 860px)";

// Abaixo de 860px a Sidebar vira gaveta, aberta pelo botão "Mais" da
// BottomNav (`aberta`/`onFechar`). No desktop esses props não fazem nada:
// a Nav ignora `aberta` via CSS e fica sempre visível.
//
// Acessibilidade da gaveta (auditoria de UX, 05/11/2026): ao abrir, o foco
// vai pro link da tela atual; Esc fecha e devolve o foco pro botão que
// abriu (o layout cuida do retorno). Fechada no mobile, a Nav fica `inert`
// — senão, mesmo fora da tela (translateX), os links continuariam no Tab e
// no leitor de tela.
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
      <Nav ref={navRef} id={ID_MENU} aria-label="Menu principal" $aberta={aberta}>
        <Logo>
          <LogoMarca aria-hidden="true">f</LogoMarca>
          finbot
        </Logo>
        {GRUPOS_NAV.map((grupo) => (
          <Grupo key={grupo.titulo} role="group" aria-labelledby={`nav-${grupo.titulo}`}>
            <GrupoTitulo id={`nav-${grupo.titulo}`}>{grupo.titulo}</GrupoTitulo>
            {grupo.itens.map((item) => {
              const { href, label, Icone } = item;
              const ativo = rotaAtiva(pathname, item);
              return (
                <Link key={href} href={href} passHref legacyBehavior>
                  {/* onClick fecha a gaveta ao navegar no celular; no
                      desktop é um no-op. */}
                  <ItemLink $ativo={ativo} aria-current={ativo ? "page" : undefined} onClick={onFechar}>
                    <Icone size={18} strokeWidth={1.75} aria-hidden="true" />
                    {label}
                  </ItemLink>
                </Link>
              );
            })}
          </Grupo>
        ))}
      </Nav>
    </>
  );
}
