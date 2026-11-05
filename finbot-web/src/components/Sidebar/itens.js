// components/Sidebar/itens.js — mapa único da navegação, compartilhado
// entre a Sidebar (desktop + gaveta) e a BottomNav (celular).
//
// Redesign de 05/11/2026 (referências: Copilot, Monarch, Mobills,
// Organizze): os 11 links soltos viraram 3 grupos. As rotas não mudaram —
// só a ordem, os rótulos ("Dashboard" virou "Início") e os ícones.
import {
  House, CalendarCheck, ArrowLeftRight, Repeat, CreditCard, Upload,
  Tags, Wallet, Users, Sparkles, UserCog,
} from "lucide-react";

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
    titulo: "Ajustes",
    itens: [
      { href: "/categorias", label: "Categorias", Icone: Tags },
      { href: "/formas", label: "Formas de pagamento", Icone: Wallet },
      { href: "/grupo", label: "Grupo", Icone: Users },
      { href: "/planos", label: "Planos", Icone: Sparkles },
      { href: "/conta", label: "Conta", Icone: UserCog },
    ],
  },
];

export function rotaAtiva(pathname, href) {
  return !!pathname && (pathname === href || pathname.startsWith(`${href}/`));
}
