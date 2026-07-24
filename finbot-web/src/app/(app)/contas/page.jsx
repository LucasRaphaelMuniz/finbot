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
import { useMemo, useState } from "react";
import { useApi } from "@/hooks/useApi";
import api from "@/services/api";
import { brl, formatarDataBR, parseValorBR } from "@/utils/format";
import MesPicker from "@/components/MesPicker";
import Loading from "@/components/Loading";
import StatCard from "@/components/StatCard";
import Toast from "@/components/Toast";
import {
  Header, Board, Coluna, ColunaHeader, ColunaTitulo, ColunaTotal, Card,
  CardInfo, CardTitulo, CardDetalhe, CardValor, ValorRiscado, BotaoMover,
  InputValor, Vazio, Resumo,
} from "./styles";

function mesAtualISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export default function ContasPage() {
  const [mes, setMes] = useState(mesAtualISO());
  const url = useMemo(() => `/contas?mes=${mes}`, [mes]);
  const { dados, loading, refetch } = useApi(url);

  const [toast, setToast] = useState(null);
  const [arrastando, setArrastando] = useState(null); // chave do card em voo
  const [colunaAlvo, setColunaAlvo] = useState(null); // "a_pagar" | "pagas"
  const [salvando, setSalvando] = useState(null);

  function avisar(mensagem, tipo = "sucesso") {
    setToast({ mensagem, tipo });
    setTimeout(() => setToast(null), 3000);
  }

  async function mover(conta, pago) {
    if (!conta.editavel) return; // linha "previsto" não existe no banco ainda
    setSalvando(conta.chave);
    try {
      await api.patch(`/contas/${conta.chave}`, { pago });
      // refetch em vez de mexer no estado local: marcar uma fatura como paga
      // muda os 3 totais do topo, e recalcular isso no browser seria uma
      // segunda implementação das somas que o backend já faz.
      refetch();
      avisar(pago ? "Marcado como pago." : "Devolvido para não pagos.");
    } catch (err) {
      avisar(err?.response?.data?.mensagem || "Não foi possível atualizar.", "erro");
    } finally {
      setSalvando(null);
    }
  }

  async function salvarValor(conta, valor) {
    if (valor === null || Number(valor) === Number(conta.valor_pago ?? conta.valor)) return;
    setSalvando(conta.chave);
    try {
      await api.patch(`/contas/${conta.chave}`, { valor });
      refetch();
      avisar("Valor atualizado.");
    } catch (err) {
      avisar(err?.response?.data?.mensagem || "Não foi possível salvar o valor.", "erro");
    } finally {
      setSalvando(null);
    }
  }

  // Drag nativo do HTML5 (sem dependência nova). Só funciona com mouse — em
  // toque o caminho é o BotaoMover de cada card, que faz exatamente a mesma
  // chamada. Decisão consciente: @dnd-kit resolveria o toque, mas é uma
  // dependência a mais pra um gesto que já tem um equivalente acessível.
  function aoSoltar(coluna) {
    return (e) => {
      e.preventDefault();
      setColunaAlvo(null);
      const chave = e.dataTransfer.getData("text/plain") || arrastando;
      setArrastando(null);
      if (!chave) return;

      const conta = [...(dados?.a_pagar || []), ...(dados?.pagas || [])]
        .find((c) => c.chave === chave);
      if (!conta) return;

      const querPago = coluna === "pagas";
      if (conta.pago === querPago) return; // soltou na coluna de origem
      mover(conta, querPago);
    };
  }

  function propsColuna(coluna) {
    return {
      onDragOver: (e) => {
        e.preventDefault();
        setColunaAlvo(coluna);
      },
      onDragLeave: () => setColunaAlvo((atual) => (atual === coluna ? null : atual)),
      onDrop: aoSoltar(coluna),
      $alvo: colunaAlvo === coluna && arrastando !== null,
    };
  }

  const totais = dados?.totais;

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

      {loading || !dados ? (
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
            <Coluna>
              <ColunaHeader>
                <ColunaTitulo>Entradas</ColunaTitulo>
                <ColunaTotal $tom="sucesso">{brl(totais.entradas)}</ColunaTotal>
              </ColunaHeader>
              {dados.entradas.length === 0 ? (
                <Vazio>Nenhuma entrada lançada neste mês.</Vazio>
              ) : (
                dados.entradas.map((e) => (
                  <Card key={e.chave} $origem="entrada">
                    <CardInfo>
                      <CardTitulo>{e.descricao}</CardTitulo>
                      <CardDetalhe>{formatarDataBR(e.data)}</CardDetalhe>
                    </CardInfo>
                    <CardValor as="span">{brl(e.valor)}</CardValor>
                  </Card>
                ))
              )}
            </Coluna>

            <Coluna {...propsColuna("a_pagar")}>
              <ColunaHeader>
                <ColunaTitulo>Não pagos</ColunaTitulo>
                <ColunaTotal $tom="erro">{brl(totais.a_pagar)}</ColunaTotal>
              </ColunaHeader>
              {dados.a_pagar.length === 0 ? (
                <Vazio>Tudo pago neste mês.</Vazio>
              ) : (
                dados.a_pagar.map((c) => (
                  <CardConta
                    key={c.chave}
                    conta={c}
                    arrastando={arrastando === c.chave}
                    salvando={salvando === c.chave}
                    onArrastar={setArrastando}
                    onMover={() => mover(c, true)}
                    onSalvarValor={(v) => salvarValor(c, v)}
                  />
                ))
              )}
            </Coluna>

            <Coluna {...propsColuna("pagas")}>
              <ColunaHeader>
                <ColunaTitulo>Pagos</ColunaTitulo>
                <ColunaTotal $tom="sucesso">{brl(totais.pago)}</ColunaTotal>
              </ColunaHeader>
              {dados.pagas.length === 0 ? (
                <Vazio>Arraste uma conta para cá quando pagar.</Vazio>
              ) : (
                dados.pagas.map((c) => (
                  <CardConta
                    key={c.chave}
                    conta={c}
                    arrastando={arrastando === c.chave}
                    salvando={salvando === c.chave}
                    onArrastar={setArrastando}
                    onMover={() => mover(c, false)}
                    onSalvarValor={(v) => salvarValor(c, v)}
                  />
                ))
              )}
            </Coluna>
          </Board>
        </>
      )}

      <Toast mensagem={toast?.mensagem} tipo={toast?.tipo} />
    </div>
  );
}

function CardConta({ conta, arrastando, salvando, onArrastar, onMover, onSalvarValor }) {
  const [editando, setEditando] = useState(false);
  const [texto, setTexto] = useState("");

  const arrastavel = conta.editavel && !salvando;
  // Numa fatura, o valor só vira editável DEPOIS de paga: antes disso o
  // número exibido é a soma real dos lançamentos, e "quanto pretendo pagar"
  // não é um dado (o backend recusa com 409 — services/contas_mes.py).
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
    >
      <BotaoMover
        $pago={conta.pago}
        disabled={!conta.editavel || salvando}
        onClick={onMover}
        title={conta.pago ? "Marcar como não pago" : "Marcar como pago"}
        aria-label={conta.pago ? "Marcar como não pago" : "Marcar como pago"}
      >
        {conta.pago ? "✓" : "○"}
      </BotaoMover>

      <CardInfo>
        <CardTitulo>{conta.descricao}</CardTitulo>
        <CardDetalhe>
          {conta.vencimento ? `vence ${formatarDataBR(conta.vencimento)} · ` : ""}
          {conta.detalhe}
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
