"use client";

// app/(app)/parcelas/page.jsx — compras parceladas em andamento (pedido do
// Lucas em 18/07/2026: "quantas faltam, o total, etc"). Só leitura: criar
// parcelado é no "Novo lançamento" (ou no bot), excluir é na parcela em
// Lançamentos ("compra inteira") — esta tela é de acompanhamento.
//
// "Restantes" conta parcelas com competência >= mês corrente direto de
// `gastos` (fonte de verdade — parcela excluída individualmente sai da
// conta), não do plano original da compra.
//
// Redesign 05/11/2026 (fase 3): além da lista (agora com barra de
// progresso por compra), uma linha do tempo dos próximos meses — quanto
// das parcelas cai em cada mês e o que termina nele. A pergunta que a
// tabela antiga não respondia: "quando meu orçamento folga?".
// O valor por mês é estimado (valor restante ÷ parcelas restantes de cada
// compra): parcela com centavos de arredondamento pode variar uns
// centavos — por isso o "≈".
import { useMemo } from "react";
import { useApi } from "@/hooks/useApi";
import { brl } from "@/utils/format";
import { mesAtualISO } from "@/utils/datas";
import {
  Header, Titulo, Subtitulo, Resumo, ResumoItem, Bloco, BlocoTitulo, LinhaMeses, Mes, MesBarra,
  MesBarraCheia, MesValor, MesNome, MesFim, Lista, Item, ItemTopo, ItemTitulo, ItemValor,
  ItemMeta, Progresso, ProgressoCheio, Selo, Vazio, SkeletonLinha,
} from "./styles";

const MESES_CURTOS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const MAX_MESES = 12;

// "2026-12-01" (ou com hora) → "2026-12"
function chaveMes(iso) {
  return iso ? String(iso).slice(0, 7) : null;
}

function rotuloMes(chave, comAno = true) {
  if (!chave) return "—";
  const [ano, mes] = chave.split("-");
  return `${MESES_CURTOS[Number(mes) - 1]}${comAno ? `/${ano.slice(2)}` : ""}`;
}

