"use client";

import { useEffect, useId, useRef } from "react";
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
const FOCAVEIS =
  'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export default function Modal({ aberto, titulo, onFechar, children, largura }) {
  const idTitulo = useId();
  const boxRef = useRef(null);
  // onFechar costuma ser uma arrow nova a cada render do pai — guardar em
  // ref evita reinstalar o listener (e re-focar) a cada digitação no form.
  const onFecharRef = useRef(onFechar);
  onFecharRef.current = onFechar;

  useEffect(() => {
    if (!aberto) return undefined;
    const anterior = document.activeElement;
    const box = boxRef.current;

    const alvoInicial =
      box?.querySelector("[data-autofocus]") ||
      [...(box?.querySelectorAll(FOCAVEIS) || [])].find((el) => !el.dataset.fechar) ||
      box;
    // Respeita `autoFocus` de algum campo filho (React já focou no commit).
    if (!box?.contains(document.activeElement)) alvoInicial?.focus();

    function onKeyDown(e) {
      if (e.key === "Escape") {
        e.stopPropagation();
        onFecharRef.current?.();
        return;
      }
      if (e.key !== "Tab" || !box) return;
      const focaveis = [...box.querySelectorAll(FOCAVEIS)].filter((el) => el.offsetParent !== null);
      if (focaveis.length === 0) {
        e.preventDefault();
        return;
      }
      const primeiro = focaveis[0];
      const ultimo = focaveis[focaveis.length - 1];
      if (e.shiftKey && (document.activeElement === primeiro || !box.contains(document.activeElement))) {
        e.preventDefault();
        ultimo.focus();
      } else if (!e.shiftKey && (document.activeElement === ultimo || !box.contains(document.activeElement))) {
        e.preventDefault();
        primeiro.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      if (anterior && typeof anterior.focus === "function" && document.contains(anterior)) {
        anterior.focus();
      }
    };
  }, [aberto]);

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
