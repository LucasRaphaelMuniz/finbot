"use client";

// components/CategoriaSelect — busca GET /api/categorias e renderiza um
// <select>. Categoria global (grupo_id null) marcada como "(padrão)" —
// mesma distinção que a API expõe (ver routes/categorias.py).
import { useApi } from "@/hooks/useApi";
import { Select } from "./styles";

// apenasAtivas=true por padrão: some com categoria desativada na hora de
// ESCOLHER categoria pra um gasto novo/editado (gasto, fixa, importação).
// A tela Categorias e o filtro de lançamentos passam apenasAtivas={false}
// de propósito — lá a categoria precisa continuar aparecendo mesmo
// desativada (senão fica impossível reativar ou filtrar gastos antigos
// que já usam ela).
export default function CategoriaSelect({ value, onChange, incluirTodas = false, apenasAtivas = true, id }) {
  const { dados, loading } = useApi("/categorias");
  const todos = dados?.itens || [];
  // `|| c.id === value` é de propósito: sem isso, editar um gasto antigo
  // que usa uma categoria já desativada faria o <select> perder o valor
  // selecionado (a option some da lista) e trocar a categoria do gasto sem
  // a pessoa pedir. Só esconde inativa que NÃO é a que já está selecionada.
  const itens = apenasAtivas ? todos.filter((c) => c.ativo || c.id === value) : todos;

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
