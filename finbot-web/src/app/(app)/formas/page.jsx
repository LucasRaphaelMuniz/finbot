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
  const [faturaDe, setFaturaDe] = useState(null); // forma selecionada pra "Ver fatura", ou null = fechado

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
          { key: "dia_vencimento", label: "Dia de vencimento", render: (f) => f.dia_vencimento || "—" },
        ]}
        rows={dados?.itens}
        loading={loading}
        vazio={{ titulo: "Nenhuma forma de pagamento cadastrada" }}
        acoes={(f) => (
          <>
            {f.dia_fechamento && <AcaoBtn onClick={() => setFaturaDe(f)}>Ver fatura</AcaoBtn>}
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

      {faturaDe && (
        <Modal aberto titulo={`Fatura — ${faturaDe.nome}`} onFechar={() => setFaturaDe(null)}>
          <StatusCartao forma={faturaDe} onErro={(msg) => avisar(msg, "erro")} onAjustado={() => avisar("Ajuste salvo.")} />
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

function StatusCartao({ forma, onErro, onAjustado }) {
  // GET /formas/:id/status-cartao (services/faturas.py::status_cartao) —
  // fatura_atual (real, já lançado + ajuste) e fatura_atual_estimada (real +
  // despesas fixas desse cartão ainda não lançadas nessa competência).
  const { dados: status, loading, refetch } = useApi(`/formas/${forma.id}/status-cartao`);

  if (loading || !status) return <p style={{ opacity: 0.7 }}>Carregando...</p>;

  function aoAjustar() {
    refetch();
    onAjustado();
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, minWidth: 320 }}>
      <LinhaValor label="Fatura atual (real)" valor={status.fatura_atual} />
      <LinhaValor
        label="Fatura atual (estimada)"
        valor={status.fatura_atual_estimada}
        detalhe={
          status.fixas_previstas_qtd > 0
            ? `inclui ${status.fixas_previstas_qtd} despesa(s) fixa(s) ainda não cobrada(s) este mês`
            : "sem despesa fixa pendente este mês — igual à real"
        }
      />
      {status.limite_mensal != null && (
        <LinhaValor label="Limite mensal" valor={status.limite_mensal} />
      )}
      {status.limite_disponivel != null && (
        <LinhaValor label="Limite disponível" valor={status.limite_disponivel} />
      )}
      <LinhaValor
        label="Fatura anterior (a pagar)"
        valor={status.fatura_anterior}
        detalhe={`vence em ${status.vencimento_fatura_anterior || "—"}`}
      />

      {/* 29/08/2026 (pedido do Lucas): o ajuste manual (migração 028) sempre
          pôde mirar qualquer competência — services/faturas.py::status_cartao
          já calcula e devolve ajuste_fatura_anterior/ajuste_motivo_anterior,
          e a rota PUT /ajuste-fatura já aceita `competencia` livre. O que
          faltava era o botão: só existia UM bloco de ajuste aqui, sempre
          preso à fatura ATUAL — não tinha como o usuário mirar a fatura que
          JÁ FECHOU (a que está "a pagar" acima). Dois blocos agora, cada um
          com sua própria competência/estado — a fatura anterior é editável
          igual à atual, sem duplicar lógica (AjusteFaturaBloco). */}
      <AjusteFaturaBloco
        titulo="fatura atual"
        forma={forma}
        competencia={status.competencia_atual}
        ajusteAtual={status.ajuste_fatura_atual}
        motivoAtual={status.ajuste_motivo_atual}
        onAjustado={aoAjustar}
        onErro={onErro}
      />
      <AjusteFaturaBloco
        titulo="fatura anterior (já fechada)"
        forma={forma}
        competencia={status.competencia_anterior}
        ajusteAtual={status.ajuste_fatura_anterior}
        motivoAtual={status.ajuste_motivo_anterior}
        onAjustado={aoAjustar}
        onErro={onErro}
      />
    </div>
  );
}

function AjusteFaturaBloco({ titulo, forma, competencia, ajusteAtual, motivoAtual, onAjustado, onErro }) {
  const [editando, setEditando] = useState(false);

  return (
    <div style={{ borderTop: "1px solid rgba(128,128,128,0.25)", paddingTop: 12 }}>
      {editando ? (
        <AjusteFaturaForm
          forma={forma}
          competencia={competencia}
          ajusteAtual={ajusteAtual}
          motivoAtual={motivoAtual}
          onSalvo={() => {
            setEditando(false);
            onAjustado();
          }}
          onErro={onErro}
          onCancelar={() => setEditando(false)}
        />
      ) : (
        <>
          <p style={{ fontSize: 13, opacity: 0.8 }}>
            Ajuste manual da {titulo}:{" "}
            <strong>{brl(ajusteAtual || 0)}</strong>
            {motivoAtual ? ` — ${motivoAtual}` : ""}
          </p>
          <small style={{ opacity: 0.7 }}>
            Some por cima do total calculado — use quando o banco fecha a
            fatura com juros, IOF ou arredondamento que não vira um gasto
            lançado.
          </small>
          <div style={{ marginTop: 8 }}>
            <button type="button" onClick={() => setEditando(true)}>
              {ajusteAtual ? "Editar ajuste" : "Adicionar ajuste"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function LinhaValor({ label, valor, detalhe }) {
  return (
    <div>
      <p style={{ opacity: 0.7, fontSize: 13 }}>{label}</p>
      <p style={{ fontSize: 18 }}>{brl(valor || 0)}</p>
      {detalhe && <small style={{ opacity: 0.7 }}>{detalhe}</small>}
    </div>
  );
}

function AjusteFaturaForm({ forma, competencia, ajusteAtual, motivoAtual, onSalvo, onErro, onCancelar }) {
  const [valor, setValor] = useState(Math.abs(ajusteAtual || 0));
  const [negativo, setNegativo] = useState((ajusteAtual || 0) < 0);
  const [motivo, setMotivo] = useState(motivoAtual || "");
  const [enviando, setEnviando] = useState(false);

  async function salvar() {
    setEnviando(true);
    try {
      await api.put(`/formas/${forma.id}/ajuste-fatura`, {
        competencia,
        valor_ajuste: negativo ? -Math.abs(valor) : Math.abs(valor),
        motivo: motivo.trim() || null,
      });
      onSalvo();
    } catch (err) {
      onErro(err?.response?.data?.mensagem || "Não foi possível salvar o ajuste.");
    } finally {
      setEnviando(false);
    }
  }

  async function remover() {
    setEnviando(true);
    try {
      await api.delete(`/formas/${forma.id}/ajuste-fatura`, { data: { competencia } });
      onSalvo();
    } catch (err) {
      onErro(err?.response?.data?.mensagem || "Não foi possível remover o ajuste.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <Field>
        <label htmlFor="ajuste-valor">Diferença</label>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <select value={negativo ? "-" : "+"} onChange={(e) => setNegativo(e.target.value === "-")} style={{ width: 64 }}>
            <option value="+">+</option>
            <option value="-">−</option>
          </select>
          <MoneyInput id="ajuste-valor" value={valor} onChange={setValor} />
        </div>
        <small style={{ opacity: 0.7 }}>
          + quando a fatura fechou maior que o calculado (juros/IOF); − quando
          fechou menor (desconto/estorno).
        </small>
      </Field>
      <Field>
        <label htmlFor="ajuste-motivo">Motivo (opcional)</label>
        <input id="ajuste-motivo" value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="ex: IOF de compra internacional" />
      </Field>
      <div style={{ display: "flex", gap: 8 }}>
        <SalvarBtn type="button" disabled={enviando} onClick={salvar}>
          {enviando ? "Salvando..." : "Salvar ajuste"}
        </SalvarBtn>
        {ajusteAtual ? (
          <AcaoBtn $perigo type="button" disabled={enviando} onClick={remover}>Remover ajuste</AcaoBtn>
        ) : null}
        <button type="button" onClick={onCancelar} disabled={enviando}>Cancelar</button>
      </div>
    </div>
  );
}

function FormForma({ forma, onSalvo, onErro }) {
  const [nome, setNome] = useState(forma?.nome || "");
  const [limite, setLimite] = useState(forma?.limite_mensal || 0);
  const [semLimite, setSemLimite] = useState(!forma?.limite_mensal);
  const [diaFechamento, setDiaFechamento] = useState(forma?.dia_fechamento || "");
  const [diaVencimento, setDiaVencimento] = useState(forma?.dia_vencimento || "");
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
      dia_vencimento: diaVencimento ? Number(diaVencimento) : null,
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
          Data em que a fatura fecha — determina em qual fatura a compra cai.
        </small>
      </Field>
      {diaFechamento && (
        <Field>
          <label htmlFor="vencimento-forma">Dia de vencimento da fatura</label>
          <input
            id="vencimento-forma" type="number" min={1} max={31}
            value={diaVencimento} onChange={(e) => setDiaVencimento(e.target.value)}
            placeholder="ex: 5"
          />
          <small style={{ opacity: 0.7 }}>
            Data em que a fatura é paga — usada pra provisionar a fatura no
            caixa do mês certo (os gastos continuam aparecendo no mês da
            compra). Sem preencher, assume o mês seguinte ao fechamento
            (caso mais comum).
          </small>
        </Field>
      )}
      {erro && <div style={{ color: "#f2545b", fontSize: 13 }}>{erro}</div>}
      <SalvarBtn type="submit" disabled={enviando}>{enviando ? "Salvando..." : "Salvar"}</SalvarBtn>
    </form>
  );
}
