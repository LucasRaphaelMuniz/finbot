// utils/categoriaVisual.js — ícone + cor de cada categoria, derivados do
// NOME (redesign de 05/11/2026; padrão Mobills/Organizze/Copilot de cada
// categoria ter um círculo colorido com ícone).
//
// O banco ainda não guarda ícone/cor por categoria. Enquanto não guarda,
// a regra é: palavra-chave conhecida no nome → ícone + cor fixos; senão,
// ícone genérico e cor escolhida por hash do nome (a mesma categoria sai
// sempre com a mesma cor, em toda tela). Quando existir coluna própria,
// só esta função muda.
import {
  ShoppingCart, Utensils, Car, Fuel, House, HeartPulse, GraduationCap,
  Popcorn, Shirt, Plane, Zap, Wifi, Smartphone, PawPrint, Gift, Receipt,
  Dumbbell, Baby, Wallet, Tag, Sparkles, Landmark, Briefcase,
} from "lucide-react";

// Tons médios: legíveis como ícone/barra sobre fundo claro e escuro. O
// fundo do círculo é o mesmo tom com alpha (ver `fundo`).
export const CORES_CATEGORIA = ["#1d9e75", "#7f77dd", "#d85a30", "#d4537e", "#378add", "#ba7517", "#639922", "#0f9fb0"];

const REGRAS = [
  [/mercad|supermerc|feira|hortifr|padaria|açoug|acoug/, ShoppingCart, 0],
  [/aliment|restaur|lanche|ifood|delivery|comida|refei/, Utensils, 2],
  [/combust|gasolin|posto|etanol/, Fuel, 5],
  [/transp|uber|99|ônibus|onibus|carro|estacion|pedágio|pedagio|ve[ií]culo/, Car, 2],
  [/morad|aluguel|condom|casa|iptu/, House, 1],
  [/sa[uú]de|farm[aá]c|m[eé]dic|rem[eé]dio|plano de sa|dentist|hospital/, HeartPulse, 3],
  [/educa|escola|curso|faculd|livro/, GraduationCap, 4],
  [/lazer|cinema|show|streaming|netflix|spotify|jogo|game|bar\b/, Popcorn, 3],
  [/roupa|vestu|cal[cç]ado|moda/, Shirt, 1],
  [/viage|hotel|passage|turism/, Plane, 4],
  [/luz|energia|copel|eletric/, Zap, 5],
  [/internet|wifi|tv|telefon/, Wifi, 4],
  [/celular|tecnolog|eletr[oô]n/, Smartphone, 7],
  [/pet|cachorr|gato|veterin/, PawPrint, 6],
  [/presente|doa[cç]/, Gift, 3],
  [/academ|esporte|gin[aá]s/, Dumbbell, 6],
  [/filho|beb[eê]|crian/, Baby, 7],
  [/beleza|cabel|est[eé]tic|cosm[eé]t/, Sparkles, 3],
  [/conta|taxa|tarifa|boleto|imposto/, Receipt, 7],
  [/banco|juros|empr[eé]st|financ|cons[oó]rc/, Landmark, 1],
  [/trabalho|escrit|empresa/, Briefcase, 4],
  [/sal[aá]rio|renda|entrada/, Wallet, 6],
];

function hash(texto) {
  let h = 0;
  for (let i = 0; i < texto.length; i += 1) h = (h * 31 + texto.charCodeAt(i)) | 0;
  return Math.abs(h);
}

export function categoriaVisual(nome) {
  const texto = String(nome || "").toLowerCase();
  const regra = REGRAS.find(([re]) => re.test(texto));
  const cor = regra ? CORES_CATEGORIA[regra[2]] : CORES_CATEGORIA[hash(texto) % CORES_CATEGORIA.length];
  return { Icone: regra ? regra[1] : Tag, cor, fundo: `${cor}26`, porRegra: !!regra };
}

export const COR_ENTRADA = "#1f9d5e";
