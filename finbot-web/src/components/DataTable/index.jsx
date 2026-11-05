"use client";

// components/DataTable — tabela genérica usada por todas as telas de CRUD
// da Fase 5. `columns`: [{key, label, render?(row), numerico?}] —
// `numerico` alinha a coluna à direita com algarismos tabulares (valores
// em R$ comparáveis de relance). `acoes(row)` retorna
// os botões de ação da linha (editar/excluir), renderizados pelo chamador
// pra não engessar quais ações cada tela precisa.
import { useMemo, useState } from "react";
import EmptyState from "@/components/EmptyState";
import { TableWrap, Table, Th, Td, Tr, AcoesTd, AcoesFlex, OrdenarBtn, Skeleton } from "./styles";

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

  // Skeleton com a forma da tabela (auditoria de UX) em vez de spinner
  // solto: a página já mostra onde os dados vão aparecer enquanto a API
  // responde. aria-busy + rótulo pra leitor de tela.
  if (loading) {
    return (
      <TableWrap aria-busy="true" aria-label="Carregando">
        <Table>
          <tbody>
            {[0, 1, 2, 3, 4].map((i) => (
              <Tr key={i}>
                {columns.map((col) => (
                  <Td key={col.key} data-label={col.label}>
                    <Skeleton />
                  </Td>
                ))}
              </Tr>
            ))}
          </tbody>
        </Table>
      </TableWrap>
    );
  }
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
              const ativa = sort.key === col.key;
              return (
                <Th
                  key={col.key}
                  $numerico={col.numerico}
                  aria-sort={ativa ? (sort.dir === "asc" ? "ascending" : "descending") : undefined}
                >
                  {/* Botão dentro do <th> (antes: onClick no próprio th) —
                      ordenar passa a funcionar por Tab/Enter, não só mouse. */}
                  {ordenavel ? (
                    <OrdenarBtn type="button" onClick={() => alternarOrdenacao(col)}>
                      {col.label}
                      {ativa ? (sort.dir === "asc" ? " ▲" : " ▼") : ""}
                    </OrdenarBtn>
                  ) : (
                    col.label
                  )}
                </Th>
              );
            })}
            {acoes && <Th style={{ textAlign: "right" }}>Ações</Th>}
          </tr>
        </thead>
        <tbody>
          {linhas.map((row) => (
            <Tr key={row.id} $atenuada={linhaAtenuada ? linhaAtenuada(row) : false}>
              {/* data-label alimenta o layout em card do mobile (styles.js):
                  abaixo de 640px cada célula vira "Rótulo .... valor". */}
              {columns.map((col) => (
                <Td key={col.key} $numerico={col.numerico} data-label={col.label}>
                  {col.render ? col.render(row) : row[col.key]}
                </Td>
              ))}
              {acoes && <AcoesTd><AcoesFlex>{acoes(row)}</AcoesFlex></AcoesTd>}
            </Tr>
          ))}
        </tbody>
      </Table>
    </TableWrap>
  );
}
