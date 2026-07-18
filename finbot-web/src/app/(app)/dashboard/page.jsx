"use client";

// app/(app)/dashboard/page.jsx — resumo analítico, só leitura (Fase 5.2 do
// PLANO_EXECUCAO.md). Tudo vem de 1 request (GET /api/resumo) — agregação
// roda no Flask (services/resumo.py), não no browser (decisão D6).
import { useMemo, useState } from "react";
import { useApi } from "@/hooks/useApi";
import { brl } from "@/utils/format";
import StatCard from "@/components/StatCard";
import ChartCategoria from "@/components/ChartCategoria";
import ChartComparativo from "@/components/ChartComparativo";
import ChartFixoVariavel from "@/components/ChartFixoVariavel";
import MesPicker from "@/components/MesPicker";
import Loading from "@/components/Loading";
import { Header, StatsRow, ChartsGrid, ChartCard, ChartTitulo } from "./styles";

function mesAtualISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export default function DashboardPage() {
  const [mes, setMes] = useState(mesAtualISO());
  const url = useMemo(() => `/resumo?mes=${mes}`, [mes]);
  const { dados, loading } = useApi(url);

  return (
    <div>
      <Header>
        <h1 style={{ fontSize: 20 }}>Dashboard</h1>
        <MesPicker value={mes} onChange={setMes} />
      </Header>

      {loading || !dados ? (
        <Loading />
      ) : (
        <>
          <StatsRow>
            {/* Mesmo padrão dos gastos: mês corrente/futuro antecipa
                entradas recorrentes (salário) ainda não lançadas. */}
            {dados.entradas_previstas > 0 ? (
              <StatCard
                label="Entradas do mês (com previstas)"
                valor={brl(dados.total_entradas_previsto)}
                detalhe={`${brl(dados.total_entradas)} reais + ${brl(dados.entradas_previstas)} recorrentes previstas`}
                tom="sucesso"
              />
            ) : (
              <StatCard label="Entradas do mês" valor={brl(dados.total_entradas)} tom="sucesso" />
            )}
            {/* Gastos previstos = reais + fixas ainda não lançadas no mês
                (fixas_previstas > 0 só em mês corrente/futuro). Mês fechado
                mostra só o real, sem card extra. */}
            {dados.fixas_previstas > 0 ? (
              <StatCard
                label="Gastos do mês (com previstos)"
                valor={brl(dados.total_gastos_previsto)}
                detalhe={`${brl(dados.total_gastos)} reais + ${brl(dados.fixas_previstas)} fixas previstas`}
                tom="erro"
              />
            ) : (
              <StatCard label="Gastos do mês" valor={brl(dados.total_gastos)} tom="erro" />
            )}
            <StatCard
              label="Saldo do mês"
              valor={brl(dados.saldo)}
              detalhe={
                dados.fixas_previstas > 0 || dados.entradas_previstas > 0
                  ? `projetado com previstos: ${brl(dados.saldo_previsto)}`
                  : undefined
              }
              tom={dados.saldo >= 0 ? "sucesso" : "erro"}
            />
            {/* Caixa: o que sai do bolso no mês (à vista + fatura vencendo).
                Só aparece quando há fatura a pagar — sem cartão, caixa e
                gastos são a mesma coisa e o card seria redundante. */}
            {dados.caixa?.fatura_a_pagar > 0 && (
              <StatCard
                label="Saída de caixa do mês"
                valor={brl(dados.caixa.saida_total)}
                detalhe={`${brl(dados.caixa.fatura_a_pagar)} de fatura(s) vencendo`}
                tom="erro"
              />
            )}
            <StatCard
              label="% médio dos limites usados"
              valor={dados.pct_limite_medio != null ? `${dados.pct_limite_medio.toFixed(0)}%` : "—"}
              tom={dados.pct_limite_medio > 80 ? "erro" : undefined}
            />
          </StatsRow>

          <ChartsGrid>
            <ChartCard>
              <ChartTitulo>Gastos por categoria</ChartTitulo>
              <ChartCategoria dados={dados.por_categoria} />
            </ChartCard>
            <ChartCard>
              <ChartTitulo>Fixo × variável</ChartTitulo>
              <ChartFixoVariavel dados={dados.fixo_variavel} />
            </ChartCard>
            <ChartCard style={{ gridColumn: "1 / -1" }}>
              <ChartTitulo>Últimos 6 meses — entradas × gastos</ChartTitulo>
              <ChartComparativo dados={dados.comparativo_6_meses} />
            </ChartCard>
          </ChartsGrid>
        </>
      )}
    </div>
  );
}
