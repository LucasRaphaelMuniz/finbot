"use client";

// components/ChartFixoVariavel — fixo (despesa_fixa_id preenchido) x
// variável, mês atual (GET /api/resumo -> fixo_variavel: {fixo, variavel}).
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { brl } from "@/utils/format";
import EmptyState from "@/components/EmptyState";

export default function ChartFixoVariavel({ dados }) {
  const fixo = dados?.fixo || 0;
  const variavel = dados?.variavel || 0;

  if (fixo === 0 && variavel === 0) {
    return <EmptyState titulo="Sem gastos neste mês" />;
  }

  const data = [
    { nome: "Fixo", valor: fixo },
    { nome: "Variável", valor: variavel },
  ];

  return (
    <ResponsiveContainer width="100%" height={280}>
      <PieChart>
        <Pie data={data} dataKey="valor" nameKey="nome" innerRadius={60} outerRadius={100} paddingAngle={2}>
          <Cell fill="#4f8cff" />
          <Cell fill="#f2b84b" />
        </Pie>
        <Tooltip formatter={(v) => brl(v)} />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}
