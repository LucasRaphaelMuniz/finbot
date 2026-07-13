"use client";

// app/(app)/categorias/page.jsx — CRUD de categorias (Fase 5.5). Categoria
// global (grupo_id null) aparece como "padrão": não tem botão de
// editar/remover — G5 do plano (categorias globais nunca somem, só
// personalizadas do grupo podem ser removidas).
import { useState } from "react";
import { useApi } from "@/hooks/useApi";
import api from "@/services/api";
import DataTable from "@/components/DataTable";
import { AcaoBtn } from "@/components/DataTable/styles";
import Modal from "@/components/Modal";
import ConfirmDialog from "@/components/ConfirmDialog";
import Toast from "@/components/Toast";
import { Field, Botao as SalvarBtn } from "@/components/AuthCard/styles";

export default function CategoriasPage() {
  const { dados, loading, refetch } = useApi("/categorias");
  const [toast, setToast] = useState(null);
  const [modalCategoria, setModalCategoria] = useState(undefined);
  const [removendo, setRemovendo] = useState(null);

  function avisar(mensagem, tipo = "sucesso") {
    setToast({ mensagem, tipo });
    setTimeout(() => setToast(null), 3000);
  }

  async function remover() {
    try {
      await api.delete(`/categorias/${removendo.id}`);
      avisar("Categoria removida.");
      setRemovendo(null);
      refetch();
    } catch (err) {
      avisar(err?.response?.data?.mensagem || "Não foi possível remover.", "erro");
    }
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 24 }}>
        <h1 style={{ fontSize: 20 }}>Categorias</h1>
        <button onClick={() => setModalCategoria(null)}>+ Nova categoria</button>
      </div>

      <DataTable
        columns={[
          {
            key: "nome", label: "Nome",
            render: (c) => c.nome + (c.grupo_id == null ? "  (padrão)" : ""),
          },
        ]}
        rows={dados?.itens}
        loading={loading}
        vazio={{ titulo: "Nenhuma categoria" }}
        acoes={(c) =>
          c.grupo_id == null ? null : (
            <>
              <AcaoBtn onClick={() => setModalCategoria(c)}>Editar</AcaoBtn>
              <AcaoBtn $perigo onClick={() => setRemovendo(c)}>Remover</AcaoBtn>
            </>
          )
        }
      />

      {modalCategoria !== undefined && (
        <Modal aberto titulo={modalCategoria ? "Editar categoria" : "Nova categoria"} onFechar={() => setModalCategoria(undefined)}>
          <FormCategoria
            categoria={modalCategoria}
            onSalvo={() => {
              setModalCategoria(undefined);
              avisar(modalCategoria ? "Categoria atualizada." : "Categoria criada.");
              refetch();
            }}
            onErro={(msg) => avisar(msg, "erro")}
          />
        </Modal>
      )}

      <ConfirmDialog
        aberto={!!removendo}
        titulo="Remover categoria"
        mensagem={`Remover "${removendo?.nome}"? Gastos já registrados com ela não são apagados.`}
        onConfirmar={remover}
        onCancelar={() => setRemovendo(null)}
      />

      <Toast mensagem={toast?.mensagem} tipo={toast?.tipo} />
    </div>
  );
}

function FormCategoria({ categoria, onSalvo, onErro }) {
  const [nome, setNome] = useState(categoria?.nome || "");
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
    try {
      if (categoria) {
        await api.put(`/categorias/${categoria.id}`, { nome });
      } else {
        await api.post("/categorias", { nome });
      }
      onSalvo();
    } catch (err) {
      onErro(err?.response?.data?.mensagem || "Não foi possível salvar.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16, minWidth: 280 }}>
      <Field>
        <label htmlFor="nome-categoria">Nome</label>
        <input id="nome-categoria" value={nome} onChange={(e) => setNome(e.target.value)} />
      </Field>
      {erro && <div style={{ color: "#f2545b", fontSize: 13 }}>{erro}</div>}
      <SalvarBtn type="submit" disabled={enviando}>{enviando ? "Salvando..." : "Salvar"}</SalvarBtn>
    </form>
  );
}
