"use client";

// app/(app)/contas/page.jsx — board "contas do mês" (pedido do Lucas,
// 24/07/2026): substitui a planilha em que ele controlava, mês a mês, o que
// ainda precisa pagar e o que já pagou.
//
// Este board raciocina em CAIXA, não em competência — é a diferença pro
// resto do app. A fatura que fechou em 28/07 aparece como conta de AGOSTO,
// porque é em agosto que o dinheiro sai. Quem decide isso é o backend
// (services/contas_mes.py); aqui só se exibe o que ele mandou.
//
// Duas naturezas de card, propositalmente indistinguíveis pra quem usa: um
// boleto é 1 gasto no banco, uma fatura é N gastos somados. O backend manda
// uma `chave` opaca ("gasto:12" / "fatura:5:2026-07-01") e a tela só devolve
// a mesma chave — nada de lógica de cartão do lado do browser.
import { useEffect, useMemo, useState } from "react";
import { useApi } from "@/hooks/useApi";
import api from "@/services/api";
import { brl, formatarCompetencia, formatarDataBR, parseValorBR } from "@/utils/format";
import MesPicker from "@/components/MesPicker";
import Loading from "@/components/Loading";
import StatCard from "@/components/StatCard";
import Toast from "@/components/Toast";
import Modal from "@/components/Modal";
import MoneyInput from "@/components/MoneyInput";
import {
  Header, Board, Coluna, ColunaHeader, ColunaTitulo, ColunaTotal, Card,
  CardInfo, CardTitulo, CardDetalhe, CardValor, ValorRiscado, BotaoMover, Indicador,
  InputValor, Vazio, Resumo, ListaDetalhe, ItemDetalhe,
  BotaoNovaEntrada, FormNovaEntrada, CampoDia,
} from "./styles";

// Mesmo truque de despesas fixas (fixas/page.jsx): dia_lancamento=31 num
// mês de 30 dias cai no último dia do mês, não "data inválida".
function ultimoDiaDoMes(mesISO) {
  const [ano, mesNum] = mesISO.split("-").map(Number);
  return new Date(ano, mesNum, 0).getDate();
}

function mesAtualISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

// Pedido do Lucas (24/07/2026): "deve ser salvo qual foi o último mês
// consultado". Guarda só o mês, não os dados — reabrir a tela sempre busca
// de novo, só não força a pessoa a navegar de volta pro mês que estava
// vendo (ex: revisando julho de propósito, sai da tela, volta: continua em
// julho, não pula pro mês corrente).
const CHAVE_ULTIMO_MES = "finbot:contas:ultimo-mes";

// ---------------------------------------------------------------------------
// Ordem preferida dos cards (pedido do Lucas, 24/07/2026: "quero também
// poder mover os cards pra deixar na ordem que eu preferir de
// visualização"). Preferência de TELA, não de dado — guardada só no
// navegador (localStorage), por mês+coluna. Decisão consciente: não criei
// tabela/migração nova pra isso. É ordem de exibição, não estado de
// negócio (diferente de `pago`, que precisa existir no servidor pra
// resumo.py/dashboard concordarem); duplicar isso no backend agora seria
// resolver um problema que não apareceu ainda ("preciso ver a mesma ordem
// no celular e no computador"). Se aparecer, migra pra lá.
// ---------------------------------------------------------------------------

function chaveOrdemStorage(mesRef, coluna) {
  return `finbot:contas:ordem:${mesRef}:${coluna}`;
}

function lerOrdemSalva(mesRef, coluna) {
  if (typeof window === "undefined") return [];
  try {
    const bruto = window.localStorage.getItem(chaveOrdemStorage(mesRef, coluna));
    const lista = bruto ? JSON.parse(bruto) : [];
    return Array.isArray(lista) ? lista : [];
  } catch {
    return [];
  }
}

function salvarOrdemStorage(mesRef, coluna, chaves) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(chaveOrdemStorage(mesRef, coluna), JSON.stringify(chaves));
}

