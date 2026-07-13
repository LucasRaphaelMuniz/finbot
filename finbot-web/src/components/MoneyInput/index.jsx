"use client";

// components/MoneyInput — input controlado em formato BR (vírgula decimal).
// Guarda o valor como number no estado do pai (`value`/`onChange` sempre
// number), mas exibe/edita como texto BR — enquanto focado, mostra o que
// a pessoa está digitando sem reformatar a cada tecla (senão o cursor pula
// de lugar); ao perder o foco, reformata pro padrão "1.234,56".
import { useEffect, useState } from "react";
import { Input } from "./styles";
import { parseValorBR } from "@/utils/format";

function formatarExibicao(valor) {
  const n = Number(valor) || 0;
  return n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function MoneyInput({ id, value, onChange, placeholder = "0,00", ...rest }) {
  const [texto, setTexto] = useState(value != null ? formatarExibicao(value) : "");
  const [focado, setFocado] = useState(false);

  useEffect(() => {
    if (!focado) setTexto(value != null ? formatarExibicao(value) : "");
  }, [value, focado]);

  return (
    <Input
      id={id}
      inputMode="decimal"
      placeholder={placeholder}
      value={texto}
      onFocus={() => setFocado(true)}
      onChange={(e) => {
        // Só deixa passar dígitos, vírgula e ponto — evita letra solta
        // quebrar o parse depois.
        const limpo = e.target.value.replace(/[^\d.,]/g, "");
        setTexto(limpo);
        onChange(parseValorBR(limpo));
      }}
      onBlur={() => {
        setFocado(false);
        setTexto(value != null ? formatarExibicao(value) : "");
      }}
      {...rest}
    />
  );
}
