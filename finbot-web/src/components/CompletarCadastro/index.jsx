"use client";

// components/CompletarCadastro — passo final do cadastro, rodado dentro do
// guard de (app)/layout.jsx quando existe sessão Supabase mas o backend
// ainda não tem usuario/grupo (ver contrato assumido em (app)/layout.jsx).
//
// Reescrito na Fase B do AUDITORIA_E_PLANO_CADASTRO.md: antes, qualquer
// telefone digitado era aceito de cara — se já existisse um usuario com
// aquele número (criado pelo bot), o cadastro web "herdava" o histórico
// dele sem nenhuma prova de que a pessoa realmente é dona daquele WhatsApp
// (F2, vulnerabilidade). Agora todo telefone informado pelo FORMULÁRIO passa
// por verificação OTP (código de 6 dígitos mandado pelo bot) antes do
// backend usá-lo pra qualquer merge — ver services/verificacao.py.
//
// Dois caminhos, que convergem no mesmo passo de verificação:
// 1. Convite (código em localStorage) → tenta aceitar direto (cobre o caso
//    de o dono já ter pré-vinculado o número via `grupo add` no bot — nesse
//    caso o backend não pede telefone nem OTP, o dono já atestou o número).
//    Se o backend responder "telefone_obrigatorio", pede telefone → OTP →
//    reenvia a aceitação já com o telefone confirmado.
// 2. Cadastro do zero → pede telefone → OTP → conforme a resposta da
//    verificação (achou cadastro do bot? já tem grupo?), pula direto pro
//    onboarding ou pede nome do grupo antes.
import { useEffect, useState } from "react";
import api from "@/services/api";
import { Wrap, Box } from "./styles";
import { Field, Botao, Mensagem } from "@/components/AuthCard/styles";
import Loading from "@/components/Loading";
import TelefoneInput from "@/components/TelefoneInput";
import { CONVITE_PENDENTE_KEY, VEIO_DO_BOT_KEY } from "@/utils/constants";

// modos possíveis:
// verificando -> (convite_tentando | telefone)
// convite_tentando -> (convite_telefone | concluído)
// convite_telefone -> convite_codigo
// convite_codigo -> concluído (via aceitar_convite)
// telefone -> codigo
// codigo -> (concluído via onboarding direto | grupo)
// grupo -> concluído (via onboarding)
export default function CompletarCadastro({ onConcluido }) {
  const [modo, setModo] = useState("verificando");
  const [codigoConvite, setCodigoConvite] = useState(null);
  const [nomeGrupo, setNomeGrupo] = useState("");
  const [telefone, setTelefone] = useState("");
  const [codigoOtp, setCodigoOtp] = useState("");
  const [resultadoVerificacao, setResultadoVerificacao] = useState(null);
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    const codigoPendente = localStorage.getItem(CONVITE_PENDENTE_KEY);
    if (codigoPendente) {
      setCodigoConvite(codigoPendente);
      tentarAceitarConviteSemTelefone(codigoPendente);
    } else {
      setModo("telefone");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function tentarAceitarConviteSemTelefone(codigo) {
    try {
      await api.post("/convites/aceitar", { codigo });
      localStorage.removeItem(CONVITE_PENDENTE_KEY);
      onConcluido();
    } catch (err) {
      const codigoErro = err?.response?.data?.erro;
      if (codigoErro === "telefone_obrigatorio") {
        setModo("convite_telefone");
        return;