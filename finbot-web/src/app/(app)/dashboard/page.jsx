"use client";

// app/(app)/dashboard/page.jsx — tela "Início" (redesign de 05/11/2026).
//
// Antes: 6 StatCards do mesmo tamanho + 3 gráficos. Agora, seguindo o que
// Copilot/Monarch/Mobills fazem, a tela responde em ordem de importância:
//   1. quanto sobra no mês (número principal + barra de quanto da renda
//      já está comprometida);
//   2. o que vence nos próximos dias (vem do board de /contas);
//   3. onde foi o dinheiro (barras por categoria + fixo × variável);
//   4. últimos lançamentos, agrupados por dia;
//   5. comparativo dos últimos 6 meses (com o popup de detalhe de antes).
//
// Cada bloco tem seu próprio request: o Flask local leva segundos por
// endpoint, e um bloco lento não deve segurar a tela inteira.
// Agregações continuam no backend (decisão D6) — o front só ordena/corta.
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, CircleAlert, CircleCheck, TrendingUp } from "lucide-react";
import { useApi } from "@/hooks/useApi";
import { brl, formatarCompetencia, formatarDataBR } from "@/utils/format";
import { mesAtualISO, diasAte, rotuloDia } from "@/utils/datas";
import { categoriaVisual, CORES_CATEGORIA, COR_ENTRADA } from "@/utils/categoriaVisual";
import ChartComparativo from "@/components/ChartComparativo";
import MesPicker from "@/components/MesPicker";
import Loading from "@/components/Loading";
import Modal from "@/components/Modal";
import { EVENTO_LANCAMENTO_SALVO } from "@/components/NovoLancamento";
import {
  Header, Titulo, Hero, HeroRotulo, HeroValor, HeroBarra, HeroBarraCheia, HeroLegenda,
  Chips, Chip, Grade, Bloco, BlocoTopo, BlocoTitulo, LinkVerTodos, LinhaConta, ContaNome,
  ContaPrazo, Valor, CatLinha, CatNome, CatTrilho, CatBarra, CatValor, Divisao, DivisaoBarra,
  DivisaoLegenda, Dia, DiaTopo, Lancamento, Avatar, LancTexto, LancTitulo, LancMeta,
  Vazio, TudoPago, SkeletonLinha, ChartCard, ChartTitulo,
  ListaDetalhe, ItemDetalhe, TextoMuted, GrupoForma, ItemAninhado,
} from "./styles";

function nomeMes(mes) {
  return formatarCompetencia(`${mes}-01`).split("/")[0].toLowerCase();
}

function textoPrazo(dias, iso) {
  if (dias == null) return { texto: "sem data", tom: "neutro" };
  if (dias < 0) return { texto: dias === -1 ? "venceu ontem" : `venceu há ${-dias} dias`, tom: "perigo" };
  if (dias === 0) return { texto: "vence hoje", tom: "alerta" };
  if (dias === 1) return { texto: "vence amanhã", tom: "alerta" };
  if (dias <= 7) return { texto: `em ${dias} dias`, tom: "neutro" };
  return { texto: `dia ${iso.slice(8, 10)}`, tom: "neutro" };
}

