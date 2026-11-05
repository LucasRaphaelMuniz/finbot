"use client";

// hooks/useFocoPreso.js — comportamento de diálogo compartilhado entre
// components/Modal e components/Painel (antes vivia só dentro do Modal):
// foco entra no diálogo ao abrir (no elemento com data-autofocus, ou no
// primeiro focável que não seja o botão de fechar); Tab/Shift+Tab ficam
// presos dentro; Esc fecha; ao fechar, o foco volta pra quem abriu.
import { useEffect, useRef } from "react";

const FOCAVEIS =
  'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function useFocoPreso(aberto, boxRef, onFechar) {
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
  }, [aberto, boxRef]);
}
