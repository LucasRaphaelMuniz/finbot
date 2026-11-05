// components/Sidebar/itens.js — mapa único da navegação, compartilhado
// entre a Sidebar (desktop + gaveta) e a BottomNav (celular).
//
// Redesign de 05/11/2026 (referências: Copilot, Monarch, Mobills,
// Organizze): os 11 links soltos viraram 3 grupos. As rotas não mudaram —
// só a ordem, os rótulos ("Dashboard" virou "Início") e os ícones.
import {
  House, CalendarCheck, ArrowLeftRight, Repeat, CreditCard, Upload,
  Settings,
} from "lucide-react";

// Abas de Configurações (layout em app/(app)/(ajustes)). As 5 telas
// continuam nas MESMAS URLs: "(ajustes)" é route group do Next, só junta
// as pastas debaixo de um layout com as abas, sem entrar no caminho —
// links antigos (política de privacidade, favoritos) seguem valendo.
export const ABAS_AJUSTES = [
  { href: "/conta", label: "Conta" },
  { href: "/categorias", label: "Categorias" },
  { href: "/formas", label: "Formas de pagamento" },
  { href: "/grupo", label: "Grupo" },
  { href: "/planos", label: "Plano" },
];

export const GRUPOS_NAV = [
  {
    titulo: "Visão geral",
    itens: [
      { href: "/dashboard", label: "Início", Icone: House },
      { href: "/contas", label: "Contas do mês", Icone: CalendarCheck },
    ],
  },
  {
    titulo: "Movimentos",
    itens: [
      { href: "/lancamentos", label: "Lançamentos", Icone: ArrowLeftRight },
      { href: "/fixas", label: "Despesas fixas", Icone: Repeat },
      { href: "/parcelas", label: "Parcelas futuras", Icone: CreditCard },
      { href: "/importacao", label: "Importar extrato", Icone: Upload },
    ],
  },
  {
    // Fase 4 (05/11/2026): Conta, Categorias, Formas, Grupo e Plano viraram
    // abas de uma tela só (app/(app)/(ajustes)). No menu fica 1 item, que
    // continua aceso em qualquer uma das 5 rotas (`ativoEm`).
    titulo: "Ajustes",
    itens: [
      {
        href: "/conta",
        label: "Configurações",
        Icone: Settings,
        ativoEm: ABAS_AJUSTES.map((a) => a.href),
      },
    ],
  },
];

function casa(pathname, href) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

// `alvo`: href (string) ou item do menu ({ href, ativoEm? }).
export function rotaAtiva(pathname, alvo) {
  if (!pathname || !alvo) return false;
  if (typeof alvo === "string") return casa(pathname, alvo);
  return (alvo.ativoEm || [alvo.href]).some((h) => casa(pathname, h));
}
