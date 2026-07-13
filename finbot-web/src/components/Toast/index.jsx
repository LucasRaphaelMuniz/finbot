import { Box } from "./styles";

// components/Toast — feedback simples de sucesso/erro. Sem lib de terceiros
// (react-hot-toast etc.) de propósito: uso é pontual, não vale a dependência
// extra agora. Se a necessidade crescer nas telas da Fase 5, revisar.
export default function Toast({ mensagem, tipo = "sucesso" }) {
  if (!mensagem) return null;
  return <Box $tipo={tipo}>{mensagem}</Box>;
}
