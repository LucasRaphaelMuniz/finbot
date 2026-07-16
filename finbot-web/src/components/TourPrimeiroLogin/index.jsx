"use client";

// components/TourPrimeiroLogin — checklist de 4 passos mostrado uma vez, no
// primeiro carregamento do app depois do cadastro (Fase C do
// AUDITORIA_E_PLANO_CADASTRO.md, corrige F5: antes a pessoa caía no
// dashboard vazio sem saber que o próximo passo era falar com o bot).
//
// Decisão de design: o conteúdo dos passos muda conforme a pessoa veio de
// um MERGE (já usava o bot, conta web só "encontrou" o histórico) ou de um
// CADASTRO NOVO (nunca falou com o bot ainda) — ver tabela no
// AUDITORIA_E_PLANO_CADASTRO.md, Fase C2. Essa distinção não é persistida
// no banco (não é informação que precise sobreviver além do momento do
// cadastro); vem de sessionStorage, setado por CompletarCadastro logo após
// o POST /api/onboarding. Se a chave não existir (ex: pessoa está revendo
// o tutorial dias depois pelo link "rever tutorial" da tela Conta), cai na
// variante "cadastro novo" por padrão — inofensivo, só menos personalizado.
import { useState } from "react";
import Modal from "@/components/Modal";
import api from "@/services/api";
import { Passo, Botoes, WhatsBotao, NumeroBot } from "./styles";
import { VEIO_DO_BOT_KEY } from "@/utils/constants";
import { formatarTelefoneExibicao } from "@/utils/format";

const NUMERO_BOT = process.env.NEXT_PUBLIC_BOT_WHATSAPP || "";

function montarPassos(veioDoBot) {
  if (veioDoBot) {
    return [
      {
        titulo: "Seus dados do bot já estão aqui",
        texto: "Tudo que você já registrava pelo WhatsApp apareceu automaticamente. Dá uma olhada na tela Lançamentos.",
      },
      {
        titulo: "Confira formas de pagamento e limites",
        texto: "Veja se os limites de cada cartão/forma ainda fazem sentido, na tela Formas.",
      },
      {
        titulo: "Explore o dashboard",
        texto: "Gráficos por categoria e por mês, pra enxergar pra onde o dinheiro está indo.",
      },
      {
        titulo: "Convide alguém pro grupo",
        texto: "Gere um link de convite na tela Grupo.",
      },
    ];
  }
  return [
    {
      titulo: "Salve o número do bot",
      texto: NUMERO_BOT
        ? "É por ele que você registra gastos pelo WhatsApp, direto na conversa."
        : "Peça o número do bot pra quem te convidou — é por ele que você registra gastos.",
      link: NUMERO_BOT ? `https://wa.me/${NUMERO_BOT}?text=oi` : null,
      linkTexto: "Mandar \"oi\" agora",
    },
    {
      titulo: "Configure formas e limites",
      texto: "Ajuste na tela Formas de pagamento — cartão, pix, o que fizer sentido pra você.",
    },
    {
      titulo: "Registre seu primeiro gasto",
      texto: 'Pelo WhatsApp, é só mandar algo como: "50 mercado cartão"',
    },
    {
      titulo: "Convide alguém pro grupo",
      texto: "Gere um link de convite na tela Grupo.",
    },
  ];
}

export default function TourPrimeiroLogin({ onFechar }) {
  const [passo, setPasso] = useState(0);
  const veioDoBot =
    typeof window !== "undefined" && sessionStorage.getItem(VEIO_DO_BOT_KEY) === "true";
  const passos = montarPassos(veioDoBot);
  const atual = passos[passo];
  const ultimo = passo === passos.length - 1;

  async function marcarVistoEFechar() {
    try {
      await api.post("/conta/tutorial-visto", { visto: true });
    } catch {
      // Falha ao marcar não deve travar a pessoa fora do app — ela só verá
      // o tour de novo no próximo carregamento, o que é inofensivo.
    } finally {
      onFechar();
    }
  }

  return (
    <Modal aberto titulo={`Passo ${passo + 1} de ${passos.length}`} onFechar={marcarVistoEFechar}>
      <Passo>
        <strong>{atual.titulo}</strong>
        <p>{atual.texto}</p>
        {atual.link && (
          <>
            <WhatsBotao href={atual.link} target="_blank" rel="noreferrer">
              💬 {atual.linkTexto}
            </WhatsBotao>
            <NumeroBot>{formatarTelefoneExibicao(NUMERO_BOT)}</NumeroBot>
          </>
        )}
      </Passo>
      <Botoes>
        <button type="button" onClick={marcarVistoEFechar}>
          Pular
        </button>
        {ultimo ? (
          <button type="button" onClick={marcarVistoEFechar}>
            Concluir
          </button>
        ) : (
          <button type="button" onClick={() => setPasso((p) => p + 1)}>
            Próximo
          </button>
        )}
      </Botoes>
    </Modal>
  );
}
