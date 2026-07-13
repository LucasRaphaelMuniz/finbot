"use client";

// components/CategoriaSelect — busca GET /api/categorias e renderiza um
// <select>. Categoria global (grupo_id null) marcada como "(padrão)" —
// mesma distinção que a API expõe (ver routes/categorias.py).
import { useApi } from "@/hooks/useApi";
import { Select } from "./styles";

export default function CategoriaSelect({ value, onChange, incluirTodas = false, id }) {
  const { dados, loading } = useApi("/categorias");
  const itens = dados?.itens || [];

  return (
    <Select
      id={id}
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
      disabled={loading}
    >
      {incluirTodas && <option value="">Todas as categorias</option>}
      {!incluirTodas && <option value="" disabled>Selecione...</option>}
      {itens.map((c) => (
        <option key={c.id} value={c.id}>
          {c.nome}{c.grupo_id == null ? " (padrão)" : ""}
        </option>
      ))}
    </Select>
  );
}
