import { Spinner } from "./styles";

// role="status" + rótulo: sem isso o spinner era só uma div girando,
// invisível pra leitor de tela (a pessoa não sabia que a tela carregava).
export default function Loading({ size, rotulo = "Carregando" }) {
  return <Spinner $size={size} role="status" aria-label={rotulo} />;
}
