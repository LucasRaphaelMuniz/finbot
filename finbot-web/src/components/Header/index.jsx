"use client";

import { useAuth } from "@/hooks/useAuth";
import { Bar, Direita, MenuBtn, SairBtn } from "./styles";

export default function Header({ onAbrirMenu }) {
  const { user, signOut } = useAuth();

  return (
    <Bar>
      {/* Só aparece abaixo de 860px (ver MenuBtn em styles.js) — abre o
          menu gaveta do Sidebar. */}
      <MenuBtn onClick={onAbrirMenu} aria-label="Abrir menu">☰</MenuBtn>
      <Direita>
        <span>{user?.email}</span>
        <SairBtn onClick={signOut}>Sair</SairBtn>
      </Direita>
    </Bar>
  );
}
