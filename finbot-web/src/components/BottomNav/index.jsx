"use client";

// components/BottomNav — barra de abas fixa no rodapé, só abaixo de 860px
// (redesign de 05/11/2026, padrão Mobills/Organizze/Nubank). Substitui o
// botão ☰ do Header: as 3 telas mais usadas ficam a 1 toque, o "+" central
// abre o NovoLancamento e "Mais" abre a gaveta com o resto (Sidebar).
import { forwardRef } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { House, ArrowLeftRight, CalendarCheck, Menu, Plus } from "lucide-react";
import { ID_MENU } from "@/components/Sidebar";
import { rotaAtiva } from "@/components/Sidebar/itens";
import { Barra, Aba, AbaLink, Mais } from "./styles";

const ABAS = [
  { href: "/dashboard", label: "Início", Icone: House },
  { href: "/lancamentos", label: "Lançamentos", Icone: ArrowLeftRight },
  null, // posição do "+"
  { href: "/contas", label: "Contas", Icone: CalendarCheck },
];

function BottomNav({ menuAberto = false, onAbrirMenu, onNovoLancamento }, maisRef) {
  const pathname = usePathname();
  const naGaveta = !ABAS.some((a) => a && rotaAtiva(pathname, a.href));

  return (
    <Barra aria-label="Atalhos">
      {ABAS.map((aba) => {
        if (!aba) {
          return (
            <Mais key="novo" type="button" onClick={onNovoLancamento} aria-label="Novo lançamento">
              <Plus size={26} strokeWidth={2.25} aria-hidden="true" />
            </Mais>
          );
        }
        const ativo = rotaAtiva(pathname, aba.href);
        return (
          <Link key={aba.href} href={aba.href} passHref legacyBehavior>
            <AbaLink $ativo={ativo} aria-current={ativo ? "page" : undefined}>
              <aba.Icone size={22} strokeWidth={ativo ? 2.25 : 1.75} aria-hidden="true" />
              {aba.label}
            </AbaLink>
          </Link>
        );
      })}
      <Aba
        ref={maisRef}
        type="button"
        $ativo={naGaveta}
        onClick={onAbrirMenu}
        aria-expanded={menuAberto}
        aria-controls={ID_MENU}
      >
        <Menu size={22} strokeWidth={naGaveta ? 2.25 : 1.75} aria-hidden="true" />
        Mais
      </Aba>
    </Barra>
  );
}

export default forwardRef(BottomNav);