// Pura, testável isoladamente: aplica a ordem salva por cima da ordem que
// já veio do backend. Card sem posição salva (conta nova, nunca
// reordenada) mantém a posição relativa que já tinha, só empurrado pro
// fim — não "pula" pro topo por não ter preferência registrada ainda.
function ordenarPorPreferencia(itens, ordemSalva) {
  if (!itens || itens.length === 0 || !ordemSalva || ordemSalva.length === 0) return itens || [];
  const posicao = new Map(ordemSalva.map((chave, i) => [chave, i]));
  return [...itens].sort((a, b) => {
    const pa = posicao.has(a.chave) ? posicao.get(a.chave) : Infinity;
    const pb = posicao.has(b.chave) ? posicao.get(b.chave) : Infinity;
    return pa - pb;
  });
}

// "entrada:9" -> "entrada". Decide se uma coluna aceita o card largado
// nela — impede que um gasto arrastado sem querer pra dentro da coluna
// Entradas (ou vice-versa) tente aplicar status de pago numa entrada
// (rejeitado com 400 pelo backend) ou vire uma entrada fantasma na lista
// de não-pagos.
function tipoDaChave(chave) {
  return (chave || "").split(":")[0];
}
function colunaAceitaChave(coluna, chave) {
  return coluna === "entradas"
    ? tipoDaChave(chave) === "entrada"
    : tipoDaChave(chave) !== "entrada";
}

