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
          {
            key: "valor", label: "Valor",
            render: (f) => (
              <>
                {brl(f.valor)}
                {f.valor_pendente != null && (
                  <div style={{ fontSize: 12, opacity: 0.7 }}>
                    {brl(f.valor_pendente)} a partir do próximo lançamento
                  </div>
                )}
              </>
            ),
          },
          { key: "dia_lancamento", label: "Todo dia" },
          {
            key: "parcelas_total",
            label: "Prazo",
            render: (f) =>
              f.parcelas_total
                ? `${f.lancadas ?? 0}/${f.parcelas_total} lançadas`
                : "sem fim",
          },
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

// Réplica em JS do truque de _dia_efetivo() no backend (services/despesas_fixas.py):
// dia_lancamento=31 num mês de 30 dias cai no último dia do mês, não "nunca lança".
function ultimoDiaDoMes(ano, mesUmIndexado) {
  return new Date(ano, mesUmIndexado, 0).getDate();
}

function FormFixa({ fixa, onSalvo, onErro }) {
  const [descricao, setDescricao] = useState(fixa?.descricao || "");
  const [valor, setValor] = useState(fixa?.valor || 0);
  const [dia, setDia] = useState(fixa?.dia_lancamento || "");
  const [categoriaId, setCategoriaId] = useState(fixa?.categoria_id || null);
  const [formaId, setFormaId] = useState(fixa?.forma_pagamento_id || null);
  const [parcelasTotal, setParcelasTotal] = useState(fixa?.parcelas_total || "");
  const [aplicarAPartir, setAplicarAPartir] = useState("imediato");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  // Só pergunta "a partir de quando" quando faz diferença de verdade: editando
  // uma fixa existente, mudando o valor, E o lançamento deste mês ainda não
  // aconteceu (dia_lancamento à frente de hoje). Depois que o dia passou,
  // mudar o valor só afeta o próximo lançamento de qualquer jeito — perguntar
  // seria ruído (ver services/despesas_fixas.py::atualizar_despesa_fixa).
  const hoje = new Date();
  const diaEfetivoMes = fixa?.dia_lancamento
    ? Math.min(fixa.dia_lancamento, ultimoDiaDoMes(hoje.getFullYear(), hoje.getMonth() + 1))
    : null;
  const aindaNaoLancouEsseMes = diaEfetivoMes != null && hoje.getDate() < diaEfetivoMes;
  const valorMudou = !!fixa && Number(valor) !== Number(fixa.valor);
  const precisaEscolherVigencia = !!fixa && valorMudou && aindaNaoLancouEsseMes;

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
      parcelas_total: parcelasTotal ? Number(parcelasTotal) : null,
      aplicar_a_partir: precisaEscolherVigencia ? aplicarAPartir : "imediato",
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
      <Field>
        <label htmlFor="prazo-fixa">Quantidade de meses (opcional)</label>
        <input
          id="prazo-fixa" type="number" min={1} max={600}
          value={parcelasTotal} onChange={(e) => setParcelasTotal(e.target.value)}
          placeholder="ex: 48 (financiamento) — vazio = sem fim"
        />
        <small style={{ opacity: 0.7 }}>
          Custo fixo com prazo (financiamento, consórcio): para de lançar
          sozinho na última parcela.
        </small>
      </Field>
      {precisaEscolherVigencia && (
        <Field>
          <label>Esse reajuste vale a partir de quando?</label>
          <label style={{ fontWeight: "normal", display: "flex", gap: 6, alignItems: "center" }}>
            <input
              type="radio" name="aplicar-a-partir" value="imediato"
              checked={aplicarAPartir === "imediato"}
              onChange={() => setAplicarAPartir("imediato")}
            />
            Já no lançamento deste mês (dia {diaEfetivoMes})
          </label>
          <label style={{ fontWeight: "normal", display: "flex", gap: 6, alignItems: "center" }}>
            <input
              type="radio" name="aplicar-a-partir" value="proximo_mes"
              checked={aplicarAPartir === "proximo_mes"}
              onChange={() => setAplicarAPartir("proximo_mes")}
            />
            Só a partir do lançamento do mês que vem (este mês mantém {brl(fixa.valor)})
          </label>
        </Field>
      )}
      {erro && <div style={{ color: "#f2545b", fontSize: 13 }}>{erro}</div>}
      <SalvarBtn type="submit" disabled={enviando}>{enviando ? "Salvando..." : "Salvar"}</SalvarBtn>
    </form>
  );
}
