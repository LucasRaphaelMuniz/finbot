// utils/format.js — formatação BR compartilhada entre componentes.
// A API Flask sempre devolve valor como number com ponto decimal (contrato
// definido no §4.3 do PLANO_EXECUCAO.md); formatar pro padrão brasileiro é
// responsabilidade do front, não do backend.

export function brl(valor) {
  const n = Number(valor) || 0;
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

const MESES_PT = [
  "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
];

// competencia vem da API como "YYYY-MM-01" (DATE truncado no mês, ver
// services/competencia.py no backend) — parse manual em vez de `new Date`
// pra não cair em problema de fuso horário deslocando o dia.
export function formatarCompetencia(competencia) {
  if (!competencia) return "";
  const [ano, mes] = competencia.split("-");
  return `${MESES_PT[parseInt(mes, 10) - 1]}/${ano}`;
}

export function formatarDataBR(isoDate) {
  if (!isoDate) return "";
  const [ano, mes, dia] = isoDate.slice(0, 10).split("-");
  return `${dia}/${mes}/${ano}`;
}

// Formata número de WhatsApp só pra EXIBIÇÃO (mesma filosofia do
// TelefoneInput: quem decide o JID "de verdade" é utils/telefone.py no
// backend, isso aqui é só cosmético). Espera dígitos com DDI, ex:
// "5544912345678" → "+55 (44) 91234-5678".
export function formatarTelefoneExibicao(numero) {
  if (!numero) return "";
  let digitos = String(numero).replace(/\D/g, "");
  if (digitos.length === 12 || digitos.length === 13) {
    if (digitos.startsWith("55")) digitos = digitos.slice(2);
  }
  if (digitos.length < 10) return `+55 ${digitos}`;
  const ddd = digitos.slice(0, 2);
  const resto = digitos.slice(2);
  const parteFinal = resto.length === 9
    ? `${resto.slice(0, 5)}-${resto.slice(5)}`
    : `${resto.slice(0, 4)}-${resto.slice(4)}`;
  return `+55 (${ddd}) ${parteFinal}`;
}

// Converte string BR ("1.234,56" ou "45,90") em number — usado pelo
// MoneyInput ao enviar pra API.
export function parseValorBR(texto) {
  if (typeof texto === "number") return texto;
  const limpo = String(texto).trim().replace(/\./g, "").replace(",", ".");
  const n = parseFloat(limpo);
  return Number.isNaN(n) ? 0 : n;
}
