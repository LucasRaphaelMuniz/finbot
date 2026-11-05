"use client";

import { useId, useRef } from "react";
import { useFocoPreso } from "@/hooks/useFocoPreso";
import { Overlay, Box, Cabecalho, Titulo, FecharBtn } from "./styles";

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
// borbulhe até ele. Checar o alvo não depende de nenhum filho cooperar.
//
// Acessibilidade (auditoria de UX, 05/11/2026) — antes era só uma div
// sobreposta: leitor de tela não sabia que era um diálogo, o foco ficava
// no botão que abriu, Tab andava pela página atrás e Esc não fazia nada.
// Agora: role="dialog" + aria-modal + título ligado por aria-labelledby;
// foco entra no diálogo ao abrir (no elemento marcado com
// data-autofocus, ou no primeiro focável); Tab/Shift+Tab ficam presos
// dentro; Esc fecha; ao fechar, o foco volta pro elemento que abriu.
export default function Modal({ aberto, titulo, onFechar, children, largura }) {
  const idTitulo = useId();
  const boxRef = useRef(null);
  // foco preso, Esc e retorno de foco: hooks/useFocoPreso (compartilhado
  // com components/Painel).
  useFocoPreso(aberto, boxRef, onFechar);

  if (!aberto) return null;
  return (
    <Overlay onClick={(e) => { if (e.target === e.currentTarget) onFechar(); }}>
      <Box
        ref={boxRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titulo ? idTitulo : undefined}
        tabIndex={-1}
        style={largura ? { width: largura } : undefined}
      >
        <Cabecalho>
          {titulo && <Titulo id={idTitulo}>{titulo}</Titulo>}
          <FecharBtn type="button" onClick={onFechar} aria-label="Fechar" data-fechar="1">
            ×
          </FecharBtn>
        </Cabecalho>
        {children}
      </Box>
    </Overlay>
  );
}
