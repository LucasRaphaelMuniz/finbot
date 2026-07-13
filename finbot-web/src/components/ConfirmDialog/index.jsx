"use client";

import Modal from "@/components/Modal";

// components/ConfirmDialog — usado nas exclusões (gasto, entrada, despesa
// fixa, membro do grupo). Para exclusão de parcela, a tela de /lancamentos
// (Fase 5) precisa da variante "só esta x compra inteira" (mesma regra D3
// do bot) — não coberta por este componente genérico de sim/não.
export default function ConfirmDialog({ aberto, titulo, mensagem, onConfirmar, onCancelar }) {
  return (
    <Modal aberto={aberto} titulo={titulo} onFechar={onCancelar}>
      <p>{mensagem}</p>
      <div style={{ display: "flex", gap: 8, marginTop: 16, justifyContent: "flex-end" }}>
        <button onClick={onCancelar}>Cancelar</button>
        <button onClick={onConfirmar}>Confirmar</button>
      </div>
    </Modal>
  );
}
