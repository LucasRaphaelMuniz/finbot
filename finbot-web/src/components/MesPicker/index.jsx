"use client";

// components/MesPicker — navega mês a mês (competência), não usa
// <input type="month"> porque a UX de setinha prev/next é mais rápida pro
// caso de uso real (comparar mês a mês), que é o padrão observado nos apps
// de referência (docs/benchmarking.md, Fase 0).
import { Wrap, Botao, Label } from "./styles";

const MESES_PT = [
  "janeiro", "fevereiro", "março", "abril", "maio", "junho",
  "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
];

// value: "YYYY-MM"
export default function MesPicker({ value, onChange }) {
  const [ano, mes] = value.split("-").map(Number);

  function mudarMes(delta) {
    const data = new Date(ano, mes - 1 + delta, 1);
    const novoAno = data.getFullYear();
    const novoMes = String(data.getMonth() + 1).padStart(2, "0");
    onChange(`${novoAno}-${novoMes}`);
  }

  return (
    <Wrap>
      <Botao onClick={() => mudarMes(-1)} aria-label="Mês anterior">‹</Botao>
      <Label>{MESES_PT[mes - 1]}/{ano}</Label>
      <Botao onClick={() => mudarMes(1)} aria-label="Próximo mês">›</Botao>
    </Wrap>
  );
}
