import { Card, Label, Valor, Detalhe } from "./styles";

// components/StatCard — 1 número + rótulo, usado na linha de cards do
// dashboard (§5.2 do plano: entradas do mês, gastos do mês, saldo, % dos
// limites usados). `detalhe` (opcional) é uma linha menor abaixo do valor —
// ex: decompor "gastos previstos" em reais + fixas previstas.
export default function StatCard({ label, valor, detalhe, tom }) {
  return (
    <Card>
      <Label>{label}</Label>
      <Valor $tom={tom}>{valor}</Valor>
      {detalhe && <Detalhe>{detalhe}</Detalhe>}
    </Card>
  );
}
