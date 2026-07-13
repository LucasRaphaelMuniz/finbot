"use client";

// (auth)/redefinir-senha — acessada via link do e-mail de recuperação.
// O Supabase já injeta uma sessão temporária a partir do token do link
// (ver detecção de sessão em hooks/useAuth via onAuthStateChange), então
// aqui só chamamos updateUser com a senha nova.
import { useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import AuthCard from "@/components/AuthCard";
import { Field, Botao, Mensagem } from "@/components/AuthCard/styles";

export default function RedefinirSenhaPage() {
  const router = useRouter();
  const [senha, setSenha] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setErro("");
    if (senha !== confirmacao) {
      setErro("As senhas não coincidem.");
      return;
    }
    if (senha.length < 6) {
      setErro("A senha precisa ter pelo menos 6 caracteres.");
      return;
    }
    setEnviando(true);
    const { error } = await supabase.auth.updateUser({ password: senha });
    setEnviando(false);
    if (error) {
      setErro(error.message);
      return;
    }
    router.replace("/login");
  }

  return (
    <AuthCard>
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <Field>
          <label htmlFor="senha">Nova senha</label>
          <input id="senha" type="password" required value={senha} onChange={(e) => setSenha(e.target.value)} />
        </Field>
        <Field>
          <label htmlFor="confirmacao">Confirme a nova senha</label>
          <input
            id="confirmacao"
            type="password"
            required
            value={confirmacao}
            onChange={(e) => setConfirmacao(e.target.value)}
          />
        </Field>
        {erro && <Mensagem $tipo="erro">{erro}</Mensagem>}
        <Botao type="submit" disabled={enviando}>
          {enviando ? "Salvando..." : "Salvar nova senha"}
        </Botao>
      </form>
    </AuthCard>
  );
}
