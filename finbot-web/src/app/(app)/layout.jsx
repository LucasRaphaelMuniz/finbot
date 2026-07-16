"use client";

// (app)/layout.jsx — guarda de rota das telas protegidas: sem sessão,
// redireciona pro /login. Sidebar + Header ficam só aqui (não em cada
// page.jsx) pra não duplicar o shell em toda tela.
//
// Também resolve o passo final do cadastro (Fase 4.2): existe sessão
// Supabase, mas o backend pode ainda não ter usuario/grupo criado (signup
// concluído, mas /api/onboarding ou /api/convites/aceitar ainda não
// rodaram — ver components/CompletarCadastro). Contrato assumido com a
// Fase 4.3 (ainda não construída): GET /api/grupo responde 404 com
// {"erro": "sem_grupo"} nesse caso. Se a Fase 4.3 adotar outro contrato,
// ajustar só o catch abaixo.
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { useTema } from "@/components/ThemeRegistry";
import api from "@/services/api";
import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";
import Loading from "@/components/Loading";
import CompletarCadastro from "@/components/CompletarCadastro";
import TourPrimeiroLogin from "@/components/TourPrimeiroLogin";

export default function AppLayout({ children }) {
  const { loading, autenticado } = useAuth();
  const { setTema } = useTema();
  const router = useRouter();
  const [statusGrupo, setStatusGrupo] = useState("verificando"); // verificando | ok | pendente
  // Fase C do AUDITORIA_E_PLANO_CADASTRO.md — null enquanto não sabemos
  // ainda (evita "piscar" o tour antes do GET /conta/eu responder).
  const [tutorialVisto, setTutorialVisto] = useState(null);
  // Menu gaveta do mobile (Sidebar/Header — ver seus styles.js pro
  // breakpoint de 860px). No desktop esse estado é irrelevante: a Nav
  // ignora `aberta` via CSS e fica sempre visível.
  const [menuAberto, setMenuAberto] = useState(false);

  useEffect(() => {
    if (!loading && !autenticado) {
      router.replace("/login");
    }
  }, [loading, autenticado, router]);

  useEffect(() => {
    if (!autenticado) return;
    api
      .get("/grupo")
      .then(() => setStatusGrupo("ok"))
      .catch((err) => {
        if (err?.response?.status === 404 && err?.response?.data?.erro === "sem_grupo") {
          setStatusGrupo("pendente");
        } else {
          // Erro inesperado (backend fora do ar, etc.) — não trava o usuário
          // num loop de verificação; deixa passar e a tela em si mostra erro.
          setStatusGrupo("ok");
        }
      });
  }, [autenticado]);

  useEffect(() => {
    if (statusGrupo !== "ok") return;
    api
      .get("/conta/eu")
      .then(({ data }) => {
        setTutorialVisto(Boolean(data?.tutorial_visto));
        // Sincroniza com o valor salvo na conta (pode ter mudado em outro
        // dispositivo) — se bater com o que já tava no cache local, isso é
        // um no-op visual, sem flash.
        if (data?.tema === "light" || data?.tema === "dark") setTema(data.tema);
      })
      .catch(() => setTutorialVisto(true)); // erro inesperado: não força o tour
  }, [statusGrupo, setTema]);

  if (loading || statusGrupo === "verificando") return <Loading />;
  if (!autenticado) return null;
  if (statusGrupo === "pendente") {
    return <CompletarCadastro onConcluido={() => setStatusGrupo("ok")} />;
  }

  return (
    <div style={{ display: "flex" }}>
      <Sidebar aberta={menuAberto} onFechar={() => setMenuAberto(false)} />
      <div style={{ flex: 1, minHeight: "100vh", minWidth: 0 }}>
        <Header onAbrirMenu={() => setMenuAberto(true)} />
        <main style={{ padding: 24 }}>{children}</main>
      </div>
      {tutorialVisto === false && (
        <TourPrimeiroLogin onFechar={() => setTutorialVisto(true)} />
      )}
    </div>
  );
}
