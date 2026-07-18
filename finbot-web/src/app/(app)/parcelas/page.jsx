"use client";

// app/(app)/parcelas/page.jsx — compras parceladas em andamento (pedido do
// Lucas em 18/07/2026: "quantas faltam, o total, etc"). Só leitura: criar
// parcelado é no modal de Lançamentos (ou no bot), excluir é na linha da
// parcela em Lançamentos ("compra inteira") — esta tela é visão de
// acompanhamento, não mais um CRUD.
//
// "Restantes" conta parcelas com competência >= mês corrente direto de
// `gastos` (fonte de verdade — parcela excluída individualmente sai da
// conta), não do plano original da compra; o plano (ex: 12x) aparece só
// como referência no "faltam 3 de 12".
import { useApi } from "@/hooks/useApi";
import { brl } from "@/utils/format";
import DataTable from "@/components/DataTable";

function formatarCompetencia(iso) {
  if (!iso) return "—";
  const [ano, mes] = iso.split("-");
  return `${mes}/${ano}`;
}

export default function ParcelasPage() {
  const { dados, loading } = useApi("/gastos/parcelamentos");

  const itens = dados?.itens || [];
  const totalRestante = itens.reduce((soma, c) => soma + Number(c.valor_restante || 0), 0);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 24 }}>
        <h1 style={{ fontSize: 20 }}>Parcelas futuras</h1>
        {itens.length > 0 && (
          <span style={{ fontSize: 14, opacity: 0.8, alignSelf: "center" }}>
            Total a vencer: <strong>{brl(totalRestante)}</strong>
          </span>
        )}
      </div>

      <DataTable
        columns={[
          { key: "descricao", label: "Descrição", render: (c) => c.descricao || "—" },
          {
            key: "tipo",
            label: "Tipo",
            render: (c) => (c.tipo === "fixa" ? "custo fixo com prazo" : "parcelamento"),
          },
          { key: "forma_nome", label: "Forma" },
          { key: "membro_nome", label: "Membro" },
          {
            key: "restantes",
            label: "Faltam",
            render: (c) => `${c.parcelas_restantes} de ${c.parcelas}`,
          },
          { key: "valor_restante", label: "Valor a vencer", render: (c) => brl(c.valor_restante) },
          { key: "valor_total", label: "Total da compra", render: (c) => brl(c.valor_total) },
          {
            key: "proxima_competencia",
            label: "Próxima",
            render: (c) => formatarCompetencia(c.proxima_competencia),
          },
          {
            key: "ultima_competencia",
            label: "Última",
            render: (c) => formatarCompetencia(c.ultima_competencia),
          },
        ]}
        rows={itens}
        loading={loading}
        vazio={{
          titulo: "Nenhuma compra parcelada em andamento",
          descricao: "Compras parceladas aparecem aqui enquanto tiverem parcelas a vencer.",
        }}
      />
    </div>
  );
}
