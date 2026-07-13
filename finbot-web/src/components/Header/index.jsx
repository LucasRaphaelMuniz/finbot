"use client";

import { useAuth } from "@/hooks/useAuth";
import { Bar, SairBtn } from "./styles";

export default function Header() {
  const { user, signOut } = useAuth();

  return (
    <Bar>
      <span>{user?.email}</span>
      <SairBtn onClick={signOut}>Sair</SairBtn>
    </Bar>
  );
}
