"use client";

import { Overlay, Box, Titulo } from "./styles";

// components/Modal — shell genérico usado por todas as telas de CRUD da
// Fase 5 (editar gasto, editar despesa fixa, etc.). Fecha ao clicar fora,
// mas não ao clicar dentro (stopPropagation) — evita fechar sem querer ao
// interagir com o formulário interno.
//
// `largura` (24/07/2026, pedido do Lucas: popup de detalhe do gráfico
// cortando texto) — sobrescreve o width padrão (min(480px, 90vw)) só onde
// o conteúdo pede mais espaço (listas com valor alinhado à direita). Prop
// opcional pra não mexer em nenhum outro uso existente do Modal.
export default function Modal({ aberto, titulo, onFechar, children, largura }) {
  if (!aberto) return null;
  return (
    <Overlay onClick={onFechar}>
      <Box onClick={(e) => e.stopPropagation()} style={largura ? { width: largura } : undefined}>
        {titulo && <Titulo>{titulo}</Titulo>}
        {children}
      </Box>
    </Overlay>
  );
}
