"use client";

// app/(app)/lancamentos/page.jsx — extrato do mês (redesign de 05/11/2026,
// fase 2; referências: Copilot, Monarch, Mobills).
//
// Antes: duas abas (Gastos | Entradas) com uma tabela cada e edição em
// modal no meio da tela. Agora:
//   - gastos e entradas numa lista só, agrupada por dia, com o saldo do
//     dia no cabeçalho (como extrato de banco);
//   - filtros rápidos em chip (tipo e origem) + busca por texto; categoria
//     e forma ficam em "Mais filtros" porque são usados com menos
//     frequência e ocupam muito espaço no celular;
//   - clicar numa linha abre um painel lateral com detalhe + edição, e a
//     exclusão sai de lá (em vez de dois botões em cada linha).
// Linha "previsto" (custo fixo projetado — services/gastos.py::
// projetar_despesas_fixas) não tem gasto real por trás: aparece atenuada
// e não abre painel.
import { useEffect, useMemo, useState } from "react";
import { Search, SlidersHorizontal, TrendingUp, X } from "lucide-react";
import { useApi } from "@/hooks/useApi";
import api from "@/services/api";
import { brl, formatarDataBR } from "@/utils/format";
import { mesAtualISO, rotuloDia } from "@/utils/datas";
import { categoriaVisual, COR_ENTRADA } from "@/utils/categoriaVisual";
import Modal from "@/components/Modal";
import Painel from "@/components/Painel";
import ConfirmDialog from "@/components/ConfirmDialog";
import MesPicker from "@/components/MesPicker";
import CategoriaSelect from "@/components/CategoriaSelect";
import FormaSelect from "@/components/FormaSelect";
import MoneyInput from "@/components/MoneyInput";
import Toast from "@/components/Toast";
import { EVENTO_LANCAMENTO_SALVO } from "@/components/NovoLancamento";
import { Field } from "@/components/AuthCard/styles";
import {
  Header, Titulo, Barra, Busca, Chips, Chip, ChipsLinha, MaisFiltrosBtn, Contador,
  Filtros, FiltroCampo, LimparBtn, Resumo, ResumoItem, Lista, Dia, DiaTopo, Linha,
  LinhaBtn, Avatar, LinhaTexto, LinhaTitulo, LinhaMeta, Selo, Valor, Vazio,
  SkeletonLinha, Form, Erro, PainelValor, PainelInfo, SalvarBtn, ExcluirBtn,
} from "./styles";

const TIPOS = [
  { id: "todos", rotulo: "Tudo" },
  { id: "gastos", rotulo: "Gastos" },
  { id: "entradas", rotulo: "Entradas" },
];

const ORIGENS = [
  { id: "todas", rotulo: "Todas" },
  { id: "avulso", rotulo: "Avulsos" },
  { id: "fixa", rotulo: "Fixos" },
  { id: "parcela", rotulo: "Parcelas" },
  { id: "previsto", rotulo: "Previstos" },
];

function origemDe(l) {
  if (l.tipo === "entrada") return l.entrada_fixa_id ? "fixa" : "avulso";
  if (l.projetado) return "previsto";
  if (l.compra_parcelada_id) return "parcela";
  if (l.despesa_fixa_id) return "fixa";
  return "avulso";
}

function tituloDe(l) {
  // Sem descrição (comum no lançamento rápido pelo bot): o nome da
  // categoria é um título melhor que "(sem descrição)".
  return l.descricao || l.categoria_nome || (l.tipo === "entrada" ? "Entrada" : "Gasto");
}

function metaDe(l) {
  if (l.tipo === "entrada") return ["Entrada", l.entrada_fixa_id ? "recorrente" : null];
  return [
    l.categoria_nome,
    l.forma_nome,
    l.membro_nome,
    l.compra_parcelada_id ? `parcela ${l.parcela_num}/${l.total_parcelas || "?"}` : null,
    l.despesa_fixa_id && !l.projetado ? "fixo" : null,
  ];
}

