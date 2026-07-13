"use client";

// app/(app)/formas/page.jsx — CRUD de formas de pagamento (Fase 5.5 do
// PLANO_EXECUCAO.md). dia_fechamento é o campo que determina a competência
// de gastos no cartão perto do fechamento (Fase 3.2/services/competencia.py) —
// por isso o aviso inline no formulário.
import { useState } from "react";
import { useApi } from "@/hooks/useApi";
import api from "@/services/api";
import { brl } from "@/utils/format";
import DataTable from "@/components/DataTable";
import { AcaoBtn } from "@/components/DataTable/styles";
import Modal from "@/components/Modal";
import ConfirmDialog from "@/components/ConfirmDialog";
import MoneyInput from "@/components/MoneyInput";
import Toast from "@/components/Toast";
import { Field, Botao as SalvarBtn } from "@/components/AuthCard/styles";

export default function FormasPage() {
  const { dados, loading, refetch } = useApi("/formas");
  const [toast, setToast] = useState(null);
  const [modalForma, setModalForma] = useState(undefined); // undefined = fechado, null = criar, {} = editar
  const [removendo, setRemovendo] = useState(null);

  function avisar(mensagem, tipo = "sucesso") {
    setToast({ mensagem, tipo });
    setTimeout(() => setToast(null), 3000);
  }

  async function remover() {
    try {
      await api.delete(`/formas/${removendo.id}`);
      avisar("Forma removida.");
      setRemovendo(null);
      refetch();
    } catch (err) {
      avisar(err?.response?.data?.mensagem || "Não foi possível remover.", "erro");
    }
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 24 }}>
        <h1 style={{ fontSize: 20 }}>Formas de pagamento</h1>
        <button onClick={() => setModalForma(null)}>+ Nova forma</button>
      </div>

      <DataTable
        columns={[
          { key: "nome", label: "Nome" },
          { key: "limite_mensal", label: "Limite mensal", render: (f) => f.limite_mensal ? brl(f.limite_mensal) : "Sem limite" },
          { key: "dia_fechamento", label: "Dia de fechamento", render: (f) => f.dia_fechamento || "—" },
        ]}
        rows={dados?.itens}
        loading={loading}
        vazio={{ titulo: "Nenhuma forma de pagamento cadastrada" }}
        acoes={(f) => (
          <>
            <AcaoBtn onClick={() => setModalForma(f)}>Editar</AcaoBtn>
            <AcaoBtn $perigo onClick={() => setRemovendo(f)}>Remover</AcaoBtn>
          </>
        )}
      />

      {modalForma !== undefined && (
        <Modal aberto titulo={modalForma ? "Editar forma" : "Nova forma"} onFechar={() => setModalForma(undefined)}>
          <FormForma
            forma={modalForma}
            onSalvo={() => {
              setModalForma(undefined);
              avisar(modalForma ? "Forma atualizada." : "Forma criada.");
              refetch();
            }}
            onErro={(msg) => avisar(msg, "erro")}
          />
        </Modal>
      )}

      <ConfirmDialog
        aberto={!!removendo}
        titulo="Remover forma de pagamento"
        mensagem={`Remover "${removendo?.nome}"? Gastos já registrados com ela não são apagados.`}
        onConfirmar={remover}
        onCancelar={() => setRemovendo(null)}
      />

      <Toast mensagem={toast?.mensagem} tipo={toast?.tipo} />
    </div>
  );
}

function FormForma({ forma, onSalvo, onErro }) {
  const [nome, setNome] = useState(forma?.nome || "");
  const [limite, setLimite] = useState(forma?.limite_mensal || 0);
  const [semLimite, setSemLimite] = useState(!forma?.limite_mensal);
  const [diaFechamento, setDiaFechamento] = useState(forma?.dia_fechamento || "");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!nome.trim()) {
      setErro("Nome é obrigatório.");
      return;
    }
    setEnviando(true);
    setErro("");
    const payload = {
      nome,
      limite_mensal: semLimite ? null : limite,
      dia_fechamento: diaFechamento ? Number(diaFechamento) : null,
    };
    try {
      if (forma) {
        await api.put(`/formas/${forma.id}`, payload);
      } else {
        await api.post("/formas", payload);
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
        <label htmlFor="nome-forma">Nome</label>
        <input id="nome-forma" value={nome} onChange={(e) => setNome(e.target.value)} />
      </Field>
      <Field>
        <label>
          <input type="checkbox" checked={semLimite} onChange={(e) => setSemLimite(e.target.checked)} />
          {" "}Sem limite mensal
        </label>
      </Field>
      {!semLimite && (
        <Field>
          <label htmlFor="limite-forma">Limite mensal</label>
          <MoneyInput id="limite-forma" value={limite} onChange={setLimite} />
        </Field>
      )}
      <Field>
        <label htmlFor="fechamento-forma">Dia de fechamento (só cartão de crédito)</label>
        <input
          id="fechamento-forma" type="number" min={1} max={31}
          value={diaFechamento} onChange={(e) => setDiaFechamento(e.target.value)}
          placeholder="ex: 25"
        />
        <small style={{ opacity: 0.7 }}>
          Gastos depois desse dia entram na competência do mês seguinte.
        </small>
      </Field>
      {erro && <div style={{ color: "#f2545b", fontSize: 13 }}>{erro}</div>}
      <SalvarBtn type="submit" disabled={enviando}>{enviando ? "Salvando..." : "Salvar"}</SalvarBtn>
    </form>
  );
}
