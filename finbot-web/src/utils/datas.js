// utils/datas.js — datas "YYYY-MM-DD" vindas da API, sem passar por fuso
// (new Date("2026-11-05") seria meia-noite UTC = dia 04 no Brasil).
import { formatarDataBR } from "@/utils/format";

export function mesAtualISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

// Diferença em dias entre hoje e a data (negativo = passado).
export function diasAte(iso) {
  if (!iso) return null;
  const [a, m, d] = iso.slice(0, 10).split("-").map(Number);
  const hoje = new Date();
  const alvo = new Date(a, m - 1, d);
  const base = new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate());
  return Math.round((alvo - base) / 86400000);
}

// Cabeçalho de grupo de dia: "Hoje", "Ontem", "Amanhã", "Segunda, 02/11".
export function rotuloDia(iso) {
  const dias = diasAte(iso);
  if (dias === 0) return "Hoje";
  if (dias === -1) return "Ontem";
  if (dias === 1) return "Amanhã";
  const [a, m, d] = iso.slice(0, 10).split("-").map(Number);
  const semana = new Date(a, m - 1, d).toLocaleDateString("pt-BR", { weekday: "long" });
  return `${semana.charAt(0).toUpperCase()}${semana.slice(1)}, ${formatarDataBR(iso).slice(0, 5)}`;
}
