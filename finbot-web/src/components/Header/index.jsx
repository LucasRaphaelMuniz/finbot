"use client";

import { useAuth } from "@/hooks/useAuth";
import { forwardRef } from "react";
import { ID_MENU } from "@/components/Sidebar";
import { Bar, Direita, MenuBtn, SairBtn } from "./styles";

// `menuBtnRef`: o layout devolve o foco pro ☰ quando a gaveta fecha.
function Header({ onAbrirMenu, menuAberto = false }, menuBtnRef) {
  const { user, signOut } = useAuth();

  return (
    <Bar>
      {/* Só aparece abaixo de 860px (ver MenuBtn em styles.js) — abre o
          menu gaveta do Sidebar. */}
      <MenuBtn
        ref={menuBtnRef}
        onClick={onAbrirMenu}
        aria-label="Abrir menu"
        aria-expanded={menuAberto}
        aria-controls={ID_MENU}
      >
        ☰
      </MenuBtn>
      <Direita>
        <span>{user?.email}</span>
        <SairBtn onClick={signOut}>Sair</SairBtn>
      </Direita>
    </Bar>
  );
}

export default forwardRef(Header);
