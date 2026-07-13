"use client";

import { Overlay, Box, Titulo } from "./styles";

// components/Modal — shell genérico usado por todas as telas de CRUD da
// Fase 5 (editar gasto, editar despesa fixa, etc.). Fecha ao clicar fora,
// mas não ao clicar dentro (stopPropagation) — evita fechar sem querer ao
// interagir com o formulário interno.
export default function Modal({ aberto, titulo, onFechar, children }) {
  if (!aberto) return null;
  return (
    <Overlay onClick={onFechar}>
      <Box onClick={(e) => e.stopPropagation()}>
        {titulo && <Titulo>{titulo}</Titulo>}
        {children}
      </Box>
    </Overlay>
  );
}
