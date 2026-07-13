"use client";

// components/FormaSelect — mesmo padrão de CategoriaSelect, pra
// formas_pagamento (GET /api/formas).
import { useApi } from "@/hooks/useApi";
import { Select } from "@/components/CategoriaSelect/styles";

export default function FormaSelect({ value, onChange, incluirTodas = false, id }) {
  const { dados, loading } = useApi("/formas");
  const itens = dados?.itens || [];

  return (
    <Select
      id={id}
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
      disabled={loading}
    >
      {incluirTodas && <option value="">Todas as formas</option>}
      {!incluirTodas && <option value="" disabled>Selecione...</option>}
      {itens.map((f) => (
        <option key={f.id} value={f.id}>{f.nome}</option>
      ))}
    </Select>
  );
}