function visualDe(l) {
  return l.tipo === "entrada"
    ? { Icone: TrendingUp, cor: COR_ENTRADA, fundo: `${COR_ENTRADA}26` }
    : categoriaVisual(l.categoria_nome);
}

function normalizar(texto) {
  return String(texto || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
}

export default function LancamentosPage() {
  const [mes, setMes] = useState(mesAtualISO());
  const [tipo, setTipo] = useState("todos");
  const [origem, setOrigem] = useState("todas");
  const [busca, setBusca] = useState("");
  const [maisFiltros, setMaisFiltros] = useState(false);
  const [filtroCategoria, setFiltroCategoria] = useState(null);
  const [filtroForma, setFiltroForma] = useState(null);
  const [toast, setToast] = useState(null);

  const [selecionado, setSelecionado] = useState(null); // lançamento no painel
  const [excluindo, setExcluindo] = useState(null); // lançamento a excluir

  // Filtro de categoria/forma só existe em gasto — com um deles ativo, a
  // lista mostra só gastos (entrada nunca bateria com o filtro).
  const filtroDeGasto = !!(filtroCategoria || filtroForma);
  const mostraGastos = tipo !== "entradas";
  const mostraEntradas = tipo !== "gastos" && !filtroDeGasto;

  const urlGastos = useMemo(() => {
    // per_page 200 (máximo da API): a lista é o mês inteiro, sem paginação.
    const params = new URLSearchParams({ mes, per_page: "200" });
    if (filtroCategoria) params.set("categoria", filtroCategoria);
    if (filtroForma) params.set("forma", filtroForma);
    return `/gastos?${params.toString()}`;
  }, [mes, filtroCategoria, filtroForma]);

  const gastos = useApi(urlGastos, { skip: !mostraGastos });
  const entradas = useApi(`/entradas?mes=${mes}`, { skip: !mostraEntradas });
  const { refetch: refetchGastos } = gastos;
  const { refetch: refetchEntradas } = entradas;

  function recarregar() {
    refetchGastos({ silent: true });
    refetchEntradas({ silent: true });
  }

  // "Novo lançamento" é global (components/NovoLancamento, no layout) — a
  // lista recarrega quando ele avisa que salvou algo.
  useEffect(() => {
    function onSalvo() {
      refetchGastos({ silent: true });
      refetchEntradas({ silent: true });
    }
    window.addEventListener(EVENTO_LANCAMENTO_SALVO, onSalvo);
    return () => window.removeEventListener(EVENTO_LANCAMENTO_SALVO, onSalvo);
  }, [refetchGastos, refetchEntradas]);

  function avisar(mensagem, tipoToast = "sucesso") {
    setToast({ mensagem, tipo: tipoToast });
    setTimeout(() => setToast(null), 3000);
  }

  // ---- lista filtrada -----------------------------------------------------
  const lancamentos = useMemo(() => {
    const termo = normalizar(busca.trim());
    return [
      ...(mostraGastos ? gastos.dados?.itens || [] : []).map((g) => ({ ...g, tipo: "gasto" })),
      ...(mostraEntradas ? entradas.dados?.itens || [] : []).map((e) => ({ ...e, tipo: "entrada" })),
    ]
      .filter((l) => l.data)
      .filter((l) => origem === "todas" || origemDe(l) === origem)
      .filter((l) => {
        if (!termo) return true;
        const alvo = normalizar(
          [l.descricao, l.categoria_nome, l.forma_nome, l.membro_nome, brl(l.valor)].join(" ")
        );
        return termo.split(/\s+/).every((p) => alvo.includes(p));
      })
      .sort((a, b) => b.data.localeCompare(a.data) || String(b.id).localeCompare(String(a.id)));
  }, [gastos.dados, entradas.dados, mostraGastos, mostraEntradas, origem, busca]);

  const dias = useMemo(() => {
    const grupos = [];
    for (const l of lancamentos) {
      // A lista é por competência: parcela comprada em julho e fixa
      // lançada antes da virada caem neste mês com data de outro. Em vez
      // de um dia solto de julho no fim da lista, vão todas pra um grupo
      // só (lista já vem em data desc, então ele fica por último).
      const chave = l.data.slice(0, 7) < mes ? "anteriores" : l.data.slice(0, 10);
      let grupo = grupos[grupos.length - 1];
      if (!grupo || grupo.chave !== chave) {
        grupo = { chave, itens: [], saldo: 0, soPrevisto: true };
        grupos.push(grupo);
      }
      grupo.itens.push(l);
      if (!l.projetado) grupo.soPrevisto = false;
      grupo.saldo += l.tipo === "entrada" ? Number(l.valor) : -Number(l.valor);
    }
    return grupos;
  }, [lancamentos, mes]);

  const totais = useMemo(() => {
    const t = { entrou: 0, saiu: 0, previsto: 0, qtd: 0 };
    for (const l of lancamentos) {
      if (l.projetado) t.previsto += Number(l.valor);
      else if (l.tipo === "entrada") t.entrou += Number(l.valor);
      else t.saiu += Number(l.valor);
      t.qtd += 1;
    }
    return t;
  }, [lancamentos]);

  // `loading` só liga no fetch "de verdade" (troca de mês/filtro); o
  // recarregar depois de salvar é silent e não pisca o esqueleto.
  const carregando = (mostraGastos && gastos.loading) || (mostraEntradas && entradas.loading);
  const erroCarga = (mostraGastos && gastos.erro) || (mostraEntradas && entradas.erro);
  const temFiltro = tipo !== "todos" || origem !== "todas" || busca.trim() || filtroDeGasto;

  function limparFiltros() {
    setTipo("todos");
    setOrigem("todas");
    setBusca("");
    setFiltroCategoria(null);
    setFiltroForma(null);
  }

  // ---- exclusão -------------------------------------------------------------
  async function handleExcluir(escopo = "unico") {
    const alvo = excluindo;
    try {
      if (alvo.tipo === "gasto") {
        await api.delete(`/gastos/${alvo.id}${escopo === "compra" ? "?escopo=compra" : ""}`);
      } else {
        await api.delete(`/entradas/${alvo.id}`);
      }
      avisar(escopo === "compra" ? "Compra parcelada excluída." : "Lançamento excluído.");
      setExcluindo(null);
      recarregar();
    } catch (err) {
      avisar(err?.response?.data?.mensagem || "Não foi possível excluir.", "erro");
    }
  }

  // Excluir sai do painel: fecha o painel primeiro (o foco volta pra
  // linha) e abre a confirmação por cima da lista — dois diálogos
  // empilhados brigariam pelo Esc e pelo foco.
  function pedirExclusao(l) {
    setSelecionado(null);
    setExcluindo(l);
  }

  return (
    <div>
      <Header>
        <Titulo>Lançamentos</Titulo>
        <MesPicker value={mes} onChange={setMes} />
      </Header>

      <Barra>
        <Busca>
          <Search size={16} aria-hidden="true" />
          <label htmlFor="busca-lancamentos" className="sr-only">Buscar lançamentos</label>
          <input
            id="busca-lancamentos"
            type="search"
            placeholder="Buscar por descrição, categoria, valor…"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
          />
        </Busca>
        <MaisFiltrosBtn
          type="button"
          aria-expanded={maisFiltros}
          aria-controls="mais-filtros"
          onClick={() => setMaisFiltros((v) => !v)}
        >
          <SlidersHorizontal size={16} aria-hidden="true" />
          Mais filtros
          {filtroDeGasto && <Contador>{(filtroCategoria ? 1 : 0) + (filtroForma ? 1 : 0)}</Contador>}
        </MaisFiltrosBtn>
      </Barra>

      <ChipsLinha>
        <Chips role="group" aria-label="Tipo de lançamento">
          {TIPOS.map((t) => (
            <Chip key={t.id} type="button" aria-pressed={tipo === t.id} onClick={() => setTipo(t.id)}>
              {t.rotulo}
            </Chip>
          ))}
        </Chips>
        <Chips role="group" aria-label="Origem">
          {ORIGENS.map((o) => (
            <Chip key={o.id} type="button" aria-pressed={origem === o.id} onClick={() => setOrigem(o.id)}>
              {o.rotulo}
            </Chip>
          ))}
        </Chips>
      </ChipsLinha>

      {maisFiltros && (
        <Filtros id="mais-filtros">
          <FiltroCampo>
            <label htmlFor="filtro-categoria">Categoria</label>
            <CategoriaSelect id="filtro-categoria" value={filtroCategoria} onChange={setFiltroCategoria} incluirTodas apenasAtivas={false} />
          </FiltroCampo>
          <FiltroCampo>
            <label htmlFor="filtro-forma">Forma de pagamento</label>
            <FormaSelect id="filtro-forma" value={filtroForma} onChange={setFiltroForma} incluirTodas />
          </FiltroCampo>
          {filtroDeGasto && (
            <small>Com categoria ou forma escolhida, só aparecem gastos.</small>
          )}
        </Filtros>
      )}

      {!carregando && lancamentos.length > 0 && (
        <Resumo aria-label="Totais da lista">
          <ResumoItem>
            <span>Entrou</span>
            <strong data-tom="entrada">{brl(totais.entrou)}</strong>
          </ResumoItem>
          <ResumoItem>
            <span>Saiu</span>
            <strong>{brl(totais.saiu)}</strong>
          </ResumoItem>
          {totais.previsto > 0 && (
            <ResumoItem>
              <span>Previsto</span>
              <strong data-tom="muted">{brl(totais.previsto)}</strong>
            </ResumoItem>
          )}
          <ResumoItem>
            <span>Lançamentos</span>
            <strong>{totais.qtd}</strong>
          </ResumoItem>
        </Resumo>
      )}

      <Lista aria-busy={carregando || undefined}>
        {carregando ? (
          [0, 1, 2, 3, 4].map((i) => <SkeletonLinha key={i} />)
        ) : erroCarga && dias.length === 0 ? (
          <Vazio role="alert">
            <strong>Não foi possível carregar os lançamentos.</strong>
            <LimparBtn type="button" onClick={() => { refetchGastos(); refetchEntradas(); }}>
              Tentar de novo
            </LimparBtn>
          </Vazio>
        ) : dias.length === 0 ? (
          <Vazio>
            {temFiltro ? (
              <>
                <strong>Nada encontrado com esses filtros.</strong>
                <LimparBtn type="button" onClick={limparFiltros}>
                  <X size={14} aria-hidden="true" /> Limpar filtros
                </LimparBtn>
              </>
            ) : (
              <>
                <strong>Nenhum lançamento neste mês.</strong>
                <span>Registre pelo botão “Novo lançamento” ou mande uma mensagem pro bot no WhatsApp.</span>
              </>
            )}
          </Vazio>
        ) : (
          dias.map((dia) => (
            <Dia key={dia.chave} aria-labelledby={`dia-${dia.chave}`}>
              <DiaTopo>
                <h2 id={`dia-${dia.chave}`}>
                  {dia.chave === "anteriores" ? "Lançados antes deste mês" : rotuloDia(dia.chave)}
                </h2>
                <span data-tom={dia.soPrevisto ? "muted" : dia.saldo >= 0 ? "entrada" : undefined}>
                  {dia.saldo >= 0 ? "+" : "−"} {brl(Math.abs(dia.saldo))}
                </span>
              </DiaTopo>
              <ul>
                {dia.itens.map((l) => {
                  const visual = visualDe(l);
                  const entrada = l.tipo === "entrada";
                  const conteudo = (
                    <>
                      <Avatar style={{ background: visual.fundo, color: visual.cor }} aria-hidden="true">
                        <visual.Icone size={18} strokeWidth={2} />
                      </Avatar>
                      <LinhaTexto>
                        <LinhaTitulo>
                          {tituloDe(l)}
                          {l.projetado && <Selo>previsto</Selo>}
                        </LinhaTitulo>
                        <LinhaMeta>
                          {[dia.chave === "anteriores" ? formatarDataBR(l.data) : null, ...metaDe(l)]
                            .filter(Boolean).join(" · ")}
                        </LinhaMeta>
                      </LinhaTexto>
                      <Valor data-tom={entrada ? "entrada" : undefined}>
                        {entrada ? "+" : "−"} {brl(l.valor)}
                      </Valor>
                    </>
                  );
                  return (
                    <Linha key={`${l.tipo}-${l.id}`} $atenuada={!!l.projetado}>
                      {l.projetado ? (
                        <div className="conteudo" title="Custo fixo previsto — vira lançamento sozinho no dia">
                          {conteudo}
                        </div>
                      ) : (
                        <LinhaBtn type="button" onClick={() => setSelecionado(l)}>
                          {conteudo}
                        </LinhaBtn>
                      )}
                    </Linha>
                  );
                })}
              </ul>
            </Dia>
          ))
        )}
      </Lista>

      {selecionado && (
        <PainelLancamento
          key={`${selecionado.tipo}-${selecionado.id}`}
          item={selecionado}
          onFechar={() => setSelecionado(null)}
          onSalvo={() => {
            setSelecionado(null);
            avisar("Alterações salvas.");
            recarregar();
          }}
          onExcluir={() => pedirExclusao(selecionado)}
        />
      )}

      {excluindo && excluindo.compra_parcelada_id ? (
        <Modal aberto titulo="Excluir parcela" onFechar={() => setExcluindo(null)}>
          <p>
            Esse gasto é a parcela {excluindo.parcela_num}/{excluindo.total_parcelas || "?"} de uma
            compra parcelada. Excluir só essa parcela ou a compra inteira (todas as parcelas)?
          </p>
          <div style={{ display: "flex", gap: 8, marginTop: 16, justifyContent: "flex-end", flexWrap: "wrap" }}>
            <button onClick={() => setExcluindo(null)} data-autofocus>Cancelar</button>
            <button onClick={() => handleExcluir("unico")}>Excluir só esta parcela</button>
            <button onClick={() => handleExcluir("compra")}>Excluir compra inteira</button>
          </div>
        </Modal>
      ) : (
        <ConfirmDialog
          aberto={!!excluindo}
          titulo="Excluir lançamento"
          textoConfirmar="Excluir lançamento"
          mensagem={
            // Lançamento de custo fixo: a exclusão grava supressão no
            // backend (migração 026) — não volta nem como "previsto" — mas
            // a fixa segue lançando nos meses seguintes. Vale avisar, senão
            // parece que excluiu o custo fixo inteiro.
            excluindo?.despesa_fixa_id
              ? `"${tituloDe(excluindo)}" vem de um custo fixo. Excluir remove só este mês (não será relançado); o custo fixo continua ativo nos próximos meses.`
              : `Excluir "${excluindo ? tituloDe(excluindo) : ""}" de ${brl(excluindo?.valor)}? Não dá pra desfazer.`
          }
          onConfirmar={() => handleExcluir("unico")}
          onCancelar={() => setExcluindo(null)}
        />
      )}

      <Toast mensagem={toast?.mensagem} tipo={toast?.tipo} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Painel lateral: detalhe + edição de um lançamento
// ---------------------------------------------------------------------------

function PainelLancamento({ item, onFechar, onSalvo, onExcluir }) {
  const ehEntrada = item.tipo === "entrada";
  const [valor, setValor] = useState(item.valor);
  const [descricao, setDescricao] = useState(item.descricao || "");
  const [categoriaId, setCategoriaId] = useState(item.categoria_id);
  const [formaId, setFormaId] = useState(item.forma_pagamento_id);
  // Data editável só em gasto: services/entradas.py::atualizar_entrada não
  // aceita `data`. `item.data` pode vir com hora — o input quer 10 chars.
  const [data, setData] = useState(item.data ? item.data.slice(0, 10) : "");
  // Recorrência (entradas): parte do estado ATUAL do modelo (recorrente_ativa
  // vem do LEFT JOIN com entradas_fixas — entrada_fixa_id sozinho ficaria
  // marcado pra sempre mesmo depois de desativar).
  const [recorrente, setRecorrente] = useState(!!item.recorrente_ativa);
  const [diaLancamento, setDiaLancamento] = useState(
    item.recorrente_dia || (item.data ? Number(item.data.slice(8, 10)) : new Date().getDate())
  );
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  const visual = visualDe(item);
  const origem = {
    avulso: ehEntrada ? "Entrada avulsa" : "Gasto avulso",
    fixa: ehEntrada ? "Entrada recorrente" : "Custo fixo",
    parcela: `Parcela ${item.parcela_num}/${item.total_parcelas || "?"} de uma compra parcelada`,
  }[origemDe(item)];

  async function handleSubmit(e) {
    e.preventDefault();
    setErro("");
    if (!valor || valor <= 0) {
      setErro("Informe um valor maior que zero.");
      return;
    }
    setEnviando(true);
    try {
      if (ehEntrada) {
        await api.put(`/entradas/${item.id}`, {
          valor, descricao,
          // Só envia recorrência se mudou — evita mexer no modelo quando a
          // pessoa só corrigiu o valor de uma entrada avulsa.
          ...(recorrente !== !!item.recorrente_ativa || (recorrente && diaLancamento !== item.recorrente_dia)
            ? { recorrente, dia_lancamento: diaLancamento }
            : {}),
        });
      } else {
        await api.put(`/gastos/${item.id}`, {
          valor, descricao, categoria_id: categoriaId, forma_pagamento_id: formaId,
          // Sem "data" quando não mudou, pra não recalcular a competência
          // à toa (services/gastos.py::atualizar_gasto).
          ...(data && data !== item.data?.slice(0, 10) ? { data } : {}),
        });
      }
      onSalvo();
    } catch (err) {
      setErro(err?.response?.data?.mensagem || "Não foi possível salvar.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Painel
      aberto
      titulo={tituloDe(item)}
      subtitulo={`${formatarDataBR(item.data)} · ${origem}`}
      onFechar={onFechar}
      rodape={
        <>
          <ExcluirBtn type="button" onClick={onExcluir}>Excluir</ExcluirBtn>
          <SalvarBtn type="submit" form="form-lancamento" disabled={enviando}>
            {enviando ? "Salvando…" : "Salvar alterações"}
          </SalvarBtn>
        </>
      }
    >
      <PainelValor>
        <Avatar style={{ background: visual.fundo, color: visual.cor }} aria-hidden="true">
          <visual.Icone size={20} strokeWidth={2} />
        </Avatar>
        <strong data-tom={ehEntrada ? "entrada" : undefined}>
          {ehEntrada ? "+" : "−"} {brl(item.valor)}
        </strong>
      </PainelValor>
      {item.membro_nome && <PainelInfo>Lançado por {item.membro_nome}</PainelInfo>}

      <Form id="form-lancamento" onSubmit={handleSubmit}>
        <Field>
          <label htmlFor="valor-edit">Valor</label>
          <MoneyInput id="valor-edit" value={valor} onChange={setValor} />
        </Field>
        <Field>
          <label htmlFor="descricao-edit">Descrição</label>
          <input id="descricao-edit" value={descricao} onChange={(e) => setDescricao(e.target.value)} />
        </Field>
        {ehEntrada ? (
          <>
            <Field>
              <label>
                <input type="checkbox" checked={recorrente} onChange={(e) => setRecorrente(e.target.checked)} />
                {" "}Recorrente (cai todo mês — ex: salário)
              </label>
              {!!item.recorrente_ativa && !recorrente && (
                <small style={{ opacity: 0.75 }}>
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
        ) : (
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
        {erro && <Erro role="alert">{erro}</Erro>}
      </Form>
    </Painel>
  );
}
