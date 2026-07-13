"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import AuthCard from "@/components/AuthCard";
import { Field, Botao, Mensagem, LinkSecundario } from "@/components/AuthCard/styles";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setErro("");
    setEnviando(true);
    const { error } = await supabase.auth.signInWithPassword({ email, password: senha });
    setEnviando(false);
    if (error) {
      setErro(traduzirErro(error.message));
      return;
    }
    router.replace("/dashboard");
  }

  return (
    <AuthCard>
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <Field>
          <label htmlFor="email">E-mail</label>
          <input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field>
          <label htmlFor="senha">Senha</label>
          <input id="senha" type="password" required value={senha} onChange={(e) => setSenha(e.target.value)} />
        </Field>
        {erro && <Mensagem $tipo="erro">{erro}</Mensagem>}
        <Botao type="submit" disabled={enviando}>
          {enviando ? "Entrando..." : "Entrar"}
        </Botao>
        <LinkSecundario href="/recuperar-senha">Esqueci minha senha</LinkSecundario>
        <LinkSecundario href="/cadastro">Não tem conta? Cadastre-se</LinkSecundario>
      </form>
    </AuthCard>
  );
}

// Supabase devolve mensagens em inglês por padrão — traduzir os casos mais
// comuns evita expor jargão técnico pro usuário final do web.
function traduzirErro(msg) {
  if (/invalid login credentials/i.test(msg)) return "E-mail ou senha incorretos.";
  if (/email not confirmed/i.test(msg)) return "Confirme seu e-mail antes de entrar.";
  return msg;
}
