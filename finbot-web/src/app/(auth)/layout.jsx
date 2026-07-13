"use client";

// (auth)/layout.jsx — guarda de rota inversa da (app)/layout.jsx: quem já
// tem sessão não deveria ver login/cadastro de novo, manda direto pro
// dashboard.
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";

export default function AuthLayout({ children }) {
  const { loading, autenticado } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && autenticado) {
      router.replace("/dashboard");
    }
  }, [loading, autenticado, router]);

  if (loading || autenticado) return null;

  return children;
}
