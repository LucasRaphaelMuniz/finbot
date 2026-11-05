"use client";

// app/(app)/fixas/page.jsx — CRUD de despesas fixas. Não tem seção própria
// numerada no §5 do PLANO_EXECUCAO.md (o plano lista a pasta em 4.1 mas
// detalha só 5.1-5.6, sem "5.x /fixas" explícito) — construída aqui pra
// fechar o gap, já que o backend (routes/fixas.py, Fase 4.3) já suporta.
// "Remover" é soft-delete (ativa=FALSE) — mesma razão do bot: gastos já
// lançados referenciam despesa_fixa_id sem cascade.
import { useMemo, useState } from "react";
import { Plus } from "lucide-react";
import { useApi } from "@/hooks/useApi";
import api from "@/services/api";
import { brl } from "@/utils/format";
import { categoriaVisual } from "@/utils/categoriaVisual";
import Painel from "@/components/Painel";
import ConfirmDialog from "@/components/ConfirmDialog";
import MoneyInput from "@/components/MoneyInput";
import CategoriaSelect from "@/components/CategoriaSelect";
import FormaSelect from "@/components/FormaSelect";
import Toast from "@/components/Toast";
import { Field } from "@/components/AuthCard/styles";
import {
  Header, Titulo, Subtitulo, NovoBtn, Resumo, ResumoItem, Lista, Linha, LinhaBtn, DiaBadge,
  Avatar, LinhaTexto, LinhaTitulo, LinhaMeta, Progresso, ProgressoCheio, Valor, ValorNovo,
  Vazio, SkeletonLinha, Form, Erro, SalvarBtn, RemoverBtn,
} from "./styles";

// Redesign 05/11/2026 (fase 3): de tabela para lista ordenada pelo dia do
// mês — é a ordem em que as contas caem, como um calendário. Cada linha
// mostra o dia em destaque, categoria/forma por nome (a API de fixas só
// devolve os ids) e, nas fixas com prazo, uma barra de quanto já foi
// lançado. Criar/editar abre o painel lateral (components/Painel), com
// "Remover" no rodapé em vez de um botão em cada linha.
export default function FixasPage() {
  const { dados, loading, refetch } = useApi("/fixas");
  const { dados: categorias } = useApi("/categorias");
  const { dados: formas } = useApi("/formas");
  const [toast, setToast] = useState(null);
  // undefined = painel fechado; null = nova; objeto = editando
  const [painelFixa, setPainelFixa] = useState(undefined);
  const [removendo, setRemovendo] = useState(null);

  const nomeCategoria = useMemo(() => mapaNomes(categorias), [categorias]);
  const nomeForma = useMemo(() => mapaNomes(formas), [formas]);

  const itens = dados?.itens || [];
  const total = itens.reduce((soma, f) => soma + Number(f.valor || 0), 0);
  const comPrazo = itens.filter((f) => f.parcelas_total).length;

  function avisar(mensagem, tipo = "sucesso") {
    setToast({ mensagem, tipo });
    setTimeout(() => setToast(null), 3000);
  }

  async function remover() {
    try {
      await api.delete(`/fixas/${removendo.id}`);
      avisar("Despesa fixa removida (não lança mais).");
      setRemovendo(null);
      refetch({ silent: true });
    } catch (err) {
      avisar(err?.response?.data?.mensagem || "Não foi possível remover.", "erro");
    }
  }

  // Remover sai do painel: fecha o painel antes de abrir a confirmação
  // (mesmo motivo de Lançamentos — dois diálogos brigariam pelo Esc).
  function pedirRemocao(f) {
    setPainelFixa(undefined);
    setRemovendo(f);
  }

  return (
    <div>
      <Header>
        <div>
          <Titulo>Despesas fixas</Titulo>
          <Subtitulo>Lançadas sozinhas todo mês, no dia marcado.</Subtitulo>
        </div>
        <NovoBtn type="button" onClick={() => setPainelFixa(null)}>
          <Plus size={16} aria-hidden="true" /> Nova despesa fixa
        </NovoBtn>
      </Header>

      {itens.length > 0 && (
        <Resumo aria-label="Totais">
          <ResumoItem>
            <span>Por mês</span>
            <strong>{brl(total)}</strong>
          </ResumoItem>
          <ResumoItem>
            <span>Despesas</span>
            <strong>{itens.length}</strong>
          </ResumoItem>
          {comPrazo > 0 && (
            <ResumoItem>
              <span>Com prazo</span>
              <strong>{comPrazo}</strong>
            </ResumoItem>
          )}
        </Resumo>
      )}

      <Lista aria-busy={loading || undefined}>
        {loading && !dados ? (
          [0, 1, 2, 3].map((i) => <SkeletonLinha key={i} />)
        ) : itens.length === 0 ? (
          <Vazio>
            <strong>Nenhuma despesa fixa cadastrada.</strong>
            <span>Aluguel, assinaturas, mensalidades: cadastre uma vez e o finbot lança todo mês.</span>
          </Vazio>
        ) : (
          <ul>
            {itens.map((f) => {
              const categoria = nomeCategoria.get(f.categoria_id);
              const visual = categoriaVisual(categoria || f.descricao);
              const pct = f.parcelas_total
                ? Math.min(100, ((f.lancadas ?? 0) / f.parcelas_total) * 100)
                : null;
              return (
                <Linha key={f.id}>
                  <LinhaBtn type="button" onClick={() => setPainelFixa(f)}>
                    <DiaBadge>
                      <small>dia</small>
                      <span>{f.dia_lancamento}</span>
                    </DiaBadge>
                    <Avatar style={{ background: visual.fundo, color: visual.cor }} aria-hidden="true">
                      <visual.Icone size={18} strokeWidth={2} />
                    </Avatar>
                    <LinhaTexto>
                      <LinhaTitulo>{f.descricao}</LinhaTitulo>
                      <LinhaMeta>
                        {[
                          categoria,
                          nomeForma.get(f.forma_pagamento_id),
                          f.parcelas_total ? `${f.lancadas ?? 0}/${f.parcelas_total} lançadas` : "sem fim",
                        ].filter(Boolean).join(" · ")}
                      </LinhaMeta>
                      {pct != null && (
                        <Progresso aria-hidden="true">
                          <ProgressoCheio style={{ width: `${pct}%` }} />
                        </Progresso>
                      )}
                    </LinhaTexto>
                    <Valor>
                      {brl(f.valor)}
                      {f.valor_pendente != null && (
                        <ValorNovo>{brl(f.valor_pendente)} a partir do próximo</ValorNovo>
                      )}
                    </Valor>
                  </LinhaBtn>
                </Linha>
              );
            })}
          </ul>
        )}
      </Lista>

      {painelFixa !== undefined && (
        <PainelFixa
          fixa={painelFixa}
          onFechar={() => setPainelFixa(undefined)}
          onRemover={() => pedirRemocao(painelFixa)}
          onSalvo={() => {
            avisar(painelFixa ? "Despesa fixa atualizada." : "Despesa fixa criada.");
            setPainelFixa(undefined);
            refetch({ silent: true });
          }}
        />
      )}

      <ConfirmDialog
        aberto={!!removendo}
        titulo="Remover despesa fixa"
        textoConfirmar="Remover despesa fixa"
        mensagem={`"${removendo?.descricao}" não vai mais lançar automaticamente. Lançamentos já feitos permanecem no histórico.`}
        onConfirmar={remover}
        onCancelar={() => setRemovendo(null)}
      />

      <Toast mensagem={toast?.mensagem} tipo={toast?.tipo} />
    </div>
  );
}

