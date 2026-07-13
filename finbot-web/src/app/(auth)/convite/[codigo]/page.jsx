"use client";

// (auth)/convite/[codigo] — landing do link de convite compartilhado
// (ex: finbot.app/convite/FIN-8K3M2P). Só existe pra pré-preencher o
// campo de código na tela de cadastro; a validação de fato (existe? já
// usado? expirado?) é responsabilidade do backend em
// POST /api/convites/aceitar, chamada depois do login (ver cadastro/page.jsx).
import { useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import Loading from "@/components/Loading";

export default function ConvitePage() {
  const router = useRouter();
  const params = useParams();

  useEffect(() => {
    const codigo = params?.codigo;
    router.replace(codigo ? `/cadastro?convite=${encodeURIComponent(codigo)}` : "/cadastro");
  }, [params, router]);

  return <Loading />;
}
