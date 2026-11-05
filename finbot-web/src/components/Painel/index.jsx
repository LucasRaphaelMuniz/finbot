"use client";

// components/Painel — painel lateral (slide-over) que entra pela direita.
// Redesign de Lançamentos (05/11/2026): editar um lançamento é uma tarefa
// curta e a lista atrás continua sendo o contexto — o painel deixa a lista
// visível ao lado no desktop em vez de tapar tudo com um modal no meio da
// tela. No celular ocupa a largura inteira.
//
// Mesmo contrato de acessibilidade do Modal (hooks/useFocoPreso):
// role="dialog", foco preso, Esc fecha, foco volta pra linha que abriu.
// `rodape` fica fixo no fim (ações), o conteúdo rola por cima.
import { useId, useRef } from "react";
import { X } from "lucide-react";
import { useFocoPreso } from "@/hooks/useFocoPreso";
import { Fundo, Caixa, Topo, Titulo, Subtitulo, FecharBtn, Corpo, Rodape } from "./styles";

export default function Painel({ aberto, titulo, subtitulo, onFechar, children, rodape }) {
  const idTitulo = useId();
  const caixaRef = useRef(null);
  useFocoPreso(aberto, caixaRef, onFechar);

  if (!aberto) return null;
  return (
    <Fundo onClick={(e) => { if (e.target === e.currentTarget) onFechar(); }}>
      <Caixa ref={caixaRef} role="dialog" aria-modal="true" aria-labelledby={idTitulo} tabIndex={-1}>
        <Topo>
          <div style={{ minWidth: 0 }}>
            <Titulo id={idTitulo}>{titulo}</Titulo>
            {subtitulo && <Subtitulo>{subtitulo}</Subtitulo>}
          </div>
          <FecharBtn type="button" onClick={onFechar} aria-label="Fechar painel" data-fechar="1">
            <X size={18} aria-hidden="true" />
          </FecharBtn>
        </Topo>
        <Corpo>{children}</Corpo>
        {rodape && <Rodape>{rodape}</Rodape>}
      </Caixa>
    </Fundo>
  );
}
