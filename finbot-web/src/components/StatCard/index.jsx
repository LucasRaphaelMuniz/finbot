import { Card, Label, Valor } from "./styles";

// components/StatCard — 1 número + rótulo, usado na linha de cards do
// dashboard (§5.2 do plano: entradas do mês, gastos do mês, saldo, % dos
// limites usados).
export default function StatCard({ label, valor, tom }) {
  return (
    <Card>
      <Label>{label}</Label>
      <Valor $tom={tom}>{valor}</Valor>
    </Card>
  );
}
