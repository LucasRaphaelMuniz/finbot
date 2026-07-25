"use client";

// components/ChartComparativo — barras dos últimos 6 meses, entradas x
// gastos (GET /api/resumo -> comparativo_6_meses: [{mes, gastos, entradas}]).
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid } from "recharts";
import { brl, formatarCompetencia } from "@/utils/format";

// `onClickBarra(tipo, mes)` — pedido do Lucas (24/07/2026): clicar numa
// barra abre o detalhe dos lançamentos daquele mês. Opcional: sem o prop,
// o gráfico continua só-leitura (nenhuma outra tela usa este componente
// hoje, mas não faz sentido a barra reagir ao clique sem ninguém escutando).
export default function ChartComparativo({ dados, onClickBarra }) {
  const dadosFormatados = (dados || []).map((d) => ({
    ...d,
    mesLabel: formatarCompetencia(`${d.mes}-01`),
  }));

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={dadosFormatados}>
        <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
        <XAxis dataKey="mesLabel" fontSize={12} />
        <YAxis fontSize={12} />
        <Tooltip formatter={(v) => brl(v)} />
        <Legend />
        <Bar
          dataKey="entradas" name="Entradas" fill="#3ec97c" radius={[4, 4, 0, 0]}
          cursor={onClickBarra ? "pointer" : undefined}
          onClick={onClickBarra ? (ponto) => onClickBarra("entradas", ponto.mes) : undefined}
        />
        <Bar
          dataKey="gastos" name="Gastos" fill="#f2545b" radius={[4, 4, 0, 0]}
          cursor={onClickBarra ? "pointer" : undefined}
          onClick={onClickBarra ? (ponto) => onClickBarra("gastos", ponto.mes) : undefined}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}
