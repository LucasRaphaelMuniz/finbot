"use client";

// app/(app)/fixas/page.jsx — CRUD de despesas fixas. Não tem seção própria
// numerada no §5 do PLANO_EXECUCAO.md (o plano lista a pasta em 4.1 mas
// detalha só 5.1-5.6, sem "5.x /fixas" explícito) — construída aqui pra
// fechar o gap, já que o backend (routes/fixas.py, Fase 4.3) já suporta.
// "Remover" é soft-delete (ativa=FALSE) — mesma razão do bot: gastos já
// lançados referenciam despesa_fixa_id sem cascade.
import { useState } from "react";
import { useApi } from "@/hooks/useApi";
import api from "@/services/api";
import { brl } from "@/utils/format";
import DataTable from "@/components/DataTable";
import { AcaoBtn } from "@/components/DataTable/styles";
import Modal from "@/components/Modal";
import ConfirmDialog from "@/components/ConfirmDialog";
import MoneyInput from "@/components/MoneyInput";
import CategoriaSelect from "@/components/CategoriaSelect";
import FormaSelect from "@/components/FormaSelect";
import Toast from "@/components/Toast";
import { Field, Botao as SalvarBtn } from "@/components/AuthCard/styles";

export default function FixasPage() {
  const { dados, loading, refetch } = useApi("/fixas");
  const [toast, setToast] = useState(null);
  const [modalFixa, setModalFixa] = useState(undefined);
  const [removendo, setRemovendo] = useState(null);

  function avisar(mensagem, tipo = "sucesso") {
    setToast({ mensagem, tipo });
    setTimeout(() => setToast(null), 3000);
  }

  async function remover() {
    try {
      await api.delete(`/fixas/${removendo.id}`);
      avisar("Despesa fixa removida (não lança mais).");
      setRemovendo(null);
      refetch();
    } catch (err) {
      avisar(err?.response?.data?.mensagem || "Não foi possível remover.", "erro");
    }
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 24 }}>
        <h1 style={{ fontSize: 20 }}>Despesas fixas</h1>
        <button onClick={() => setModalFixa(null)}>+ Nova despesa fixa</button>
      </div>

      <DataTable
        columns={[
          { key: "descricao", label: "Descrição" },
          { key: "valor", label: "Valor", render: (f) => brl(f.valor) },
          { key: "dia_lancamento", label: "Todo dia" },
        ]}
        rows={dados?.itens}
        loading={loading}
        vazio={{ titulo: "Nenhuma despesa fixa cadastrada", descricao: "Ex: aluguel, assinaturas, mensalidades." }}
        acoes={(f) => (
          <>
            <AcaoBtn onClick={() => setModalFixa(f)}>Editar</AcaoBtn>
            <AcaoBtn $perigo onClick={() => setRemovendo(f)}>Remover</AcaoBtn>
          </>
        )}
      />

      {modalFixa !== undefined && (
        <Modal aberto titulo={modalFixa ? "Editar despesa fixa" : "Nova despesa fixa"} onFechar={() => setModalFixa(undefined)}>
          <FormFixa
            fixa={modalFixa}
            onSalvo={() => {
              setModalFixa(undefined);
              avisar(modalFixa ? "Despesa fixa atualizada." : "Despesa fixa criada.");
              refetch();
            }}
            onErro={(msg) => avisar(msg, "erro")}
          />
        </Modal>
      )}

      <ConfirmDialog
        aberto={!!removendo}
        titulo="Remover despesa fixa"
        mensagem={`"${removendo?.descricao}" não vai mais lançar automaticamente. Lançamentos já feitos permanecem no histórico.`}
        onConfirmar={remover}
        onCancelar={() => setRemovendo(null)}
      />

      <Toast mensagem={toast?.mensagem} tipo={toast?.tipo} />
    </div>
  );
}

function FormFixa({ fixa, onSalvo, onErro }) {
  const [descricao, setDescricao] = useState(fixa?.descricao || "");
  const [valor, setValor] = useState(fixa?.valor || 0);
  const [dia, setDia] = useState(fixa?.dia_lancamento || "");
  const [categoriaId, setCategoriaId] = useState(fixa?.categoria_id || null);
  const [formaId, setFormaId] = useState(fixa?.forma_pagamento_id || null);
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!descricao.trim() || !valor || !dia) {
      setErro("Descrição, valor e dia são obrigatórios.");
      return;
    }
    setEnviando(true);
    setErro("");
    const payload = {
      descricao, valor, dia_lancamento: Number(dia),
      categoria_id: categoriaId, forma_pagamento_id: formaId,
    };
    try {
      if (fixa) {
        await api.put(`/fixas/${fixa.id}`, payload);
      } else {
        await api.post("/fixas", payload);
      }
      onSalvo();
    } catch (err) {
      onErro(err?.response?.data?.mensagem || "Não foi possível salvar.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16, minWidth: 300 }}>
      <Field>
        <label htmlFor="descricao-fixa">Descrição</label>
        <input id="descricao-fixa" value={descricao} onChange={(e) => setDescricao(e.target.value)} />
      </Field>
      <Field>
        <label htmlFor="valor-fixa">Valor</label>
        <MoneyInput id="valor-fixa" value={valor} onChange={setValor} />
      </Field>
      <Field>
        <label htmlFor="dia-fixa">Dia do lançamento</label>
        <input id="dia-fixa" type="number" min={1} max={31} value={dia} onChange={(e) => setDia(e.target.value)} />
      </Field>
      <Field>
        <label htmlFor="categoria-fixa">Categoria (opcional)</label>
        <CategoriaSelect id="categoria-fixa" value={categoriaId} onChange={setCategoriaId} incluirTodas />
      </Field>
      <Field>
        <label htmlFor="forma-fixa">Forma de pagamento (opcional)</label>
        <FormaSelect id="forma-fixa" value={formaId} onChange={setFormaId} incluirTodas />
      </Field>
      {erro && <div style={{ color: "#f2545b", fontSize: 13 }}>{erro}</div>}
      <SalvarBtn type="submit" disabled={enviando}>{enviando ? "Salvando..." : "Salvar"}</SalvarBtn>
    </form>
  );
}
