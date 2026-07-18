"use client";

// (auth)/cadastro — cria a conta (Supabase Auth). A criação do grupo/usuario
// no backend (POST /api/onboarding ou /api/convites/aceitar, ver §4.3 do
// PLANO_EXECUCAO.md) só roda DEPOIS que existe uma sessão autenticada —
// e isso só acontece após a confirmação de e-mail, na maioria dos projetos
// Supabase (confirmação habilitada por padrão). Por isso esse passo final
// não roda aqui: ele fica no guard de (app)/layout.jsx, que detecta "sessão
// existe mas backend não tem usuario/grupo ainda" e completa o cadastro
// antes de liberar o dashboard. O código do convite atravessa esse hiato
// (signup → confirmação de e-mail → 1º login) via localStorage, porque o
// clique no link de confirmação recarrega a página do zero.
import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { supabase } from "@/lib/supabase";
import AuthCard from "@/components/AuthCard";
import { Field, Botao, Mensagem, LinkSecundario } from "@/components/AuthCard/styles";
import TelefoneInput from "@/components/TelefoneInput";
import { CONVITE_PENDENTE_KEY, WHATSAPP_PENDENTE_KEY } from "@/utils/constants";

export default function CadastroPage() {
  const searchParams = useSearchParams();
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [whatsapp, setWhatsapp] = useState("");
  const [codigoConvite, setCodigoConvite] = useState(searchParams.get("convite") || "");
  const [erro, setErro] = useState("");
  const [mensagem, setMensagem] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setErro("");
    setMensagem("");
    setEnviando(true);

    const { data, error } = await supabase.auth.signUp({
      email,
      password: senha,
      options: { data: { nome } },
    });

    setEnviando(false);
    if (error) {
      setErro(error.message);
      return;
    }

    if (codigoConvite.trim()) {
      localStorage.setItem(CONVITE_PENDENTE_KEY, codigoConvite.trim());
    }
    // Só guarda o dígitos crus — o OTP em CompletarCadastro é quem valida
    // de verdade (ver comentário em utils/constants.js). Isso é só
    // pré-preenchimento pra pessoa não digitar o número 2x.
    if (whatsapp.trim()) {
      localStorage.setItem(WHATSAPP_PENDENTE_KEY, whatsapp.trim());
    }

    if (!data.session) {
      // Confirmação de e-mail habilitada — sem sessão ainda. O signup fica
      // "pendente" até o clique no link recebido por e-mail.
      setMensagem("Conta criada! Confirme seu e-mail para poder entrar.");
      return;
    }

    // Auto-confirm habilitado no projeto Supabase — já existe sessão.
    // (app)/layout.jsx cuida de completar o cadastro (onboarding) e liberar
    // o dashboard a partir daqui.
    window.location.href = "/dashboard";
  }

  return (
    <AuthCard>
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <Field>
          <label htmlFor="nome">Seu nome</label>
          <input id="nome" required value={nome} onChange={(e) => setNome(e.target.value)} />
        </Field>
        <Field>
          <label htmlFor="email">E-mail</label>
          <input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field>
          <label htmlFor="senha">Senha</label>
          <input
            id="senha"
            type="password"
            required
            minLength={6}
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
          />
        </Field>
        <Field>
          <label htmlFor="whatsapp">Seu WhatsApp (opcional)</label>
          <TelefoneInput id="whatsapp" value={whatsapp} onChange={setWhatsapp} />
          <small style={{ fontSize: 12, opacity: 0.7 }}>
            Informe agora pra pular esse passo depois — de qualquer forma,
            vamos confirmar por código enviado pelo WhatsApp.
          </small>
        </Field>
        <Field>
          <label htmlFor="convite">Código de convite (opcional)</label>
          <input
            id="convite"
            placeholder="FIN-8K3M2P"
            value={codigoConvite}
            onChange={(e) => setCodigoConvite(e.target.value)}
          />
        </Field>
        {mensagem && <Mensagem>{mensagem}</Mensagem>}
        {erro && <Mensagem $tipo="erro">{erro}</Mensagem>}
        <Botao type="submit" disabled={enviando}>
          {enviando ? "Criando conta..." : "Criar conta"}
        </Botao>
        <p style={{ fontSize: 12, opacity: 0.7, textAlign: "center" }}>
          Ao criar sua conta, você concorda com nossa{" "}
          <a href="/politica-privacidade" target="_blank" rel="noreferrer">
            Política de Privacidade
          </a>.
        </p>
        <LinkSecundario href="/login">Já tem conta? Entrar</LinkSecundario>
      </form>
    </AuthCard>
  );
}
