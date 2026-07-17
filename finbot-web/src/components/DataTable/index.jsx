"use client";

// components/DataTable — tabela genérica usada por todas as telas de CRUD
// da Fase 5. `columns`: [{key, label, render?(row)}]. `acoes(row)` retorna
// os botões de ação da linha (editar/excluir), renderizados pelo chamador
// pra não engessar quais ações cada tela precisa.
import EmptyState from "@/components/EmptyState";
import Loading from "@/components/Loading";
import { TableWrap, Table, Th, Td, Tr, AcoesTd, AcoesFlex } from "./styles";

// `linhaAtenuada(row)`: opcional, marca a linha inteira como "prevista/não
// definitiva" (itálico + opacidade reduzida — ver styles.js) em vez de cada
// tela ter que replicar esse estilo cell a cell. Usado hoje só por
// Lançamentos (custo fixo projetado, ainda não lançado de verdade).
export default function DataTable({ columns, rows, loading, vazio, acoes, linhaAtenuada }) {
  if (loading) return <Loading />;
  if (!rows || rows.length === 0) {
    return <EmptyState titulo={vazio?.titulo || "Nada por aqui ainda"} descricao={vazio?.descricao} acao={vazio?.acao} />;
  }

  return (
    <TableWrap>
      <Table>
        <thead>
          <tr>
            {columns.map((col) => (
              <Th key={col.key}>{col.label}</Th>
            ))}
            {acoes && <Th style={{ textAlign: "right" }}>Ações</Th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
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
