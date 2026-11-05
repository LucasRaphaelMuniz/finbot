"use client";

// app/(app)/(ajustes)/layout.jsx — Configurações: título único + abas por
// cima das 5 telas de ajuste. Antes eram 5 itens soltos no menu; agora o
// menu tem um "Configurações" só e a troca entre elas é pelas abas (padrão
// de Monarch/YNAB/Organizze). Ver ABAS_AJUSTES
// (components/Sidebar/itens.js) sobre as URLs.
import { useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ABAS_AJUSTES, rotaAtiva } from "@/components/Sidebar/itens";
import { Topo, Titulo, Abas, Aba, Conteudo } from "./styles";

export default function AjustesLayout({ children }) {
  const pathname = usePathname();
  const abasRef = useRef(null);

  // Celular: as abas rolam na horizontal; garante que a aba da tela atual
  // apareça (ex: "Plano" ficaria escondida à direita).
  useEffect(() => {
    abasRef.current
      ?.querySelector('[aria-current="page"]')
      ?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [pathname]);

  return (
    <div>
      <Topo>
        <Titulo>Configurações</Titulo>
        <Abas ref={abasRef} aria-label="Seções de configurações">
          {ABAS_AJUSTES.map(({ href, label }) => {
            const ativa = rotaAtiva(pathname, href);
            return (
              <Link key={href} href={href} passHref legacyBehavior>
                <Aba aria-current={ativa ? "page" : undefined}>{label}</Aba>
              </Link>
            );
          })}
        </Abas>
      </Topo>
      <Conteudo>{children}</Conteudo>
    </div>
  );
}
