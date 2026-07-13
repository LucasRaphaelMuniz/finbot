"use client";

// components/TelefoneInput — input de WhatsApp usado nos 3 lugares que pedem
// telefone (CompletarCadastro x2, FormEditarMembro em /grupo). Fase A5 do
// AUDITORIA_E_PLANO_CADASTRO.md.
//
// Duas decisões de design:
// 1. Só formata pra EXIBIÇÃO — a normalização "de verdade" (que decide o
//    JID final gravado no banco, incluindo a regra do 9º dígito) continua
//    100% em utils/telefone.py, único lugar que conhece essa regra.
//    Reimplementar a mesma lógica aqui em JS duplicaria regra de negócio
//    sem teste automatizado do lado do front — exatamente o problema que a
//    Fase A está corrigindo do lado do Python (F1: normalização divergente
//    entre bot e web). O componente só limpa o que não é dígito e limita a
//    11 dígitos (DDD + 9 dígitos), pra dar feedback visual rápido; quem diz
//    a palavra final é o backend.
// 2. value/onChange trabalham só com dígitos crus (ex: "44912345678"), nunca
//    com o JID salvo no banco ("...@s.whatsapp.net"). Se o valor recebido já
//    vier em formato JID — caso comum ao editar um membro existente, onde
//    `membro.telefone` já é o JID vindo da API — o componente tira o sufixo
//    e o "55" antes de exibir. Sem isso a pessoa veria
//    "5544912345678@s.whatsapp.net" dentro do campo de edição em vez do
//    número que ela reconhece (bug real que existia em FormEditarMembro
//    antes deste componente).
import { Input } from "./styles";

function paraDigitosExibicao(valor) {
  if (!valor) return "";
  let digitos = String(valor).replace("@s.whatsapp.net", "").replace(/\D/g, "");
  if (digitos.length === 12 || digitos.length === 13) {
    if (digitos.startsWith("55")) digitos = digitos.slice(2);
  }
  return digitos;
}

export default function TelefoneInput({ id, value, onChange, placeholder = "Ex: 44912345678", ...rest }) {
  return (
    <Input
      id={id}
      type="tel"
      inputMode="numeric"
      placeholder={placeholder}
      value={paraDigitosExibicao(value)}
      onChange={(e) => onChange(e.target.value.replace(/\D/g, "").slice(0, 11))}
      {...rest}
    />
  );
}