function mapaNomes(dados) {
  const lista = Array.isArray(dados) ? dados : dados?.itens || [];
  return new Map(lista.map((x) => [x.id, x.nome]));
}

function PainelFixa({ fixa, onFechar, onRemover, onSalvo }) {
  return (
    <Painel
      aberto
      titulo={fixa ? fixa.descricao : "Nova despesa fixa"}
      subtitulo={fixa ? `Lança todo dia ${fixa.dia_lancamento}` : "Lançada sozinha todo mês"}
      onFechar={onFechar}
      rodape={
        <>
          {fixa && <RemoverBtn type="button" onClick={onRemover}>Remover</RemoverBtn>}
          <SalvarBtn type="submit" form="form-fixa">
            {fixa ? "Salvar alterações" : "Criar despesa fixa"}
          </SalvarBtn>
        </>
      }
    >
      <FormFixa fixa={fixa} onSalvo={onSalvo} />
    </Painel>
  );
}

// Réplica em JS do truque de _dia_efetivo() no backend (services/despesas_fixas.py):
// dia_lancamento=31 num mês de 30 dias cai no último dia do mês, não "nunca lança".
function ultimoDiaDoMes(ano, mesUmIndexado) {
  return new Date(ano, mesUmIndexado, 0).getDate();
}

function FormFixa({ fixa, onSalvo }) {
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
      setErro(err?.response?.data?.mensagem || "Não foi possível salvar.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Form id="form-fixa" onSubmit={handleSubmit} aria-busy={enviando || undefined}>
      <Field>
        <label htmlFor="descricao-fixa">Descrição</label>
        <input id="descricao-fixa" data-autofocus value={descricao} onChange={(e) => setDescricao(e.target.value)} />
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
      {erro && <Erro role="alert">{erro}</Erro>}
    </Form>
  );
}
