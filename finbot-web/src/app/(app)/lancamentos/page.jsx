"use client";

// app/(app)/lancamentos/page.jsx — CRUD de gastos e entradas (Fase 5.1 do
// PLANO_EXECUCAO.md). Abas trocam o recurso (gastos x entradas) inteiro,
// não só um filtro — são listagens/formulários genuinamente diferentes
// (gasto tem categoria+forma+parcelamento; entrada não tem nenhum dos dois).
import { useMemo, useState } from "react";
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
import {
  Header, Abas, Aba, Filtros, BotaoNovo, Form, Field,
  ToggleTipo, ToggleBtn, Erro, SalvarBtn,
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

  const [modalNovo, setModalNovo] = useState(false);
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
      render: (r) =>
        r.compra_parcelada_id ? `parcela ${r.parcela_num}/${r.total_parcelas || "?"}` :
        r.despesa_fixa_id ? "fixa" : "avulso",
    },
    { key: "valor", label: "Valor", render: (r) => brl(r.valor) },
  ];

  const colunasEntradas = [
    { key: "data", label: "Data", render: (r) => formatarDataBR(r.data) },
    { key: "descricao", label: "Descrição" },
    { key: "valor", label: "Valor", render: (r) => brl(r.valor) },
  ];

  const linhas = aba === "gastos" ? dadosGastos?.itens : dadosEntradas?.itens;
  const carregando = aba === "gastos" ? loadingGastos : loadingEntradas;

  return (
    <div>
      <Header>
        <Abas>
          <Aba $ativa={aba === "gastos"} onClick={() => setAba("gastos")}>Gastos</Aba>
          <Aba $ativa={aba === "entradas"} onClick={() => setAba("entradas")}>Entradas</Aba>
        </Abas>
        <BotaoNovo onClick={() => setModalNovo(true)}>+ Novo lançamento</BotaoNovo>
      </Header>

      <Filtros>
        <MesPicker value={mes} onChange={setMes} />
        {aba === "gastos" && (
          <>
            <CategoriaSelect value={filtroCategoria} onChange={setFiltroCategoria} incluirTodas apenasAtivas={false} />
            <FormaSelect value={filtroForma} onChange={setFiltroForma} incluirTodas />
          </>
        )}
      </Filtros>

      <DataTable
        columns={aba === "gastos" ? colunasGastos : colunasEntradas}
        rows={linhas}
        loading={carregando}
        vazio={{
          titulo: aba === "gastos" ? "Nenhum gasto neste mês" : "Nenhuma entrada registrada",
          descricao: "Use o botão \"Novo lançamento\" para adicionar.",
        }}
        acoes={(row) => (
          <>
            <AcaoBtn onClick={() => setModalEditar(row)}>Editar</AcaoBtn>
            <AcaoBtn $perigo onClick={() => setModalExcluir(row)}>Excluir</AcaoBtn>
          </>
        )}
      />

      <ModalNovoLancamento
        aberto={modalNovo}
        onFechar={() => setModalNovo(false)}
        onSalvo={() => {
          setModalNovo(false);
          avisar("Lançamento registrado!");
          refetchAtual();
        }}
        onErro={(msg) => avisar(msg, "erro")}
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
            <button onClick={() => setModalExcluir(null)}>Cancelar</button>
            <button onClick={() => handleExcluir("unico")}>Só esta parcela</button>
            <button onClick={() => handleExcluir("compra")}>Compra inteira</button>
          </div>
        </Modal>
      ) : (
        <ConfirmDialog
          aberto={!!modalExcluir}
          titulo="Confirmar exclusão"
          mensagem="Tem certeza que deseja excluir este lançamento?"
          onConfirmar={() => handleExcluir("unico")}
          onCancelar={() => setModalExcluir(null)}
        />
      )}

      <Toast mensagem={toast?.mensagem} tipo={toast?.tipo} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Modal: novo lançamento (toggle gasto/entrada)
// ---------------------------------------------------------------------------

