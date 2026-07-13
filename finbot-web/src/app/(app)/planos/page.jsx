"use client";

// app/(app)/planos/page.jsx — Fase 6.3 do PLANO_EXECUCAO.md: cards dos 4
// planos, plano atual do grupo destacado. Preços definidos pelo Lucas em
// 11/07/2026 (Fase 6, P6) — botão de contratação continua desabilitado
// porque não existe gateway de pagamento ainda (D7 adiada, P5): mostrar o
// preço já é útil (usuário sabe quanto vai custar), cobrar de fato é outra
// fase.
import { useApi } from "@/hooks/useApi";
import Loading from "@/components/Loading";
import { brl } from "@/utils/format";
import { Grid, Card, Selo, Nome, Preco, Membros, BotaoContratar } from "./styles";

export default function PlanosPage() {
  const { dados: planosData, loading: loadingPlanos } = useApi("/planos");
  const { dados: assinatura, loading: loadingAssinatura } = useApi("/assinatura");

  if (loadingPlanos || loadingAssinatura) return <Loading />;

  const planos = planosData?.itens || [];

  return (
    <div>
      <h1 style={{ fontSize: 20, marginBottom: 8 }}>Planos</h1>
      <p style={{ opacity: 0.7, marginBottom: 24, fontSize: 14 }}>
        Contratação ainda não está disponível — por enquanto, todos os grupos usam
        o finbot sem limite de membros, independente do plano mostrado abaixo.
      </p>

      <Grid>
        {planos.map((p) => {
          const atual = assinatura?.plano_id === p.id;
          return (
            <Card key={p.id} $atual={atual}>
              {atual && <Selo>Plano atual</Selo>}
              <Nome>{p.nome}</Nome>
              <Preco>
                {p.preco_mensal != null ? `${brl(p.preco_mensal)}/mês` : "Em breve"}
              </Preco>
    