// Recarrega os blocos quando o modal global de novo lançamento salva algo.
function useRecarregarAoLancar(...refetches) {
  useEffect(() => {
    const onSalvo = () => refetches.forEach((r) => r({ silent: true }));
    window.addEventListener(EVENTO_LANCAMENTO_SALVO, onSalvo);
    return () => window.removeEventListener(EVENTO_LANCAMENTO_SALVO, onSalvo);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, refetches);
}

export default function InicioPage() {
  const [mes, setMes] = useState(mesAtualISO());
  const resumo = useApi(useMemo(() => `/resumo?mes=${mes}`, [mes]));
  const contas = useApi(useMemo(() => `/contas?mes=${mes}`, [mes]));
  const gastos = useApi(useMemo(() => `/gastos?mes=${mes}&per_page=20`, [mes]));
  const entradas = useApi(useMemo(() => `/entradas?mes=${mes}`, [mes]));
  useRecarregarAoLancar(resumo.refetch, contas.refetch, gastos.refetch, entradas.refetch);

  // Popup de detalhe ao clicar numa barra do gráfico (pedido do Lucas,
  // 24/07/2026): { tipo: "gastos" | "entradas", mes: "YYYY-MM" } | null.
  const [detalhe, setDetalhe] = useState(null);

  return (
    <div>
      <Header>
        <Titulo>Início</Titulo>
        <MesPicker value={mes} onChange={setMes} />
      </Header>

      <ResumoMes dados={resumo.dados} carregando={resumo.loading} mes={mes} />

      <Grade>
        <AVencer dados={contas.dados} carregando={contas.loading} mes={mes} />
        <OndeFoi dados={resumo.dados} carregando={resumo.loading} />
      </Grade>

      <UltimosLancamentos
        gastos={gastos.dados?.itens}
        entradas={entradas.dados?.itens}
        carregando={gastos.loading || entradas.loading}
      />

      <ChartCard>
        <ChartTitulo>Entradas × gastos por mês</ChartTitulo>
        {resumo.loading || !resumo.dados ? (
          <SkeletonLinha style={{ height: 240 }} />
        ) : (
          <ChartComparativo
            dados={resumo.dados.comparativo_6_meses}
            onClickBarra={(tipo, mesClicado) => setDetalhe({ tipo, mes: mesClicado })}
          />
        )}
        <TextoMuted>Clique numa barra para ver os lançamentos do mês.</TextoMuted>
      </ChartCard>

      <DetalheMes detalhe={detalhe} onFechar={() => setDetalhe(null)} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// 1. Número principal do mês
// ---------------------------------------------------------------------------

function ResumoMes({ dados, carregando, mes }) {
  if (carregando || !dados) {
    return (
      <Hero aria-busy="true">
        <SkeletonLinha style={{ width: 160 }} />
        <SkeletonLinha style={{ width: 240, height: 36, marginTop: 8 }} />
        <SkeletonLinha style={{ height: 8, marginTop: 16 }} />
      </Hero>
    );
  }

  const passado = mes < mesAtualISO();
  // Mês corrente/futuro antecipa fixas e entradas recorrentes ainda não
  // lançadas (o backend manda 0 nos dois pra mês passado).
  const temPrevisto = dados.fixas_previstas > 0 || dados.entradas_previstas > 0;
  const sobra = temPrevisto ? dados.saldo_previsto : dados.saldo;
  const entradasMes = dados.total_entradas_previsto;
  const gastosMes = dados.total_gastos_previsto;
  const pct = entradasMes > 0 ? Math.min(100, Math.round((gastosMes / entradasMes) * 100)) : null;

  const rotulo = passado
    ? `Sobrou em ${nomeMes(mes)}`
    : temPrevisto ? `Sobra prevista em ${nomeMes(mes)}` : `Sobra em ${nomeMes(mes)}`;

  return (
    <Hero>
      <HeroRotulo>{rotulo}</HeroRotulo>
      <HeroValor $negativo={sobra < 0}>{brl(sobra)}</HeroValor>

      {pct != null && (
        <>
          <HeroBarra
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={pct}
            aria-label="Parte das entradas já comprometida com gastos"
          >
            <HeroBarraCheia style={{ width: `${pct}%` }} $tom={pct >= 100 ? "perigo" : pct >= 85 ? "alerta" : "ok"} />
          </HeroBarra>
          <HeroLegenda>{pct}% das entradas do mês {passado ? "foram gastos" : "já comprometidos"}</HeroLegenda>
        </>
      )}

      <Chips>
        <Chip>
          <span>Entrou</span>
          <strong>{brl(dados.total_entradas)}</strong>
          {dados.entradas_previstas > 0 && <small>+ {brl(dados.entradas_previstas)} previsto</small>}
        </Chip>
        <Chip>
          <span>Gastou</span>
          <strong>{brl(dados.total_gastos)}</strong>
          {dados.fixas_previstas > 0 && <small>+ {brl(dados.fixas_previstas)} em fixas</small>}
        </Chip>
        {dados.contas?.a_pagar > 0 && (
          <Chip $tom="alerta">
            <span>Falta pagar</span>
            <strong>{brl(dados.contas.a_pagar)}</strong>
          </Chip>
        )}
        {dados.pct_limite_medio != null && (
          <Chip $tom={dados.pct_limite_medio > 80 ? "perigo" : undefined}>
            <span>Limite dos cartões</span>
            <strong>{dados.pct_limite_medio.toFixed(0)}% usado</strong>
          </Chip>
        )}
      </Chips>
    </Hero>
  );
}

// ---------------------------------------------------------------------------
// 2. A vencer — itens não pagos do board de /contas, por vencimento
// ---------------------------------------------------------------------------

function AVencer({ dados, carregando, mes }) {
  const itens = useMemo(() => {
    const lista = [...(dados?.a_pagar || [])];
    lista.sort((a, b) => (a.vencimento || "9999").localeCompare(b.vencimento || "9999"));
    return lista;
  }, [dados]);
  const visiveis = itens.slice(0, 5);
  const mesAtual = mes === mesAtualISO();

  return (
    <Bloco aria-labelledby="titulo-a-vencer">
      <BlocoTopo>
        <BlocoTitulo id="titulo-a-vencer">{mesAtual ? "A vencer" : `Contas de ${nomeMes(mes)}`}</BlocoTitulo>
        <Link href="/contas" passHref legacyBehavior>
          <LinkVerTodos>Contas do mês <ArrowRight size={14} aria-hidden="true" /></LinkVerTodos>
        </Link>
      </BlocoTopo>

      {carregando || !dados ? (
        <>{[0, 1, 2].map((i) => <SkeletonLinha key={i} style={{ margin: "12px 0" }} />)}</>
      ) : visiveis.length === 0 ? (
        dados.pagas?.length > 0 ? (
          <TudoPago>
            <CircleCheck size={20} aria-hidden="true" />
            <span>
              Tudo pago neste mês
              <small>{dados.pagas.length} conta(s) · {brl(dados.totais?.pago)}</small>
            </span>
          </TudoPago>
        ) : (
          <Vazio>Nenhuma conta para este mês.</Vazio>
        )
      ) : (
        <>
          {visiveis.map((item) => {
            const prazo = mesAtual
              ? textoPrazo(diasAte(item.vencimento), item.vencimento || "")
              : { texto: item.vencimento ? `dia ${item.vencimento.slice(8, 10)}` : "sem data", tom: "neutro" };
            return (
              <LinhaConta key={item.chave}>
                <ContaNome>
                  {item.descricao}
                  <ContaPrazo $tom={prazo.tom}>
                    {prazo.tom === "perigo" && <CircleAlert size={12} aria-hidden="true" />}
                    {prazo.texto}
                    {item.tipo === "previsto" ? " · previsto" : ""}
                  </ContaPrazo>
                </ContaNome>
                <Valor>{brl(item.valor)}</Valor>
              </LinhaConta>
            );
          })}
          {itens.length > visiveis.length && (
            <TextoMuted style={{ marginTop: 8 }}>
              + {itens.length - visiveis.length} conta(s) · total a pagar {brl(dados.totais?.a_pagar)}
            </TextoMuted>
          )}
        </>
      )}
    </Bloco>
  );
}

// ---------------------------------------------------------------------------
// 3. Onde foi o dinheiro — barras horizontais por categoria
// ---------------------------------------------------------------------------

const MAX_CATEGORIAS = 6;

function OndeFoi({ dados, carregando }) {
  const linhas = useMemo(() => {
    const lista = [...(dados?.por_categoria || [])].filter((c) => c.total > 0);
    lista.sort((a, b) => b.total - a.total);
    if (lista.length <= MAX_CATEGORIAS) return lista;
    const resto = lista.slice(MAX_CATEGORIAS - 1).reduce((s, c) => s + c.total, 0);
    return [...lista.slice(0, MAX_CATEGORIAS - 1), { categoria: "Demais categorias", total: resto, outras: true }];
  }, [dados]);

  // Duas categorias com a mesma cor lado a lado confundem a leitura das
  // barras: a cor "natural" (utils/categoriaVisual) vale quando está livre,
  // senão a barra pega a próxima cor ainda não usada nesta lista.
  // Categorias reconhecidas por palavra-chave (Mercado = verde) escolhem
  // primeiro; as de cor sorteada por hash cedem a vez.
  const cores = useMemo(() => {
    const usadas = new Set();
    const resultado = linhas.map(() => null);
    const visuais = linhas.map((c) => (c.outras ? null : categoriaVisual(c.categoria)));
    for (const porRegra of [true, false]) {
      visuais.forEach((v, i) => {
        if (!v || v.porRegra !== porRegra) return;
        let cor = v.cor;
        if (usadas.has(cor)) cor = CORES_CATEGORIA.find((x) => !usadas.has(x)) || cor;
        usadas.add(cor);
        resultado[i] = cor;
      });
    }
    return resultado.map((cor) => cor || "#888780");
  }, [linhas]);

  const total = linhas.reduce((s, c) => s + c.total, 0);
  const maior = linhas[0]?.total || 1;
  const fixo = dados?.fixo_variavel?.fixo || 0;
  const variavel = dados?.fixo_variavel?.variavel || 0;
  const pctFixo = fixo + variavel > 0 ? Math.round((fixo / (fixo + variavel)) * 100) : null;

  return (
    <Bloco aria-labelledby="titulo-onde-foi">
      <BlocoTopo>
        <BlocoTitulo id="titulo-onde-foi">Onde foi o dinheiro</BlocoTitulo>
        <Link href="/lancamentos" passHref legacyBehavior>
          <LinkVerTodos>Lançamentos <ArrowRight size={14} aria-hidden="true" /></LinkVerTodos>
        </Link>
      </BlocoTopo>

      {carregando || !dados ? (
        <>{[0, 1, 2, 3].map((i) => <SkeletonLinha key={i} style={{ margin: "12px 0" }} />)}</>
      ) : linhas.length === 0 ? (
        <Vazio>Nenhum gasto neste mês.</Vazio>
      ) : (
        <>
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {linhas.map((c, i) => {
              const cor = cores[i];
              return (
                <CatLinha key={c.categoria}>
                  <CatNome>{c.categoria}</CatNome>
                  <CatTrilho aria-hidden="true">
                    <CatBarra style={{ width: `${Math.max(3, (c.total / maior) * 100)}%`, background: cor }} />
                  </CatTrilho>
                  <CatValor>
                    {brl(c.total)}
                    <small>{total > 0 ? Math.round((c.total / total) * 100) : 0}%</small>
                  </CatValor>
                </CatLinha>
              );
            })}
          </ul>

          {pctFixo != null && (
            <Divisao>
              <DivisaoBarra aria-hidden="true">
                <span style={{ width: `${pctFixo}%` }} />
              </DivisaoBarra>
              <DivisaoLegenda>
                <span><i data-tipo="fixo" /> Fixo {brl(fixo)}</span>
                <span><i data-tipo="variavel" /> Variável {brl(variavel)}</span>
              </DivisaoLegenda>
            </Divisao>
          )}
        </>
      )}
    </Bloco>
  );
}

// ---------------------------------------------------------------------------
// 4. Últimos lançamentos — gastos + entradas do mês, agrupados por dia
// ---------------------------------------------------------------------------

const MAX_LANCAMENTOS = 8;

function UltimosLancamentos({ gastos, entradas, carregando }) {
  const dias = useMemo(() => {
    const todos = [
      // linha projetada (fixa prevista) não é lançamento de verdade ainda
      ...(gastos || []).filter((g) => !g.projetado).map((g) => ({ ...g, tipo: "gasto" })),
      ...(entradas || []).map((e) => ({ ...e, tipo: "entrada" })),
    ]
      .filter((l) => l.data && diasAte(l.data) <= 0)
      .sort((a, b) => b.data.localeCompare(a.data) || String(b.id).localeCompare(String(a.id)))
      .slice(0, MAX_LANCAMENTOS);

    const grupos = [];
    for (const l of todos) {
      const chave = l.data.slice(0, 10);
      let grupo = grupos[grupos.length - 1];
      if (!grupo || grupo.chave !== chave) {
        grupo = { chave, itens: [], saldo: 0 };
        grupos.push(grupo);
      }
      grupo.itens.push(l);
      grupo.saldo += l.tipo === "entrada" ? Number(l.valor) : -Number(l.valor);
    }
    return grupos;
  }, [gastos, entradas]);

  return (
    <Bloco aria-labelledby="titulo-ultimos" style={{ marginBottom: 20 }}>
      <BlocoTopo>
        <BlocoTitulo id="titulo-ultimos">Últimos lançamentos</BlocoTitulo>
        <Link href="/lancamentos" passHref legacyBehavior>
          <LinkVerTodos>Ver todos <ArrowRight size={14} aria-hidden="true" /></LinkVerTodos>
        </Link>
      </BlocoTopo>

      {carregando && !gastos ? (
        <>{[0, 1, 2].map((i) => <SkeletonLinha key={i} style={{ margin: "14px 0" }} />)}</>
      ) : dias.length === 0 ? (
        <Vazio>Nenhum lançamento neste mês. Use “Novo lançamento” ou mande uma mensagem pro bot.</Vazio>
      ) : (
        dias.map((dia) => (
          <Dia key={dia.chave}>
            <DiaTopo>
              <span>{rotuloDia(dia.chave)}</span>
              <span>{dia.saldo >= 0 ? "+" : "−"} {brl(Math.abs(dia.saldo))}</span>
            </DiaTopo>
            <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {dia.itens.map((l) => {
                const entrada = l.tipo === "entrada";
                const visual = entrada
                  ? { Icone: TrendingUp, cor: COR_ENTRADA, fundo: `${COR_ENTRADA}26` }
                  : categoriaVisual(l.categoria_nome);
                const meta = entrada
                  ? ["Entrada", l.entrada_fixa_id ? "recorrente" : null]
                  : [
                    l.categoria_nome,
                    l.forma_nome,
                    l.compra_parcelada_id ? `parcela ${l.parcela_num}/${l.total_parcelas || "?"}` : null,
                    l.despesa_fixa_id ? "fixa" : null,
                  ];
                return (
                  <Lancamento key={`${l.tipo}-${l.id}`}>
                    <Avatar style={{ background: visual.fundo, color: visual.cor }} aria-hidden="true">
                      <visual.Icone size={18} strokeWidth={2} />
                    </Avatar>
                    <LancTexto>
                      {/* Sem descrição (comum no lançamento rápido pelo bot): o nome
                          da categoria é um título melhor que "(sem descrição)". */}
                      <LancTitulo>{l.descricao || l.categoria_nome || (entrada ? "Entrada" : "Gasto")}</LancTitulo>
                      <LancMeta>
                        {meta.filter(Boolean).join(" · ")}
                      </LancMeta>
                    </LancTexto>
                    <Valor $tom={entrada ? "entrada" : undefined}>
                      {entrada ? "+" : "−"} {brl(l.valor)}
                    </Valor>
                  </Lancamento>
                );
              })}
            </ul>
          </Dia>
        ))
      )}
    </Bloco>
  );
}

// ---------------------------------------------------------------------------
// Popup de detalhe do mês clicado — reusa os endpoints que já existem
// (GET /api/gastos?mes=, GET /api/entradas?mes=) em vez de agregar de novo
// no backend: o gráfico já mostra o total, aqui só falta a lista por trás.
// `total` de /api/gastos é CONTAGEM de linhas, não soma de valor (contrato
// de services/gastos.py::listar_gastos) — por isso o total exibido aqui é
// somado no front a partir dos itens, não lido de `dados.total`.
// ---------------------------------------------------------------------------

// Agrupa por forma de pagamento (pedido do Lucas, 24/07/2026: "quero que
// apareça primeiro pela forma de pagamento"). Função pura — só reorganiza
// o que /api/gastos já devolve, nenhum cálculo novo no backend. Ordenado
// por total decrescente: a forma que mais pesou no mês aparece primeiro,
// que é a pergunta mais provável ("no que eu mais gastei").
function agruparPorForma(itens) {
  const grupos = new Map();
  for (const item of itens) {
    const nome = item.forma_nome || "Sem forma de pagamento";
    if (!grupos.has(nome)) grupos.set(nome, { nome, total: 0, itens: [] });
    const grupo = grupos.get(nome);
    grupo.total += Number(item.valor);
    grupo.itens.push(item);
  }
  return [...grupos.values()].sort((a, b) => b.total - a.total);
}

function DetalheMes({ detalhe, onFechar }) {
  const { tipo, mes } = detalhe || {};
  const url = tipo === "gastos" ? (mes ? `/gastos?mes=${mes}&per_page=200` : null)
    : tipo === "entradas" ? (mes ? `/entradas?mes=${mes}` : null)
    : null;
  const { dados, loading } = useApi(url, { skip: !url });

  // Fecha os grupos toda vez que abre um mês/tipo diferente — expandido de
  // um clique anterior não devia vazar pro próximo popup.
  const [expandidos, setExpandidos] = useState(() => new Set());
  useEffect(() => setExpandidos(new Set()), [tipo, mes]);

  function alternar(nomeForma) {
    setExpandidos((atual) => {
      const novo = new Set(atual);
      novo.has(nomeForma) ? novo.delete(nomeForma) : novo.add(nomeForma);
      return novo;
    });
  }

  const itens = dados?.itens || [];
  const totalItens = itens.reduce((s, item) => s + Number(item.valor), 0);
  const titulo = mes
    ? `${tipo === "gastos" ? "Gastos" : "Entradas"} — ${formatarCompetencia(`${mes}-01`)}`
    : "";
  const grupos = tipo === "gastos" ? agruparPorForma(itens) : null;

  return (
    // Largura maior que o padrão do Modal (480px): com data + categoria +
    // forma na mesma linha, o texto cortava contra o valor à direita
    // (relato do Lucas, print do popup de julho/2026).
    <Modal aberto={!!detalhe} titulo={titulo} onFechar={onFechar} largura="min(640px, 92vw)">
      {loading || !dados ? (
        <Loading />
      ) : itens.length === 0 ? (
        <TextoMuted>Nenhum lançamento neste mês.</TextoMuted>
      ) : grupos ? (
        <>
          <ListaDetalhe>
            {grupos.map((grupo) => (
              <div key={grupo.nome}>
                <GrupoForma type="button" onClick={() => alternar(grupo.nome)}>
                  <span>{expandidos.has(grupo.nome) ? "▾" : "▸"} {grupo.nome}</span>
                  <span>{brl(grupo.total)}</span>
                </GrupoForma>
                {expandidos.has(grupo.nome) && grupo.itens.map((item) => (
                  <ItemAninhado key={item.id}>
                    <div>
                      <div>
                        {item.descricao || "(sem descrição)"}
                        {item.projetado ? " · previsto" : ""}
                      </div>
                      <TextoMuted>
                        {formatarDataBR(item.data)}
                        {item.categoria_nome ? ` · ${item.categoria_nome}` : ""}
                      </TextoMuted>
                    </div>
                    <span>{brl(item.valor)}</span>
                  </ItemAninhado>
                ))}
              </div>
            ))}
          </ListaDetalhe>
          <ItemDetalhe style={{ fontWeight: 600, marginTop: 8 }}>
            <span>Total</span>
            <span>{brl(totalItens)}</span>
          </ItemDetalhe>
        </>
      ) : (
        // Entrada não tem forma de pagamento (não é uma compra, é dinheiro
        // caindo na conta) — segue lista simples, sem agrupamento.
        <>
          <ListaDetalhe>
            {itens.map((item) => (
              <ItemDetalhe key={item.id}>
                <div>
                  <div>{item.descricao || "(sem descrição)"}</div>
                  <TextoMuted>{formatarDataBR(item.data)}</TextoMuted>
                </div>
                <span>{brl(item.valor)}</span>
              </ItemDetalhe>
            ))}
          </ListaDetalhe>
          <ItemDetalhe style={{ fontWeight: 600, marginTop: 8 }}>
            <span>Total</span>
            <span>{brl(totalItens)}</span>
          </ItemDetalhe>
        </>
      )}
    </Modal>
  );
}
