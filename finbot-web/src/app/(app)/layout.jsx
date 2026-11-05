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
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { useTema } from "@/components/ThemeRegistry";
import api from "@/services/api";
import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";
import BottomNav from "@/components/BottomNav";
import NovoLancamento from "@/components/NovoLancamento";
import Toast from "@/components/Toast";
import Loading from "@/components/Loading";
import CompletarCadastro from "@/components/CompletarCadastro";
import TourPrimeiroLogin from "@/components/TourPrimeiroLogin";
import { Shell, Coluna, Main } from "./styles";

export default function AppLayout({ children }) {
  const { loading, autenticado } = useAuth();
  const { setTema } = useTema();
  const router = useRouter();
  const [statusGrupo, setStatusGrupo] = useState("verificando"); // verificando | ok | pendente
  // Fase C do AUDITORIA_E_PLANO_CADASTRO.md — null enquanto não sabemos
  // ainda (evita "piscar" o tour antes do GET /conta/eu responder).
  const [tutorialVisto, setTutorialVisto] = useState(null);
  // Menu gaveta do mobile (abaixo de 860px), aberto pelo "Mais" da
  // BottomNav. No desktop esse estado é irrelevante: a Nav ignora `aberta`
  // via CSS e fica sempre visível.
  const [menuAberto, setMenuAberto] = useState(false);
  const menuBtnRef = useRef(null);
  // Novo lançamento é ação global (Header no desktop, "+" da BottomNav no
  // celular) — modal e toast de confirmação moram aqui, uma vez só.
  const [novoAberto, setNovoAberto] = useState(false);
  const [toast, setToast] = useState(null);
  const toastTimer = useRef(null);
  const avisar = useCallback((mensagem, tipo = "sucesso") => {
    clearTimeout(toastTimer.current);
    setToast({ mensagem, tipo });
    toastTimer.current = setTimeout(() => setToast(null), 3000);
  }, []);
  useEffect(() => () => clearTimeout(toastTimer.current), []);
  // Fecha a gaveta e devolve o foco pro botão "Mais" (Esc ou clique no fundo).
  const fecharMenu = useCallback(() => {
    if (!menuAberto) return;
    setMenuAberto(false);
    menuBtnRef.current?.focus();
  }, [menuAberto]);

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
    <Shell>
      <Sidebar aberta={menuAberto} onFechar={fecharMenu} />
      <Coluna>
        <Header onNovoLancamento={() => setNovoAberto(true)} />
        <Main>{children}</Main>
      </Coluna>
      <BottomNav
        ref={menuBtnRef}
        menuAberto={menuAberto}
        onAbrirMenu={() => setMenuAberto(true)}
        onNovoLancamento={() => setNovoAberto(true)}
      />
      <NovoLancamento
        aberto={novoAberto}
        onFechar={() => setNovoAberto(false)}
        onSalvo={(tipo) => {
          setNovoAberto(false);
          avisar(tipo === "entrada" ? "Entrada registrada." : "Gasto registrado.");
        }}
        onErro={(msg) => avisar(msg, "erro")}
      />
      <Toast mensagem={toast?.mensagem} tipo={toast?.tipo} />
      {tutorialVisto === false && (
        <TourPrimeiroLogin onFechar={() => setTutorialVisto(true)} />
      )}
    </Shell>
  );
}
