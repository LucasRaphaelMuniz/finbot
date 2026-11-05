"use client";

// components/NovoLancamento — modal de "novo lançamento" (gasto ou
// entrada). Antes vivia dentro de lancamentos/page.jsx e só abria lá; no
// redesign de 05/11/2026 virou ação global (botão no Header no desktop,
// "+" central da BottomNav no celular — padrão Mobills/Organizze), então
// saiu da página e passou a ser montado uma vez só no (app)/layout.jsx.
//
// Quem precisa reagir a um lançamento novo (Lançamentos, Início) escuta o
// evento EVENTO_LANCAMENTO_SALVO em vez de receber callback — o modal não
// sabe qual tela está aberta por baixo.
import { useState } from "react";
import { TrendingDown, TrendingUp } from "lucide-react";
import api from "@/services/api";
import Modal from "@/components/Modal";
import CategoriaSelect from "@/components/CategoriaSelect";
import FormaSelect from "@/components/FormaSelect";
import MoneyInput from "@/components/MoneyInput";
import { Field } from "@/components/AuthCard/styles";
import { Form, ToggleTipo, ToggleBtn, Erro, SalvarBtn } from "./styles";

export const EVENTO_LANCAMENTO_SALVO = "finbot:lancamento-salvo";

export default function NovoLancamento({ aberto, onFechar, onSalvo, onErro }) {
  const [tipo, setTipo] = useState("gasto"); // gasto | entrada
  const [valor, setValor] = useState(0);
  const [descricao, setDescricao] = useState("");
  const [categoriaId, setCategoriaId] = useState(null);
  const [formaId, setFormaId] = useState(null);
  const [parcelado, setParcelado] = useState(false);
  const [parcelas, setParcelas] = useState(2);
  // Pedido do Lucas (24/07/2026): as entradas dele são quase todas fixas
  // (salário, VA/VR) — o checkbox de recorrente já vem marcado.
  const [recorrente, setRecorrente] = useState(true);
  const [diaLancamento, setDiaLancamento] = useState(new Date().getDate());
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
    setRecorrente(true);
    setDiaLancamento(new Date().getDate());
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
        // `recorrente` cria também o modelo em entradas_fixas — o lançador
        // diário repete a entrada nos próximos meses no dia informado.
        await api.post("/entradas", {
          valor, descricao,
          ...(recorrente ? { recorrente: true, dia_lancamento: diaLancamento } : {}),
        });
      } else {
        if (!categoriaId || !formaId) {
          setErro("Selecione categoria e forma de pagamento.");
          setEnviando(false);
          return;
        }
        // `parcelas` >= 2 faz o POST /gastos criar a compra parcelada
        // inteira (services/parcelamento.py — a mesma do bot).
        await api.post("/gastos", {
          valor, descricao, categoria_id: categoriaId, forma_pagamento_id: formaId,
          ...(parcelado && parcelas >= 2 ? { parcelas } : {}),
        });
      }
      const tipoSalvo = tipo;
      resetar();
      window.dispatchEvent(new CustomEvent(EVENTO_LANCAMENTO_SALVO, { detail: { tipo: tipoSalvo } }));
      onSalvo?.(tipoSalvo);
    } catch (err) {
      onErro?.(err?.response?.data?.mensagem || "Não foi possível salvar.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Modal aberto={aberto} titulo="Novo lançamento" onFechar={() => { resetar(); onFechar(); }}>
      <Form onSubmit={handleSubmit}>
        <ToggleTipo role="group" aria-label="Tipo de lançamento">
          <ToggleBtn type="button" $tom="gasto" aria-pressed={tipo === "gasto"} $ativo={tipo === "gasto"} onClick={() => setTipo("gasto")}>
            <TrendingDown size={16} aria-hidden="true" /> Gasto
          </ToggleBtn>
          <ToggleBtn type="button" $tom="entrada" aria-pressed={tipo === "entrada"} $ativo={tipo === "entrada"} onClick={() => setTipo("entrada")}>
            <TrendingUp size={16} aria-hidden="true" /> Entrada
          </ToggleBtn>
        </ToggleTipo>

        <Field>
          <label htmlFor="novo-valor">Valor</label>
          <MoneyInput id="novo-valor" value={valor} onChange={setValor} data-autofocus />
        </Field>

        <Field>
          <label htmlFor="novo-descricao">Descrição</label>
          <input id="novo-descricao" value={descricao} onChange={(e) => setDescricao(e.target.value)} />
        </Field>

        {tipo === "entrada" && (
          <>
            <Field>
              <label>
                <input type="checkbox" checked={recorrente} onChange={(e) => setRecorrente(e.target.checked)} />
                {" "}Recorrente/Fixo (cai todo mês — ex: salário)
              </label>
            </Field>
            {recorrente && (
              <Field>
                <label htmlFor="novo-dia-entrada">Dia do mês em que cai</label>
                <input
                  id="novo-dia-entrada" type="number" min={1} max={31}
                  value={diaLancamento} onChange={(e) => setDiaLancamento(Number(e.target.value))}
                />
              </Field>
            )}
          </>
        )}

        {tipo === "gasto" && (
          <>
            <Field>
              <label htmlFor="novo-categoria">Categoria</label>
              <CategoriaSelect id="novo-categoria" value={categoriaId} onChange={setCategoriaId} />
            </Field>
            <Field>
              <label htmlFor="novo-forma">Forma de pagamento</label>
              <FormaSelect id="novo-forma" value={formaId} onChange={setFormaId} />
            </Field>
            <Field>
              <label>
                <input type="checkbox" checked={parcelado} onChange={(e) => setParcelado(e.target.checked)} />
                {" "}Compra parcelada
              </label>
            </Field>
            {parcelado && (
              <Field>
                <label htmlFor="novo-parcelas">Número de parcelas</label>
                <input
                  id="novo-parcelas" type="number" min={2} max={48}
                  value={parcelas} onChange={(e) => setParcelas(Number(e.target.value))}
                />
              </Field>
            )}
          </>
        )}

        {erro && <Erro role="alert">{erro}</Erro>}
        <SalvarBtn type="submit" disabled={enviando}>
          {enviando ? "Salvando..." : tipo === "gasto" ? "Salvar gasto" : "Salvar entrada"}
        </SalvarBtn>
      </Form>
    </Modal>
  );
}
