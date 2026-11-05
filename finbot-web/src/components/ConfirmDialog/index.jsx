"use client";

import Modal from "@/components/Modal";
import { Acoes, BotaoPerigo } from "./styles";

// components/ConfirmDialog — usado nas exclusões (gasto, entrada, despesa
// fixa, membro do grupo). Para exclusão de parcela, a tela de /lancamentos
// (Fase 5) precisa da variante "só esta x compra inteira" (mesma regra D3
// do bot) — não coberta por este componente genérico de sim/não.
//
// Auditoria de UX (05/11/2026): o botão era um "Confirmar" neutro, igual
// ao Cancelar. Agora o verbo diz o que acontece (`textoConfirmar`, ex:
// "Excluir lançamento"), o botão é vermelho e o foco inicial cai em
// Cancelar — Enter por reflexo não apaga nada.
export default function ConfirmDialog({
  aberto,
  titulo,
  mensagem,
  onConfirmar,
  onCancelar,
  textoConfirmar = "Excluir",
}) {
  return (
    <Modal aberto={aberto} titulo={titulo} onFechar={onCancelar}>
      <p>{mensagem}</p>
      <Acoes>
        <button type="button" onClick={onCancelar} data-autofocus>
          Cancelar
        </button>
        <BotaoPerigo type="button" onClick={onConfirmar}>
          {textoConfirmar}
        </BotaoPerigo>
      </Acoes>
    </Modal>
  );
}
