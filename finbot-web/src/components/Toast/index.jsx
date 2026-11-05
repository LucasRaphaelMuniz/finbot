import { Box, Regiao } from "./styles";

// components/Toast — feedback simples de sucesso/erro. Sem lib de terceiros
// (react-hot-toast etc.) de propósito: uso é pontual, não vale a dependência
// extra agora. Se a necessidade crescer nas telas da Fase 5, revisar.
//
// A região aria-live fica SEMPRE montada (vazia quando não há mensagem):
// leitor de tela só anuncia mudanças dentro de uma região que já existia
// no DOM — montar a região junto com o texto (como antes, `return null`
// sem mensagem) faz a maioria dos leitores ignorar o aviso. Erro usa
// role="alert" (interrompe a leitura); sucesso usa status (educado).
export default function Toast({ mensagem, tipo = "sucesso" }) {
  const erro = tipo === "erro";
  return (
    <Regiao role={erro ? "alert" : "status"} aria-live={erro ? "assertive" : "polite"}>
      {mensagem ? <Box $tipo={tipo}>{mensagem}</Box> : null}
    </Regiao>
  );
}
