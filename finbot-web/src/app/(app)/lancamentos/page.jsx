"use client";

// app/(app)/lancamentos/page.jsx — CRUD de gastos e entradas (Fase 5.1 do
// PLANO_EXECUCAO.md). Abas trocam o recurso (gastos x entradas) inteiro,
// não só um filtro — são listagens/formulários genuinamente diferentes
// (gasto tem categoria+forma+parcelamento; entrada não tem nenhum dos dois).
import { useEffect, useMemo, useState } from "react";
import { useApi } from "@/hooks/useApi";
import api from "@/services/api";
import { brl, formatarDataBR } from "@/utils/format";
import DataTable from "@/components/DataTable";
import { AcaoBtn } from "@/components/DataTable/styles";
import Modal from "@/components/Modal";
import ConfirmDialog from "@/components/ConfirmDialog";
import MesPicker from "@/components/MesPicker";
import CategoriaSelect from "@/components/CategoriaSelect";
import FormaSelect from "@/components/FormaSelect";
import MoneyInput from "@/components/MoneyInput";
import Toast from "@/components/Toast";
import { EVENTO_LANCAMENTO_SALVO } from "@/components/NovoLancamento";
import { Field } from "@/components/AuthCard/styles";
import {
  Header, Abas, Aba, Filtros, FiltroCampo, Form,
  Erro, SalvarBtn,
} from "./styles";

function mesAtualISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export default function LancamentosPage() {
  const [aba, setAba] = useState("gastos"); // gastos | entradas
  const [mes, setMes] = useState(mesAtualISO());
  const [filtroCategoria, setFiltroCategoria] = useState(null);
  const [filtroForma, setFiltroForma] = useState(null);
  const [toast, setToast] = useState(null);

  const [modalEditar, setModalEditar] = useState(null); // gasto/entrada sendo editado, ou null
  const [modalExcluir, setModalExcluir] = useState(null); // gasto/entrada a excluir, ou null

  const urlGastos = useMemo(() => {
    const params = new URLSearchParams({ mes });
    if (filtroCategoria) params.set("categoria", filtroCategoria);
    if (filtroForma) params.set("forma", filtroForma);
    return `/gastos?${params.toString()}`;
  }, [mes, filtroCategoria, filtroForma]);

  const { dados: dadosGastos, loading: loadingGastos, refetch: refetchGastos } = useApi(
    urlGastos, { skip: aba !== "gastos" }
  );
  const { dados: dadosEntradas, loading: loadingEntradas, refetch: refetchEntradas } = useApi(
    "/entradas", { skip: aba !== "entradas" }
  );

  function avisar(mensagem, tipo = "sucesso") {
    setToast({ mensagem, tipo });
    setTimeout(() => setToast(null), 3000);
  }

  function refetchAtual() {
    if (aba === "gastos") refetchGastos();
    else refetchEntradas();
  }

  // "Novo lançamento" agora é global (components/NovoLancamento, montado
  // no layout) — a lista recarrega quando ele avisa que salvou algo.
  useEffect(() => {
    function onSalvo() {
      if (aba === "gastos") refetchGastos();
      else refetchEntradas();
    }
    window.addEventListener(EVENTO_LANCAMENTO_SALVO, onSalvo);
    return () => window.removeEventListener(EVENTO_LANCAMENTO_SALVO, onSalvo);
  }, [aba, refetchGastos, refetchEntradas]);

  async function handleExcluir(escopo = "unico") {
    try {
      if (aba === "gastos") {
        await api.delete(`/gastos/${modalExcluir.id}${escopo === "compra" ? "?escopo=compra" : ""}`);
      } else {
        await api.delete(`/entradas/${modalExcluir.id}`);
      }
      avisar("Removido com sucesso.");
      setModalExcluir(null);
      refetchAtual();
    } catch (err) {
      avisar(err?.response?.data?.mensagem || "Não foi possível remover.", "erro");
    }
  }

  const colunasGastos = [
    { key: "data", label: "Data", render: (r) => formatarDataBR(r.data) },
    { key: "descricao", label: "Descrição" },
    { key: "categoria_nome", label: "Categoria" },
    { key: "forma_nome", label: "Forma" },
    { key: "membro_nome", label: "Membro" },
    {
      key: "parcela",
      label: "Origem",
      sortable: false,
      render: (r) =>
        r.projetado ? "fixa (previsto)" :
        r.compra_parcelada_id ? `parcela ${r.parcela_num}/${r.total_parcelas || "?"}` :
        r.despesa_fixa_id ? "fixa" : "avulso",
    },
    { key: "valor", label: "Valor", numerico: true, render: (r) => brl(r.valor) },
  ];

  const colunasEntradas = [
    { key: "data", label: "Data", render: (r) => formatarDataBR(r.data) },
    { key: "descricao", label: "Descrição" },
    { key: "valor", label: "Valor", numerico: true, render: (r) => brl(r.valor) },
  ];

  const linhas = aba === "gastos" ? dadosGastos?.itens : dadosEntradas?.itens;
  const carregando = aba === "gastos" ? loadingGastos : loadingEntradas;

  return (
    <div>
      <Header>
        <h1 style={{ fontSize: 20 }}>Lançamentos</h1>
      </Header>

      {/* aria-pressed: as abas são um par de botões de alternância — sem
          isso, leitor de tela não sabia qual dos dois estava ativo. */}
      <Abas>
        <Aba type="button" aria-pressed={aba === "gastos"} $ativa={aba === "gastos"} onClick={() => setAba("gastos")}>Gastos</Aba>
        <Aba type="button" aria-pressed={aba === "entradas"} $ativa={aba === "entradas"} onClick={() => setAba("entradas")}>Entradas</Aba>
      </Abas>

      {/* Filtros lado a lado com label visível (antes: 2 selects de largura
          total empilhados, sem label nenhum). */}
      <Filtros>
        <MesPicker value={mes} onChange={setMes} />
        {aba === "gastos" && (
          <>
            <FiltroCampo>
              <label htmlFor="filtro-categoria">Categoria</label>
              <CategoriaSelect id="filtro-categoria" value={filtroCategoria} onChange={setFiltroCategoria} incluirTodas apenasAtivas={false} />
            </FiltroCampo>
            <FiltroCampo>
              <label htmlFor="filtro-forma">Forma de pagamento</label>
              <FormaSelect id="filtro-forma" value={filtroForma} onChange={setFiltroForma} incluirTodas />
            </FiltroCampo>
          </>
        )}
      </Filtros>

      <DataTable
        columns={aba === "gastos" ? colunasGastos : colunasEntradas}
        rows={linhas}
        loading={carregando}
        vazio={{
          titulo: aba === "gastos" ? "Nenhum gasto neste mês" : "Nenhuma entrada registrada",
          descricao: "Registre pelo botão \"Novo lançamento\" ou mande uma mensagem pro bot no WhatsApp.",
        }}
        linhaAtenuada={(row) => !!row.projetado}
        acoes={(row) =>
          // Linha projetada (custo fixo previsto, futuro — ver
          // services/gastos.py::projetar_despesas_fixas) não tem um
          // /api/gastos/:id real por trás; "id" é string sintética de key.
          // Sem botão Confirmar (removido 18/07/2026): o lançamento é 100%
          // automático — catch-up no lançador + execução na subida do
          // processo. A linha vira gasto real sozinha no dia.
          row.projetado ? null : (
            <>
              <AcaoBtn onClick={() => setModalEditar(row)}>Editar</AcaoBtn>
              <AcaoBtn $perigo onClick={() => setModalExcluir(row)}>Excluir</AcaoBtn>
            </>
          )
        }
      />

      {modalEditar && (
        <ModalEditarLancamento
          tipo={aba}
          item={modalEditar}
          onFechar={() => setModalEditar(null)}
          onSalvo={() => {
            setModalEditar(null);
            avisar("Alterações salvas.");
            refetchAtual();
          }}
          onErro={(msg) => avisar(msg, "erro")}
        />
      )}

      {modalExcluir && modalExcluir.compra_parcelada_id ? (
        <Modal aberto titulo="Excluir parcela" onFechar={() => setModalExcluir(null)}>
          <p>
            Esse gasto é a parcela {modalExcluir.parcela_num}/{modalExcluir.total_parcelas || "?"} de uma
            compra parcelada. Excluir só essa parcela ou a compra inteira (todas as parcelas)?
          </p>
          <div style={{ display: "flex", gap: 8, marginTop: 16, justifyContent: "flex-end" }}>
            <button onClick={() => setModalExcluir(null)} data-autofocus>Cancelar</button>
            <button onClick={() => handleExcluir("unico")}>Só esta parcela</button>
            <button onClick={() => handleExcluir("compra")}>Compra inteira</button>
          </div>
        </Modal>
      ) : (
        <ConfirmDialog
          aberto={!!modalExcluir}
          titulo="Excluir lançamento"
          textoConfirmar="Excluir lançamento"
          mensagem={
            // Lançamento de custo fixo (inclusive o antecipado do mês
            // seguinte): a exclusão grava supressão no backend (migração
            // 026) — não volta nem como real nem como "previsto" — mas a
            // fixa segue lançando nos meses seguintes. Vale avisar, senão
            // parece que excluiu o custo fixo inteiro.
            modalExcluir?.despesa_fixa_id
              ? `"${modalExcluir.descricao || "Este lançamento"}" vem de um custo fixo. Excluir remove só este mês (não será relançado); o custo fixo continua ativo nos próximos meses.`
              : `Excluir "${modalExcluir?.descricao || "lançamento sem descrição"}" de ${brl(modalExcluir?.valor)}? Não dá pra desfazer.`
          }
          onConfirmar={() => handleExcluir("unico")}
          onCancelar={() => setModalExcluir(null)}
        />
      )}

      <Toast mensagem={toast?.mensagem} tipo={toast?.tipo} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Modal: editar lançamento existente
// ---------------------------------------------------------------------------

function ModalEditarLancamento({ tipo, item, onFechar, onSalvo, onErro }) {
  const [valor, setValor] = useState(item.valor);
  const [descricao, setDescricao] = useState(item.descricao || "");
  const [categoriaId, setCategoriaId] = useState(item.categoria_id);
  const [formaId, setFormaId] = useState(item.forma_pagamento_id);
  // Data editável (03/08/2026, pedido do Lucas) — só gastos: entrada não
  // expõe isso hoje (services/entradas.py::atualizar_entrada não aceita
  // `data`, fora de escopo deste pedido). `item.data` vem "YYYY-MM-DD..."
  // (às vezes com hora) — <input type="date"> só aceita os 10 primeiros
  // caracteres.
  const [data, setData] = useState(item.data ? item.data.slice(0, 10) : "");
  // Recorrência (entradas): inicia do estado ATUAL do modelo
  // (recorrente_ativa vem do LEFT JOIN com entradas_fixas — entrada_fixa_id
  // sozinho ficaria marcado pra sempre mesmo depois de desativar).
  const [recorrente, setRecorrente] = useState(!!item.recorrente_ativa);
  const [diaLancamento, setDiaLancamento] = useState(
    item.recorrente_dia || (item.data ? new Date(item.data).getDate() : new Date().getDate())
  );
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setErro("");
    if (!valor || valor <= 0) {
      setErro("Informe um valor maior que zero.");
      return;
    }
    setEnviando(true);
    try {
      if (tipo === "entradas") {
        await api.put(`/entradas/${item.id}`, {
          valor, descricao,
          // Só envia se mudou algo de recorrência — evita mexer no modelo
          // quando a pessoa só corrigiu o valor de uma entrada avulsa.
          ...(recorrente !== !!item.recorrente_ativa || (recorrente && diaLancamento !== item.recorrente_dia)
            ? { recorrente, dia_lancamento: diaLancamento }
            : {}),
        });
      } else {
        await api.put(`/gastos/${item.id}`, {
          valor, descricao, categoria_id: categoriaId, forma_pagamento_id: formaId,
          // Muda a competência junto no backend (services/gastos.py::
          // atualizar_gasto) — sem enviar "data" de propósito quando não
          // mudou nada, pra não recalcular a competência à toa.
          ...(data && data !== item.data?.slice(0, 10) ? { data } : {}),
        });
      }
      onSalvo();
    } catch (err) {
      onErro(err?.response?.data?.mensagem || "Não foi possível salvar.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Modal aberto titulo="Editar lançamento" onFechar={onFechar}>
      <Form onSubmit={handleSubmit}>
        <Field>
          <label htmlFor="valor-edit">Valor</label>
          <MoneyInput id="valor-edit" value={valor} onChange={setValor} />
        </Field>
        <Field>
          <label htmlFor="descricao-edit">Descrição</label>
          <input id="descricao-edit" value={descricao} onChange={(e) => setDescricao(e.target.value)} />
        </Field>
        {tipo === "entradas" && (
          <>
            <Field>
              <label>
                <input type="checkbox" checked={recorrente} onChange={(e) => setRecorrente(e.target.checked)} />
                {" "}Recorrente/Fixo (cai todo mês — ex: salário)
              </label>
              {!!item.recorrente_ativa && !recorrente && (
                <small style={{ opacity: 0.7 }}>
                  Desmarcar para de lançar nos próximos meses — as entradas já
                  lançadas não são apagadas.
                </small>
              )}
            </Field>
            {recorrente && (
              <Field>
                <label htmlFor="dia-entrada-edit">Dia do mês em que cai</label>
                <input
                  id="dia-entrada-edit" type="number" min={1} max={31}
                  value={diaLancamento} onChange={(e) => setDiaLancamento(Number(e.target.value))}
                />
              </Field>
            )}
          </>
        )}
        {tipo === "gastos" && (
          <>
            <Field>
              <label htmlFor="data-edit">Data</label>
              <input id="data-edit" type="date" value={data} onChange={(e) => setData(e.target.value)} />
            </Field>
            <Field>
              <label htmlFor="categoria-edit">Categoria</label>
              <CategoriaSelect id="categoria-edit" value={categoriaId} onChange={setCategoriaId} />
            </Field>
            <Field>
              <label htmlFor="forma-edit">Forma de pagamento</label>
              <FormaSelect id="forma-edit" value={formaId} onChange={setFormaId} />
            </Field>
          </>
        )}
        {erro && <Erro>{erro}</Erro>}
        <SalvarBtn type="submit" disabled={enviando}>
          {enviando ? "Salvando..." : "Salvar alterações"}
        </SalvarBtn>
      </Form>
    </Modal>
  );
}
