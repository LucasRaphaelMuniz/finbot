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
import { CONVITE_PENDENTE_KEY, VEIO_DO_BOT_KEY, WHATSAPP_PENDENTE_KEY } from "@/utils/constants";

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
    // WhatsApp informado opcionalmente no formulário de cadastro
    // (page.jsx) — só pré-preenche o campo, o OTP abaixo continua
    // obrigatório de qualquer forma (ver utils/constants.js).
    const whatsappPendente = localStorage.getItem(WHATSAPP_PENDENTE_KEY);
    if (whatsappPendente) {
      setTelefone(whatsappPendente);
      localStorage.removeItem(WHATSAPP_PENDENTE_KEY);
    }

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
      }
      localStorage.removeItem(CONVITE_PENDENTE_KEY);
      if (codigoErro === "convite_invalido" || codigoErro === "convite_expirado") {
        setErro(err?.response?.data?.mensagem || "Convite inválido.");
        setModo("telefone");
      } else {
        setErro(err?.response?.data?.mensagem || "Não foi possível validar o convite.");
        setModo("telefone");
      }
    }
  }

  async function enviarCodigo(e) {
    e.preventDefault();
    setErro("");
    setEnviando(true);
    try {
      await api.post("/verificacao/enviar", { telefone });
      setModo(modo === "convite_telefone" ? "convite_codigo" : "codigo");
    } catch (err) {
      setErro(err?.response?.data?.mensagem || "Não foi possível enviar o código.");
    } finally {
      setEnviando(false);
    }
  }

  async function confirmarCodigo(e) {
    e.preventDefault();
    setErro("");
    setEnviando(true);
    try {
      const { data } = await api.post("/verificacao/confirmar", { telefone, codigo: codigoOtp });
      setResultadoVerificacao(data);

      if (modo === "convite_codigo") {
        await api.post("/convites/aceitar", { codigo: codigoConvite, telefone });
        localStorage.removeItem(CONVITE_PENDENTE_KEY);
        onConcluido();
        return;
      }

      // Caminho onboarding: se já existia cadastro do bot COM grupo, não
      // precisa perguntar mais nada — o "puxa tudo" acontece direto.
      if (data.ja_existia && data.tem_grupo) {
        sessionStorage.setItem(VEIO_DO_BOT_KEY, "true");
        await api.post("/onboarding", { telefone });
        onConcluido();
        return;
      }

      sessionStorage.setItem(VEIO_DO_BOT_KEY, data.ja_existia ? "true" : "false");
      setModo("grupo");
    } catch (err) {
      setErro(err?.response?.data?.mensagem || "Código incorreto.");
    } finally {
      setEnviando(false);
    }
  }

  async function handleSubmitGrupo(e) {
    e.preventDefault();
    setErro("");
    setEnviando(true);
    try {
      await api.post("/onboarding", { nome_grupo: nomeGrupo, telefone });
      onConcluido();
    } catch (err) {
      setErro(err?.response?.data?.mensagem || "Não foi possível concluir o cadastro.");
    } finally {
      setEnviando(false);
    }
  }

  if (modo === "verificando" || modo === "convite_tentando") {
    return (
      <Wrap>
        <Loading />
      </Wrap>
    );
  }

  if (modo === "telefone" || modo === "convite_telefone") {
    return (
      <Wrap>
        <Box>
          <strong>Só mais um passo</strong>
          <p style={{ fontSize: 13, opacity: 0.7 }}>
            Informe seu WhatsApp (com DDD) — vamos mandar um código de verificação
            por lá pra confirmar que é você.
          </p>
          <form onSubmit={enviarCodigo} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <Field>
              <label htmlFor="telefone">Seu WhatsApp</label>
              <TelefoneInput id="telefone" required value={telefone} onChange={setTelefone} />
            </Field>
            {erro && <Mensagem $tipo="erro">{erro}</Mensagem>}
            <Botao type="submit" disabled={enviando || !telefone}>
              {enviando ? "Enviando código..." : "Enviar código pelo WhatsApp"}
            </Botao>
          </form>
        </Box>
      </Wrap>
    );
  }

  if (modo === "codigo" || modo === "convite_codigo") {
    return (
      <Wrap>
        <Box>
          <strong>Digite o código</strong>
          <p style={{ fontSize: 13, opacity: 0.7 }}>
            Mandamos um código de 6 dígitos pro seu WhatsApp. Ele vale por 10 minutos.
          </p>
          <form onSubmit={confirmarCodigo} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <Field>
              <label htmlFor="codigo-otp">Código de verificação</label>
              <input
                id="codigo-otp"
                required
                inputMode="numeric"
                maxLength={6}
                placeholder="000000"
                value={codigoOtp}
                onChange={(e) => setCodigoOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
              />
            </Field>
            {erro && <Mensagem $tipo="erro">{erro}</Mensagem>}
            <Botao type="submit" disabled={enviando || codigoOtp.length !== 6}>
              {enviando ? "Confirmando..." : "Confirmar"}
            </Botao>
          </form>
        </Box>
      </Wrap>
    );
  }

  // modo === "grupo" — só chega aqui quando não achou grupo existente pra
  // reaproveitar (número novo, ou número do bot sem grupo ainda).
  return (
    <Wrap>
      <Box>
        <strong>
          {resultadoVerificacao?.ja_existia ? "Encontramos seu WhatsApp!" : "Só mais um passo"}
        </strong>
        {resultadoVerificacao?.ja_existia && (
          <p style={{ fontSize: 13, opacity: 0.7 }}>
            Você já usava o bot por esse número. Só falta dar um nome pro grupo.
          </p>
        )}
        <form onSubmit={handleSubmitGrupo} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <Field>
            <label htmlFor="nomeGrupo">Nome do grupo (ex: Família Silva)</label>
            <input id="nomeGrupo" required value={nomeGrupo} onChange={(e) => setNomeGrupo(e.target.value)} />
          </Field>
          {erro && <Mensagem $tipo="erro">{erro}</Mensagem>}
          <Botao type="submit" disabled={enviando}>
            {enviando ? "Salvando..." : "Concluir cadastro"}
          </Botao>
        </form>
      </Box>
    </Wrap>
  );
}
