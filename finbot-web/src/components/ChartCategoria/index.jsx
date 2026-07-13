"use client";

// components/ChartCategoria — donut de gastos por categoria no mês
// (GET /api/resumo -> por_categoria: [{categoria, total}]).
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { brl } from "@/utils/format";
import EmptyState from "@/components/EmptyState";

const CORES = ["#4f8cff", "#3ec97c", "#f2b84b", "#f2545b", "#a06cd5", "#3ec9c9", "#e88bd6"];

export default function ChartCategoria({ dados }) {
  if (!dados || dados.length === 0) {
    return <EmptyState titulo="Sem gastos neste mês" />;
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <PieChart>
        <Pie
          data={dados}
          dataKey="total"
          nameKey="categoria"
          innerRadius={60}
          outerRadius={100}
          paddingAngle={2}
        >
          {dados.map((_, i) => (
            <Cell key={i} fill={CORES[i % CORES.length]} />
          ))}
        </Pie>
        <Tooltip formatter={(v) => brl(v)} />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}
