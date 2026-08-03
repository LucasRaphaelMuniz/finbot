"use client";

// components/DataTable — tabela genérica usada por todas as telas de CRUD
// da Fase 5. `columns`: [{key, label, render?(row)}]. `acoes(row)` retorna
// os botões de ação da linha (editar/excluir), renderizados pelo chamador
// pra não engessar quais ações cada tela precisa.
import { useMemo, useState } from "react";
import EmptyState from "@/components/EmptyState";
import Loading from "@/components/Loading";
import { TableWrap, Table, Th, Td, Tr, AcoesTd, AcoesFlex } from "./styles";

// `linhaAtenuada(row)`: opcional, marca a linha inteira como "prevista/não
// definitiva" (itálico + opacidade reduzida — ver styles.js) em vez de cada
// tela ter que replicar esse estilo cell a cell. Usado hoje só por
// Lançamentos (custo fixo projetado, ainda não lançado de verdade).
//
// Ordenação por coluna (03/08/2026, pedido do Lucas): clicar no cabeçalho
// ordena asc → desc → volta pra ordem original da API (3º clique). Cada
// coluna pode dar `sortValue(row)` quando o valor pra comparar não é
// `row[col.key]` puro (ex: coluna calculada a partir de `render`, tipo
// "Origem" em Lançamentos) — sem isso, ordena pelo campo cru. `sortable:
// false` tira o cabeçalho do clique (usado nas colunas onde nem faz
// sentido comparar, como "Origem"). Comparação por número quando os dois
// valores são number; senão cai pra string com localeCompare pt-BR (acentos
// ordenam certo). `null`/`undefined` sempre vai pro fim, não pro topo —
// senão gasto sem categoria (categoria_nome null) aparece antes de tudo
// toda vez que alguém ordena por Categoria, o que é o oposto do que se
// espera ao clicar pra ordenar.
export default function DataTable({ columns, rows, loading, vazio, acoes, linhaAtenuada }) {
  const [sort, setSort] = useState({ key: null, dir: "asc" });

  const linhas = useMemo(() => {
    if (!rows || !sort.key) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col) return rows;
    const valorDe = col.sortValue || ((r) => r[col.key]);

    const copia = [...rows].sort((a, b) => {
      const va = valorDe(a);
      const vb = valorDe(b);
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      if (typeof va === "number" && typeof vb === "number") return va - vb;
      return String(va).localeCompare(String(vb), "pt-BR");
    });
    return sort.dir === "desc" ? copia.reverse() : copia;
  }, [rows, sort, columns]);

  function alternarOrdenacao(col) {
    if (col.sortable === false) return;
    setSort((atual) => {
      if (atual.key !== col.key) return { key: col.key, dir: "asc" };
      if (atual.dir === "asc") return { key: col.key, dir: "desc" };
      return { key: null, dir: "asc" };
    });
  }

  if (loading) return <Loading />;
  if (!rows || rows.length === 0) {
    return <EmptyState titulo={vazio?.titulo || "Nada por aqui ainda"} descricao={vazio?.descricao} acao={vazio?.acao} />;
  }

  return (
    <TableWrap>
      <Table>
        <thead>
          <tr>
            {columns.map((col) => {
              const ordenavel = col.sortable !== false;
              return (
                <Th key={col.key} $ordenavel={ordenavel} onClick={() => alternarOrdenacao(col)}>
                  {col.label}
                  {sort.key === col.key ? (sort.dir === "asc" ? " ▲" : " ▼") : ""}
                </Th>
              );
            })}
            {acoes && <Th style={{ textAlign: "right" }}>Ações</Th>}
          </tr>
        </thead>
        <tbody>
          {linhas.map((row) => (
            <Tr key={row.id} $atenuada={linhaAtenuada ? linhaAtenuada(row) : false}>
              {columns.map((col) => (
                <Td key={col.key}>{col.render ? col.render(row) : row[col.key]}</Td>
              ))}
              {acoes && <AcoesTd><AcoesFlex>{acoes(row)}</AcoesFlex></AcoesTd>}
            </Tr>
          ))}
        </tbody>
      </Table>
    </TableWrap>
  );
}