function somarMes(chave, n) {
  const [ano, mes] = chave.split("-").map(Number);
  const d = new Date(ano, mes - 1 + n, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export default function ParcelasPage() {
  const { dados, loading } = useApi("/gastos/parcelamentos");
  const itens = useMemo(() => dados?.itens || [], [dados]);
  const totalRestante = itens.reduce((soma, c) => soma + Number(c.valor_restante || 0), 0);

  const meses = useMemo(() => {
    if (itens.length === 0) return [];
    const hoje = mesAtualISO();
    // Custo fixo com prazo: a API conta como "restante" só o que ainda não
    // foi lançado — o mês corrente (e o seguinte, quando a fixa já lançou
    // adiantado) some da conta, mas é pago do mesmo jeito. Na linha do
    // tempo ele vale de hoje até a última parcela.
    const inicioDe = (c) => {
      const de = chaveMes(c.proxima_competencia);
      return c.tipo === "fixa" && de && de > hoje ? hoje : de;
    };
    const inicio = itens.map(inicioDe).filter(Boolean).sort()[0];
    const fim = itens.map((c) => chaveMes(c.ultima_competencia)).filter(Boolean).sort().pop();
    if (!inicio || !fim) return [];
    const lista = [];
    for (let m = inicio; m <= fim && lista.length < MAX_MESES; m = somarMes(m, 1)) {
      let valor = 0;
      const terminam = [];
      for (const c of itens) {
        const de = inicioDe(c);
        const ate = chaveMes(c.ultima_competencia);
        if (!de || !ate || m < de || m > ate) continue;
        valor += Number(c.valor_restante || 0) / Math.max(1, Number(c.parcelas_restantes || 1));
        if (m === ate) terminam.push(c.descricao || "compra");
      }
      lista.push({ chave: m, valor, terminam });
    }
    return lista;
  }, [itens]);

  const maiorMes = Math.max(1, ...meses.map((m) => m.valor));
  const ultimoFim = itens.map((c) => chaveMes(c.ultima_competencia)).filter(Boolean).sort().pop();

  return (
    <div>
      <Header>
        <Titulo>Parcelas futuras</Titulo>
        <Subtitulo>Compras parceladas e custos fixos com prazo que ainda têm parcela a vencer.</Subtitulo>
      </Header>

      {loading && !dados ? (
        <Lista aria-busy="true">{[0, 1, 2].map((i) => <SkeletonLinha key={i} />)}</Lista>
      ) : itens.length === 0 ? (
        <Lista>
          <Vazio>
            <strong>Nenhuma parcela a vencer.</strong>
            <span>Compras parceladas aparecem aqui enquanto tiverem parcelas pela frente.</span>
          </Vazio>
        </Lista>
      ) : (
        <>
          <Resumo aria-label="Totais">
            <ResumoItem>
              <span>Total a vencer</span>
              <strong>{brl(totalRestante)}</strong>
            </ResumoItem>
            <ResumoItem>
              <span>Compras</span>
              <strong>{itens.length}</strong>
            </ResumoItem>
            <ResumoItem>
              <span>Última parcela</span>
              <strong>{rotuloMes(ultimoFim)}</strong>
            </ResumoItem>
          </Resumo>

          {meses.length > 0 && (
            <Bloco aria-labelledby="titulo-meses">
              <BlocoTitulo id="titulo-meses">Quanto cai em cada mês</BlocoTitulo>
              <LinhaMeses role="list">
                {meses.map((m) => (
                  <Mes
                    key={m.chave}
                    role="listitem"
                    aria-label={`${rotuloMes(m.chave)}: aproximadamente ${brl(m.valor)}${m.terminam.length ? `, termina ${m.terminam.join(", ")}` : ""}`}
                  >
                    <MesValor aria-hidden="true">≈ {brl(m.valor).replace(/,\d{2}$/, "")}</MesValor>
                    <MesBarra aria-hidden="true">
                      <MesBarraCheia style={{ height: `${(m.valor / maiorMes) * 100}%` }} />
                    </MesBarra>
                    <MesNome aria-hidden="true">{rotuloMes(m.chave)}</MesNome>
                    {m.terminam.length > 0 && (
                      <MesFim aria-hidden="true" title={`Termina: ${m.terminam.join(", ")}`}>
                        −{m.terminam.length}
                      </MesFim>
                    )}
                  </Mes>
                ))}
              </LinhaMeses>
              <Subtitulo style={{ marginTop: 8 }}>
                O “−1” marca o mês em que uma compra termina e o orçamento folga.
              </Subtitulo>
            </Bloco>
          )}

          <Lista>
            <ul>
              {itens.map((c) => {
                const pagas = Number(c.parcelas) - Number(c.parcelas_restantes);
                const pct = c.parcelas ? Math.min(100, (pagas / c.parcelas) * 100) : 0;
                return (
                  <Item key={c.id}>
                    <ItemTopo>
                      <ItemTitulo>
                        {c.descricao || "Compra sem descrição"}
                        {c.tipo === "fixa" && <Selo>custo fixo</Selo>}
                      </ItemTitulo>
                      <ItemValor>{brl(c.valor_restante)}</ItemValor>
                    </ItemTopo>
                    <Progresso
                      role="progressbar"
                      aria-label={`${c.descricao || "Compra"}: ${pagas} de ${c.parcelas} parcelas pagas`}
                      aria-valuemin={0}
                      aria-valuemax={Number(c.parcelas)}
                      aria-valuenow={pagas}
                    >
                      <ProgressoCheio style={{ width: `${pct}%` }} />
                    </Progresso>
                    <ItemMeta>
                      <span>
                        faltam <strong>{c.parcelas_restantes}</strong> de {c.parcelas}
                        {" · "}termina em {rotuloMes(chaveMes(c.ultima_competencia))}
                      </span>
                      <span>
                        {[c.forma_nome, c.membro_nome].filter(Boolean).join(" · ")}
                        {c.valor_total ? ` · total ${brl(c.valor_total)}` : ""}
                      </span>
                    </ItemMeta>
                  </Item>
                );
              })}
            </ul>
          </Lista>
        </>
      )}
    </div>
  );
}
