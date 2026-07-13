"use client";

import { useState } from "react";
import { supabase } from "@/lib/supabase";
import AuthCard from "@/components/AuthCard";
import { Field, Botao, Mensagem, LinkSecundario } from "@/components/AuthCard/styles";

export default function RecuperarSenhaPage() {
  const [email, setEmail] = useState("");
  const [mensagem, setMensagem] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setErro("");
    setMensagem("");
    setEnviando(true);
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/redefinir-senha`,
    });
    setEnviando(false);
    if (error) {
      setErro(error.message);
      return;
    }
    setMensagem("Se esse e-mail existir, enviamos um link para redefinir a senha.");
  }

  return (
    <AuthCard>
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <Field>
          <label htmlFor="email">E-mail</label>
          <input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        {mensagem && <Mensagem>{mensagem}</Mensagem>}
        {erro && <Mensagem $tipo="erro">{erro}</Mensagem>}
        <Botao type="submit" disabled={enviando}>
          {enviando ? "Enviando..." : "Enviar link de recuperação"}
        </Botao>
        <LinkSecundario href="/login">Voltar para o login</LinkSecundario>
      </form>
    </AuthCard>
  );
}