function ModalNovoLancamento({ aberto, onFechar, onSalvo, onErro }) {
  const [tipo, setTipo] = useState("gasto"); // gasto | entrada
  const [valor, setValor] = useState(0);
  const [descricao, setDescricao] = useState("");
  const [categoriaId, setCategoriaId] = useState(null);
  const [formaId, setFormaId] = useState(null);
  const [parcelado, setParcelado] = useState(false);
  const [parcelas, setParcelas] = useState(2);
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  function resetar() {
    setTipo("gasto");
    setValor(0);
    setDescricao("");
    setCategoriaId(null);
    setFormaId(null);
    setParcelado(false);
    setParcelas(2);
    setErro("");
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setErro("");

    if (!valor || valor <= 0) {
      setErro("Informe um valor maior que zero.");
      return;
    }

    setEnviando(true);
    try {
      if (tipo === "entrada") {
        await api.post("/entradas", { valor, descricao });
      } else {
        if (!categoriaId || !formaId) {
          setErro("Selecione categoria e forma de pagamento.");
          setEnviando(false);
          return;
        }
        // Parcelamento ainda não tem endpoint dedicado na API web (só o bot
        // cria compra parcelada, via services/parcelamento.py) — a Fase 4.3
        // não previu isso no contrato REST. Registro parcelado pela web fica
        // pendente; aqui só bloqueio com uma mensagem clara em vez de
        // fingir que funciona.
        if (parcelado) {
          setErro("Lançamento parcelado ainda não é suportado pela web — use o WhatsApp por enquanto.");
          setEnviando(false);
          return;
        }
        await api.post("/gastos", { valor, descricao, categoria_id: categoriaId, forma_pagamento_id: formaId });
      }
      resetar();
      onSalvo();
    } catch (err) {
      onErro(err?.response?.data?.mensagem || "Não foi possível salvar.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Modal aberto={aberto} titulo="Novo lançamento" onFechar={() => { resetar(); onFechar(); }}>
      <Form onSubmit={handleSubmit}>
        <ToggleTipo>
          <ToggleBtn type="button" $ativo={tipo === "gasto"} onClick={() => setTipo("gasto")}>
            💸 Gasto
          </ToggleBtn>
          <ToggleBtn type="button" $ativo={tipo === "entrada"} onClick={() => setTipo("entrada")}>
            📈 Entrada
          </ToggleBtn>
        </ToggleTipo>

        <Field>
          <label htmlFor="valor">Valor</label>
          <MoneyInput id="valor" value={valor} onChange={setValor} />
        </Field>

        <Field>
          <label htmlFor="descricao">Descrição</label>
          <input id="descricao" value={descricao} onChange={(e) => setDescricao(e.target.value)} />
        </Field>

        {tipo === "gasto" && (
          <>
            <Field>
              <label htmlFor="categoria">Categoria</label>
              <CategoriaSelect id="categoria" value={categoriaId} onChange={setCategoriaId} />
            </Field>
            <Field>
              <label htmlFor="forma">Forma de pagamento</label>
              <FormaSelect id="forma" value={formaId} onChange={setFormaId} />
            </Field>
            <Field>
              <label>
                <input type="checkbox" checked={parcelado} onChange={(e) => setParcelado(e.target.checked)} />
                {" "}Compra parcelada
              </label>
            </Field>
            {parcelado && (
              <Field>
                <label htmlFor="parcelas">Número de parcelas</label>
                <input
                  id="parcelas" type="number" min={2} max={48}
                  value={parcelas} onChange={(e) => setParcelas(Number(e.target.value))}
                />
              </Field>
            )}
          </>
        )}

        {erro && <Erro>{erro}</Erro>}
        <SalvarBtn type="submit" disabled={enviando}>
          {enviando ? "Salvando..." : "Salvar"}
        </SalvarBtn>
      </Form>
    </Modal>
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
        await api.put(`/entradas/${item.id}`, { valor, descricao });
      } else {
        await api.put(`/gastos/${item.id}`, {
          valor, descricao, categoria_id: categoriaId, forma_pagamento_id: formaId,
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
        {tipo === "gastos" && (
          <>
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
