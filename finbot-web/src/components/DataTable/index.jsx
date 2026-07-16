"use client";

// components/DataTable — tabela genérica usada por todas as telas de CRUD
// da Fase 5. `columns`: [{key, label, render?(row)}]. `acoes(row)` retorna
// os botões de ação da linha (editar/excluir), renderizados pelo chamador
// pra não engessar quais ações cada tela precisa.
import EmptyState from "@/components/EmptyState";
import Loading from "@/components/Loading";
import { TableWrap, Table, Th, Td, Tr, AcoesTd } from "./styles";

export default function DataTable({ columns, rows, loading, vazio, acoes }) {
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
            <Tr key={row.id}>
              {columns.map((col) => (
                <Td key={col.key}>{col.render ? col.render(row) : row[col.key]}</Td>
              ))}
              {acoes && <AcoesTd>{acoes(row)}</AcoesTd>}
            </Tr>
          ))}
        </tbody>
      </Table>
    </TableWrap>
  );
}
