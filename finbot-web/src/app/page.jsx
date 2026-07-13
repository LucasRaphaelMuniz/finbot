"use client";

// app/page.jsx — rota raiz "/" só decide pra onde mandar: dashboard se tem
// sessão, login se não tem. Nenhuma UI própria.
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";

export default function Home() {
  const { loading, autenticado } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    router.replace(autenticado ? "/dashboard" : "/login");
  }, [loading, autenticado, router]);

  return null;
}
