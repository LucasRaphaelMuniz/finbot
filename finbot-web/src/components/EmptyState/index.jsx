import { Wrap } from "./styles";

// components/EmptyState — usado em toda tela de listagem quando não há
// dados ainda (padrão exigido pelo §Fase 5 do PLANO_EXECUCAO.md: toda tela
// tem estado vazio + loading + erro).
export default function EmptyState({ titulo, descricao, acao }) {
  return (
    <Wrap>
      <strong>{titulo}</strong>
      {descricao && <span>{descricao}</span>}
      {acao}
    </Wrap>
  );
}
