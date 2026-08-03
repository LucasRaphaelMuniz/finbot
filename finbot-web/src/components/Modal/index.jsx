"use client";

import { Overlay, Box, Titulo } from "./styles";

// components/Modal — shell genérico usado por todas as telas de CRUD da
// Fase 5 (editar gasto, editar despesa fixa, etc.). Fecha ao clicar fora,
// mas não ao clicar dentro.
//
// `largura` (24/07/2026, pedido do Lucas: popup de detalhe do gráfico
// cortando texto) — sobrescreve o width padrão (min(480px, 90vw)) só onde
// o conteúdo pede mais espaço (listas com valor alinhado à direita). Prop
// opcional pra não mexer em nenhum outro uso existente do Modal.
//
// Fechamento por CLIQUE NO ALVO, não por stopPropagation no filho
// (03/08/2026, investigando bug do Lucas: modal de editar lançamento
// fechando sozinho). `e.target === e.currentTarget` só é verdadeiro quando
// o clique aconteceu no próprio Overlay (fundo escuro) — não em nada que
// borbulhe até ele. A versão anterior dependia de `Box` chamar
// `stopPropagation()` em TODO clique interno; qualquer coisa dentro do
// formulário que não propague direito (ex: um popup nativo do browser,
// como o calendário do <input type="date">, que não faz parte da árvore
// React) furava essa defesa e fechava o modal à toa. Checar o alvo não
// depende de nenhum filho cooperar.
export default function Modal({ aberto, titulo, onFechar, children, largura }) {
  if (!aberto) return null;
  return (
    <Overlay onClick={(e) => { if (e.target === e.currentTarget) onFechar(); }}>
      <Box style={largura ? { width: largura } : undefined}>
        {titulo && <Titulo>{titulo}</Titulo>}
        {children}
      </Box>
    </Overlay>
  );
}
