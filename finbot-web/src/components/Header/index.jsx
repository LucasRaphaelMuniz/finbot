"use client";

// components/Header — barra do topo das telas logadas.
//
// Redesign de 05/11/2026: o botão ☰ saiu (no celular a gaveta abre pelo
// "Mais" da BottomNav) e entrou "Novo lançamento" como ação global no
// desktop. No celular o Header mostra só a marca e Sair — o "+" fica na
// BottomNav, ao alcance do polegar.
import { Plus, LogOut } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { Bar, Marca, Direita, Email, NovoBtn, SairBtn } from "./styles";

export default function Header({ onNovoLancamento }) {
  const { user, signOut } = useAuth();

  return (
    <Bar>
      <Marca aria-hidden="true">finbot</Marca>
      <Direita>
        <NovoBtn type="button" onClick={onNovoLancamento}>
          <Plus size={18} strokeWidth={2.25} aria-hidden="true" />
          Novo lançamento
        </NovoBtn>
        <Email>{user?.email}</Email>
        <SairBtn type="button" onClick={signOut}>
          <LogOut size={16} aria-hidden="true" />
          Sair
        </SairBtn>
      </Direita>
    </Bar>
  );
}