export default function ContasPage() {
  // Começa sempre com o mês atual — igual no servidor (SSR) e no 1º render
  // do cliente, pra não divergir (localStorage só existe no browser). Um
  // useEffect logo abaixo troca pro mês salvo assim que a página monta.
  const [mes, setMes] = useState(mesAtualISO());
  useEffect(() => {
    const salvo = window.localStorage.getItem(CHAVE_ULTIMO_MES);
    if (salvo && /^\d{4}-\d{2}$/.test(salvo)) setMes(salvo);
  }, []);
  useEffect(() => {
    window.localStorage.setItem(CHAVE_ULTIMO_MES, mes);
  }, [mes]);

  const url = useMemo(() => `/contas?mes=${mes}`, [mes]);
  const { dados, loading, refetch } = useApi(url);

  // `local` é o que a tela desenha; `dados` é a última resposta confirmada
  // pelo servidor. Arrastar/editar mexe em `local` NA HORA (otimista) — o
  // card já pula de coluna antes da rede responder, sem passar pelo
  // <Loading/>. `dados` só entra de novo quando o servidor confirma (via
  // refetch silencioso) ou quando dá erro (aí `local` volta a ser `dados`,
  // desfazendo o palpite). Sincroniza sempre que `dados` muda de verdade —
  // troca de mês, 1ª carga, ou a reconciliação depois de um PATCH.
  const [local, setLocal] = useState(null);
  useEffect(() => setLocal(dados), [dados]);

  const [toast, setToast] = useState(null);
  const [arrastando, setArrastando] = useState(null); // chave do card em voo
  const [colunaAlvo, setColunaAlvo] = useState(null); // "entradas" | "a_pagar" | "pagas"
  const [salvando, setSalvando] = useState(null);
  const [detalheChave, setDetalheChave] = useState(null); // fatura aberta no modal

  // Ordem preferida de cada coluna (ver bloco de comentário acima) — recarrega
  // do localStorage sempre que troca de mês, porque a preferência é por mês.
  const [ordens, setOrdens] = useState({ entradas: [], a_pagar: [], pagas: [] });
  useEffect(() => {
    setOrdens({
      entradas: lerOrdemSalva(mes, "entradas"),
      a_pagar: lerOrdemSalva(mes, "a_pagar"),
      pagas: lerOrdemSalva(mes, "pagas"),
    });
  }, [mes]);

  function avisar(mensagem, tipo = "sucesso") {
    setToast({ mensagem, tipo });
    setTimeout(() => setToast(null), 3000);
  }

  async function mover(conta, pago) {
    if (!conta.editavel) return; // linha "previsto" não existe no banco ainda
    setSalvando(conta.chave);
    setLocal((atual) => moverLocal(atual, conta.chave, pago));
    try {
      await api.patch(`/contas/${conta.chave}`, { pago });
      // Silencioso: confirma com o número exato do backend (uma fatura
      // pode ter fixas previstas somadas, que o palpite local não sabe
      // calcular) sem acionar o <Loading/> — só troca os números.
      refetch({ silent: true });
      avisar(pago ? "Marcado como pago." : "Devolvido para não pagos.");
    } catch (err) {
      setLocal(dados); // desfaz o palpite: volta pro último estado confirmado
      avisar(err?.response?.data?.mensagem || "Não foi possível atualizar.", "erro");
    } finally {
      setSalvando(null);
    }
  }

  async function salvarValor(conta, valor) {
    if (valor === null || Number(valor) === Number(conta.valor_pago ?? conta.valor)) return;
    setSalvando(conta.chave);
    setLocal((atual) => editarValorLocal(atual, conta, valor));
    try {
      await api.patch(`/contas/${conta.chave}`, { valor });
      refetch({ silent: true });
      avisar("Valor atualizado.");
    } catch (err) {
      setLocal(dados);
      avisar(err?.response?.data?.mensagem || "Não foi possível salvar o valor.", "erro");
    } finally {
      setSalvando(null);
    }
  }

  const dadosExibidos = local;
  const totais = dadosExibidos?.totais;

  // Ordem de exibição = ordem do backend, com a preferência salva aplicada
  // por cima (ver ordenarPorPreferencia). Recalculado a cada render — as
  // listas são pequenas (dezenas de cards, não milhares), não vale a pena
  // memoizar às custas de mais uma dependência pra manter sincronizada.
  const entradasOrdenadas = ordenarPorPreferencia(dadosExibidos?.entradas, ordens.entradas);
  const aPagarOrdenadas = ordenarPorPreferencia(dadosExibidos?.a_pagar, ordens.a_pagar);
  const pagasOrdenadas = ordenarPorPreferencia(dadosExibidos?.pagas, ordens.pagas);

  // Handler único pro arraste — usado tanto ao soltar no fundo vazio de uma
  // coluna (chaveAlvo=null, vai pro fim) quanto ao soltar EM CIMA de outro
  // card (chaveAlvo=a chave dele, entra antes/depois conforme a metade em
  // que soltou). Reordenar é sempre local (localStorage); só dispara
  // `mover()` pro servidor quando a coluna de destino é diferente da atual
  // do card — mesma regra de sempre, só que agora reaproveitada nos dois
  // caminhos de soltar (fundo da coluna e em cima de um card).
  function soltar(coluna, chaveArrastada, chaveAlvo, depoisDoAlvo) {
    if (!chaveArrastada || chaveArrastada === chaveAlvo) return;
    if (!colunaAceitaChave(coluna, chaveArrastada)) return;

    const listaAtual = coluna === "entradas" ? entradasOrdenadas
      : coluna === "a_pagar" ? aPagarOrdenadas
      : pagasOrdenadas;

    const chavesDestino = listaAtual.map((c) => c.chave).filter((k) => k !== chaveArrastada);
    let indice = chaveAlvo ? chavesDestino.indexOf(chaveAlvo) : chavesDestino.length;
    if (indice === -1) indice = chavesDestino.length;
    if (chaveAlvo && depoisDoAlvo) indice += 1;
    chavesDestino.splice(indice, 0, chaveArrastada);

    setOrdens((atual) => ({ ...atual, [coluna]: chavesDestino }));
    salvarOrdemStorage(mes, coluna, chavesDestino);

    if (coluna !== "entradas") {
      const conta = [...(local?.a_pagar || []), ...(local?.pagas || [])]
        .find((c) => c.chave === chaveArrastada);
      const querPago = coluna === "pagas";
      if (conta && conta.pago !== querPago) mover(conta, querPago);
    }
  }

  // Drag nativo do HTML5 (sem dependência nova). Só funciona com mouse — em
  // toque o caminho é o BotaoMover de cada card, que faz exatamente a mesma
  // chamada pra status; reordenar por toque não tem equivalente ainda (ver
  // nota na próxima seção). Decisão consciente: @dnd-kit resolveria o
  // toque, mas é uma dependência a mais pra um gesto que hoje só falta no
  // celular, não no uso principal (desktop).
  function propsColuna(coluna) {
    return {
      onDragOver: (e) => {
        e.preventDefault();
        setColunaAlvo(coluna);
      },
      onDragLeave: () => setColunaAlvo((atual) => (atual === coluna ? null : atual)),
      onDrop: (e) => {
        e.preventDefault();
        setColunaAlvo(null);
        const chave = e.dataTransfer.getData("text/plain") || arrastando;
        setArrastando(null);
        soltar(coluna, chave, null, false); // sem alvo = solta no fim da coluna
      },
      $alvo: colunaAlvo === coluna && arrastando !== null,
    };
  }

  return (
    <div>
      <Header>
        <div>
          <h1 style={{ fontSize: 20 }}>Contas do mês</h1>
          <p style={{ fontSize: 13, opacity: 0.7, marginTop: 4 }}>
            O que sai do bolso neste mês — fixas em boleto e faturas que vencem
            agora. Compras no débito/pix não entram: já foram pagas na hora.
          </p>
        </div>
        <MesPicker value={mes} onChange={setMes} />
      </Header>

      {loading || !dadosExibidos ? (
        <Loading />
      ) : (
        <>
          <Resumo>
            <StatCard label="Entradas" valor={brl(totais.entradas)} tom="sucesso" />
            <StatCard label="Total de saídas" valor={brl(totais.saidas)} tom="erro" />
            <StatCard
              label="Falta pagar"
              valor={brl(totais.a_pagar)}
              detalhe={`${brl(totais.pago)} já pago`}
              tom={totais.a_pagar > 0 ? "erro" : "sucesso"}
            />
            <StatCard
              label="Sobra do mês"
              valor={brl(totais.sobra)}
              tom={totais.sobra >= 0 ? "sucesso" : "erro"}
            />
          </Resumo>

          <Board>
            <Coluna {...propsColuna("entradas")}>
              <ColunaHeader>
                <ColunaTitulo>Entradas</ColunaTitulo>
                <ColunaTotal $tom="sucesso">{brl(totais.entradas)}</ColunaTotal>
              </ColunaHeader>
              {entradasOrdenadas.length === 0 ? (
                <Vazio>Nenhuma entrada lançada neste mês.</Vazio>
              ) : (
                entradasOrdenadas.map((e) => (
                  <CardConta
                    key={e.chave}
                    conta={e}
                    arrastando={arrastando === e.chave}
                    salvando={salvando === e.chave}
                    onArrastar={setArrastando}
                    onMover={() => {}}
                    onSalvarValor={(v) => salvarValor(e, v)}
                    onAbrirDetalhe={() => {}}
                    onSoltarSobre={(chaveAlvo, chaveArrastada, depois) =>
                      soltar("entradas", chaveArrastada, chaveAlvo, depois)}
                  />
                ))
              )}
              <NovaEntrada mes={mes} onCriada={() => refetch({ silent: true })} onErro={(m) => avisar(m, "erro")} />
            </Coluna>

            <Coluna {...propsColuna("a_pagar")}>
              <ColunaHeader>
                <ColunaTitulo>Não pagos</ColunaTitulo>
                <ColunaTotal $tom="erro">{brl(totais.a_pagar)}</ColunaTotal>
              </ColunaHeader>
              {aPagarOrdenadas.length === 0 ? (
                <Vazio>Tudo pago neste mês.</Vazio>
              ) : (
                aPagarOrdenadas.map((c) => (
                  <CardConta
                    key={c.chave}
                    conta={c}
                    arrastando={arrastando === c.chave}
                    salvando={salvando === c.chave}
                    onArrastar={setArrastando}
                    onMover={() => mover(c, true)}
                    onSalvarValor={(v) => salvarValor(c, v)}
                    onAbrirDetalhe={setDetalheChave}
                    onSoltarSobre={(chaveAlvo, chaveArrastada, depois) =>
                      soltar("a_pagar", chaveArrastada, chaveAlvo, depois)}
                  />
                ))
              )}
            </Coluna>

            <Coluna {...propsColuna("pagas")}>
              <ColunaHeader>
                <ColunaTitulo>Pagos</ColunaTitulo>
                <ColunaTotal $tom="sucesso">{brl(totais.pago)}</ColunaTotal>
              </ColunaHeader>
              {pagasOrdenadas.length === 0 ? (
                <Vazio>Arraste uma conta para cá quando pagar.</Vazio>
              ) : (
                pagasOrdenadas.map((c) => (
                  <CardConta
                    key={c.chave}
                    conta={c}
                    arrastando={arrastando === c.chave}
                    salvando={salvando === c.chave}
                    onArrastar={setArrastando}
                    onMover={() => mover(c, false)}
                    onSalvarValor={(v) => salvarValor(c, v)}
                    onAbrirDetalhe={setDetalheChave}
                    onSoltarSobre={(chaveAlvo, chaveArrastada, depois) =>
                      soltar("pagas", chaveArrastada, chaveAlvo, depois)}
                  />
                ))
              )}
            </Coluna>
          </Board>
        </>
      )}

      <DetalheFatura chave={detalheChave} onFechar={() => setDetalheChave(null)} />

      <Toast mensagem={toast?.mensagem} tipo={toast?.tipo} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Modal de detalhe — pedido do Lucas (24/07/2026): "se eu clicar no Cartão,
// ele abre as despesas do cartão no mês". Busca sob demanda (só quando abre;
// `useApi(chave ? ... : null)` some ao fechar) em vez de vir junto com o
// board inteiro — o board já carrega N linhas de fatura, e a maioria nunca é
// clicada; buscar o detalhe de todas de cara seria trabalho jogado fora.
function DetalheFatura({ chave, onFechar }) {
  const url = chave ? `/contas/${chave}/detalhe` : null;
  const { dados, loading } = useApi(url, { skip: !chave });

  return (
    <Modal aberto={!!chave} titulo={dados ? `Fatura ${dados.forma_nome}` : "Fatura"} onFechar={onFechar}>
      {loading || !dados ? (
        <Loading />
      ) : (
        <>
          <ListaDetalhe>
            {dados.itens.map((item) => (
              <ItemDetalhe key={item.id}>
                <div>
                  <div>{item.descricao || "(sem descrição)"}</div>
                  <CardDetalhe>
                    {formatarDataBR(item.data)}
                    {item.categoria_nome ? ` · ${item.categoria_nome}` : ""}
                    {item.total_parcelas ? ` · parcela` : ""}
                  </CardDetalhe>
                </div>
                <span>{brl(item.valor)}</span>
              </ItemDetalhe>
            ))}
          </ListaDetalhe>
          <ItemDetalhe style={{ fontWeight: 600, marginTop: 8 }}>
            <span>Total</span>
            <span>{brl(dados.total)}</span>
          </ItemDetalhe>
        </>
      )}
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Palpite local (otimista) — move/edita ANTES do servidor confirmar, pra
// arrastar não esperar um round-trip pra reagir. Reproduz a MESMA fórmula
// de totais de services/contas_mes.py::listar_contas_mes (a_pagar = soma
// dos não pagos; pago = soma de valor_pago quando existe, senão valor;
// saidas/sobra derivados). Duplicar essa conta no front é uma concessão
// consciente pela resposta instantânea — o refetch silencioso logo depois
// busca o número exato do backend (que sabe de fixas previstas somadas na
// fatura, por exemplo) e corrige qualquer diferença sem o usuário notar.
function recalcularTotais(entradas, aPagar, pagas) {
  const totalEntradas = entradas.reduce((s, e) => s + Number(e.valor), 0);
  const totalAPagar = aPagar.reduce((s, c) => s + Number(c.valor), 0);
  const totalPago = pagas.reduce(
    (s, c) => s + Number(c.valor_pago != null ? c.valor_pago : c.valor), 0
  );
  return {
    entradas: totalEntradas,
    a_pagar: totalAPagar,
    pago: totalPago,
    saidas: totalAPagar + totalPago,
    sobra: totalEntradas - (totalAPagar + totalPago),
  };
}

function moverLocal(board, chave, pago) {
  if (!board) return board;
  const todas = [...board.a_pagar, ...board.pagas];
  const conta = todas.find((c) => c.chave === chave);
  if (!conta) return board;

  const atualizada = { ...conta, pago, pago_em: pago ? new Date().toISOString() : null };
  const aPagar = board.a_pagar.filter((c) => c.chave !== chave);
  const pagas = board.pagas.filter((c) => c.chave !== chave);
  (pago ? pagas : aPagar).push(atualizada);

  return { ...board, a_pagar: aPagar, pagas, totais: recalcularTotais(board.entradas, aPagar, pagas) };
}

function editarValorLocal(board, conta, valor) {
  if (!board) return board;

  if (conta.tipo === "entrada") {
    const entradas = board.entradas.map((e) => (e.chave === conta.chave ? { ...e, valor } : e));
    return { ...board, entradas, totais: recalcularTotais(entradas, board.a_pagar, board.pagas) };
  }

  const aplica = (lista) => lista.map((c) => {
    if (c.chave !== conta.chave) return c;
    // Fatura: o valor exibido some de `valor_pago` quando ela está paga —
    // editar mexe ali, nunca em `valor` (que é a soma real dos gastos).
    return conta.tipo === "fatura" ? { ...c, valor_pago: valor } : { ...c, valor };
  });
  const aPagar = aplica(board.a_pagar);
  const pagas = aplica(board.pagas);
  return { ...board, a_pagar: aPagar, pagas, totais: recalcularTotais(board.entradas, aPagar, pagas) };
}

// ---------------------------------------------------------------------------
// Nova entrada dentro do mês do board (pedido do Lucas, 24/07/2026): antes
// só dava pra criar entrada pela tela de Lançamentos, que sempre data com
// HOJE — sem jeito de já lançar o salário de agosto navegando em julho.
// `data` vai explícita no POST (services/entradas.py::registrar_entrada
// ganhou esse parâmetro; sem ele, sempre caía no DEFAULT NOW() da coluna).
// ---------------------------------------------------------------------------

function NovaEntrada({ mes, onCriada, onErro }) {
  const diaPadrao = mes === mesAtualISO() ? new Date().getDate() : 1;
  const [aberto, setAberto] = useState(false);
  const [descricao, setDescricao] = useState("");
  const [valor, setValor] = useState(0);
  const [dia, setDia] = useState(diaPadrao);
  const [enviando, setEnviando] = useState(false);

  function abrir() {
    setDescricao("");
    setValor(0);
    setDia(diaPadrao);
    setAberto(true);
  }

  async function salvar(e) {
    e.preventDefault();
    if (!valor || valor <= 0) return;
    setEnviando(true);
    try {
      const diaValido = Math.min(Math.max(1, Number(dia) || 1), ultimoDiaDoMes(mes));
      await api.post("/entradas", {
        valor, descricao, data: `${mes}-${String(diaValido).padStart(2, "0")}`,
      });
      setAberto(false);
      onCriada();
    } catch (err) {
      onErro(err?.response?.data?.mensagem || "Não foi possível criar a entrada.");
    } finally {
      setEnviando(false);
    }
  }

  if (!aberto) {
    return (
      <BotaoNovaEntrada type="button" onClick={abrir}>
        + Nova entrada em {formatarCompetencia(`${mes}-01`)}
      </BotaoNovaEntrada>
    );
  }

  return (
    <FormNovaEntrada onSubmit={salvar}>
      <input
        placeholder="Descrição" value={descricao} autoFocus
        onChange={(e) => setDescricao(e.target.value)}
      />
      <MoneyInput value={valor} onChange={setValor} />
      <CampoDia
        type="number" min={1} max={31} value={dia} title="Dia do mês"
        onChange={(e) => setDia(e.target.value)}
      />
      <button type="submit" disabled={enviando}>{enviando ? "..." : "Salvar"}</button>
      <button type="button" onClick={() => setAberto(false)}>Cancelar</button>
    </FormNovaEntrada>
  );
}

function CardConta({
  conta, arrastando, salvando, onArrastar, onMover, onSalvarValor, onAbrirDetalhe, onSoltarSobre,
}) {
  const [editando, setEditando] = useState(false);
  const [texto, setTexto] = useState("");
  const temDetalhe = conta.tipo === "fatura"; // só fatura resume N gastos por trás
  // Entrada não tem status de pago (dinheiro que entra não fica "a pagar")
  // — services/contas_mes.py::marcar_conta rejeita essa chave com 400, então
  // nem oferece o botão aqui: não é um controle desabilitado à toa, é um
  // controle que não existe pra esse tipo. Isso NÃO impede arrastar — só
  // impede que arrastar mude status; reordenar (pedido do Lucas, 24/07/2026)
  // vale pra qualquer card, entrada inclusive.
  const temStatusPago = conta.tipo !== "entrada";

  const arrastavel = conta.editavel && !salvando;
  // Numa fatura, o valor só vira editável DEPOIS de paga: antes disso o
  // número exibido é a soma real dos lançamentos, e "quanto pretendo pagar"
  // não é um dado (o backend recusa com 409 — services/contas_mes.py).
  // Entrada é sempre editável (não tem esse impasse — só existe 1 valor).
  const podeEditarValor =
    conta.editavel && (conta.tipo !== "fatura" || conta.pago);

  const valorExibido = conta.valor_pago != null ? conta.valor_pago : conta.valor;

  function abrirEdicao() {
    if (!podeEditarValor) return;
    setTexto(
      Number(valorExibido).toLocaleString("pt-BR", {
        minimumFractionDigits: 2, maximumFractionDigits: 2,
      })
    );
    setEditando(true);
  }

  function confirmar() {
    setEditando(false);
    onSalvarValor(parseValorBR(texto));
  }

  return (
    <Card
      $origem={conta.origem}
      $arrastando={arrastando}
      $arrastavel={arrastavel}
      draggable={arrastavel}
      onDragStart={(e) => {
        e.dataTransfer.setData("text/plain", conta.chave);
        e.dataTransfer.effectAllowed = "move";
        onArrastar(conta.chave);
      }}
      onDragEnd={() => onArrastar(null)}
      // Soltar EM CIMA de outro card reordena (em vez de só ir pro fundo
      // da coluna, que é o que o onDrop da Coluna já cobria). stopPropagation
      // pra não disparar os dois handlers pro mesmo gesto — sem isso, o
      // drop seria tratado 2x (reordenar aqui E "soltar no fundo" na Coluna).
      onDragOver={(e) => {
        e.preventDefault();
        e.stopPropagation();
      }}
      onDrop={(e) => {
        e.preventDefault();
        e.stopPropagation();
        const chaveArrastada = e.dataTransfer.getData("text/plain");
        if (!chaveArrastada || chaveArrastada === conta.chave) return;
        const rect = e.currentTarget.getBoundingClientRect();
        const depois = e.clientY > rect.top + rect.height / 2;
        onSoltarSobre(conta.chave, chaveArrastada, depois);
      }}
    >
      {temStatusPago && (
        <BotaoMover
          disabled={!conta.editavel || salvando}
          onClick={onMover}
          title={conta.pago ? "Marcar como não pago" : "Marcar como pago"}
          aria-label={conta.pago ? "Marcar como não pago" : "Marcar como pago"}
        >
          <Indicador $pago={conta.pago}>{conta.pago ? "✓" : ""}</Indicador>
        </BotaoMover>
      )}

      <CardInfo
        onClick={temDetalhe ? () => onAbrirDetalhe(conta.chave) : undefined}
        style={temDetalhe ? { cursor: "pointer" } : undefined}
        title={temDetalhe ? "Ver despesas do cartão neste mês" : undefined}
      >
        <CardTitulo>
          {conta.descricao}
          {temDetalhe && <span style={{ opacity: 0.5, fontWeight: 400 }}> ›</span>}
        </CardTitulo>
        <CardDetalhe>
          {conta.tipo === "entrada"
            ? formatarDataBR(conta.data)
            : (conta.vencimento ? `vence ${formatarDataBR(conta.vencimento)} · ` : "") + (conta.detalhe || "")}
        </CardDetalhe>
      </CardInfo>

      {editando ? (
        <InputValor
          autoFocus
          inputMode="decimal"
          value={texto}
          onChange={(e) => setTexto(e.target.value.replace(/[^\d.,]/g, ""))}
          onBlur={confirmar}
          onKeyDown={(e) => {
            if (e.key === "Enter") confirmar();
            if (e.key === "Escape") setEditando(false);
          }}
        />
      ) : (
        <CardValor
          as={podeEditarValor ? "button" : "span"}
          $editavel={podeEditarValor}
          onClick={abrirEdicao}
          title={podeEditarValor ? "Clique para editar" : undefined}
        >
          {/* Fatura paga com valor diferente do que fechou: mostra os dois,
              porque a diferença (rotativo, desconto) é justamente o que
              interessa enxergar. */}
          {conta.valor_pago != null && conta.valor_pago !== conta.valor && (
            <ValorRiscado>{brl(conta.valor)}</ValorRiscado>
          )}
          {brl(valorExibido)}
        </CardValor>
      )}
    </Card>
  );
}
