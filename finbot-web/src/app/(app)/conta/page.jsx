"use client";

// app/(app)/conta/page.jsx — Fase 5.6 do PLANO_EXECUCAO.md: nome/apelido,
// e-mail, troca de senha, sair, exclusão de conta (LGPD, reescrita na
// Fase 7.5: só o master apaga tudo, com reautenticação por senha).
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { useTema } from "@/components/ThemeRegistry";
import { useApi } from "@/hooks/useApi";
import { supabase } from "@/lib/supabase";
import api from "@/services/api";
import Toast from "@/components/Toast";
import { Field, Botao as SalvarBtn, Mensagem } from "@/components/AuthCard/styles";

export default function ContaPage() {
  const { user, signOut } = useAuth();
  const router = useRouter();
  const [toast, setToast] = useState(null);
  const { dados: grupo } = useApi("/grupo");

  function avisar(mensagem, tipo = "sucesso") {
    setToast({ mensagem, tipo });
    setTimeout(() => setToast(null), 3000);
  }

  // "eu" dentro do grupo — cruza auth_user_id (Supabase) com a lista de
  // membros que a API devolve, mesmo truque já usado no NomeForm abaixo.
  const eu = grupo?.membros?.find((m) => m.auth_user_id === user?.id);
  const ehMaster = Boolean(eu && grupo && grupo.criador_id === eu.id);

  return (
    <div style={{ maxWidth: 420, display: "flex", flexDirection: "column", gap: 32 }}>
      <h1 style={{ fontSize: 20 }}>Conta</h1>

      <section>
        <p style={{ opacity: 0.7, fontSize: 13 }}>E-mail</p>
        <p>{user?.email}</p>
      </section>

      <TemaToggle onErro={(m) => avisar(m, "erro")} />

      <NomeForm onSalvo={() => avisar("Nome atualizado.")} onErro={(m) => avisar(m, "erro")} />
      <SenhaForm onSalvo={() => avisar("Senha alterada.")} onErro={(m) => avisar(m, "erro")} />

      <section>
        <button onClick={signOut}>Sair</button>
      </section>

      <ExclusaoConta
        ehMaster={ehMaster}
        emailUsuario={user?.email}
        onExcluida={() => router.replace("/login")}
      />

      <section>
        <button
          onClick={async () => {
            // Fase C do AUDITORIA_E_PLANO_CADASTRO.md — zera a flag no
            // backend e recarrega, pra (app)/layout.jsx buscar o status
            // atualizado e mostrar o TourPrimeiroLogin de novo.
            await api.post("/conta/tutorial-visto", { visto: false });
            window.location.reload();
          }}
          style={{ fontSize: 13, opacity: 0.7, background: "none", border: "none", cursor: "pointer" }}
        >
          Rever tutorial
        </button>
      </section>

      <a href="/politica-privacidade" target="_blank" rel="noreferrer" style={{ fontSize: 12, opacity: 0.7 }}>
        Política de Privacidade
      </a>

      <Toast mensagem={toast?.mensagem} tipo={toast?.tipo} />
    </div>
  );
}

function TemaToggle({ onErro }) {
  // Otimista: troca a tela na hora (useTema já grava no localStorage, ver
  // ThemeRegistry) e só depois confirma no backend. Se a API recusar,
  // desfaz — sem isso a pessoa clicaria e ficaria olhando pra tela parada
  // até a resposta do PUT voltar.
  const { tema, setTema } = useTema();
  const [salvando, setSalvando] = useState(false);

  async function alternar() {
    const anterior = tema;
    const novo = tema === "dark" ? "light" : "dark";
    setTema(novo);
    setSalvando(true);
    try {
      await api.put("/conta/tema", { tema: novo });
    } catch (err) {
      setTema(anterior);
      onErro(err?.response?.data?.mensagem || "Não foi possível salvar o tema.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <section>
      <p style={{ opacity: 0.7, fontSize: 13, marginBottom: 8 }}>Tema</p>
      <button onClick={alternar} disabled={salvando}>
        {tema === "dark" ? "🌙 Escuro" : "☀️ Claro"} — trocar para {tema === "dark" ? "claro" : "escuro"}
      </button>
    </section>
  );
}

function NomeForm({ onSalvo, onErro }) {
  const { user } = useAuth();
  const [nome, setNome] = useState(user?.user_metadata?.nome || "");
  const [enviando, setEnviando] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setEnviando(true);
    try {
      // Atualiza tanto o metadata do Supabase (fonte de verdade da sessão)
      // quanto o registro `usuarios` do finbot (que é o que o bot/API usa
      // de fato) — reaproveita PUT /api/grupo/membros/:id com o próprio id,
      // já que "eu" também sou um membro do meu grupo.
      await supabase.auth.updateUser({ data: { nome } });
      const { data: grupo } = await api.get("/grupo");
      const eu = grupo?.membros?.find((m) => m.auth_user_id === user.id);
      if (eu) {
        await api.put(`/grupo/membros/${eu.id}`, { nome });
      }
      onSalvo();
    } catch (err) {
      onErro(err?.response?.data?.mensagem || "Não foi possível salvar o nome.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <Field>
        <label htmlFor="nome-conta">Nome</label>
        <input id="nome-conta" value={nome} onChange={(e) => setNome(e.target.value)} />
      </Field>
      <SalvarBtn type="submit" disabled={enviando} style={{ width: "fit-content" }}>
        {enviando ? "Salvando..." : "Salvar nome"}
      </SalvarBtn>
    </form>
  );
}

function SenhaForm({ onSalvo, onErro }) {
  const [senha, setSenha] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (senha.length < 6) {
      onErro("A senha precisa ter pelo menos 6 caracteres.");
      return;
    }
    setEnviando(true);
    const { error } = await supabase.auth.updateUser({ password: senha });
    setEnviando(false);
    if (error) {
      onErro(error.message);
      return;
    }
    setSenha("");
    onSalvo();
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <Field>
        <label htmlFor="nova-senha">Nova senha</label>
        <input id="nova-senha" type="password" value={senha} onChange={(e) => setSenha(e.target.value)} />
      </Field>
      <SalvarBtn type="submit" disabled={enviando} style={{ width: "fit-content" }}>
        {enviando ? "Salvando..." : "Alterar senha"}
      </SalvarBtn>
    </form>
  );
}

function ExclusaoConta({ ehMaster, emailUsuario, onExcluida }) {
  const [senha, setSenha] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const [concordo, setConcordo] = useState(false);
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  const textoConfirmacao = ehMaster ? "EXCLUIR TUDO" : "EXCLUIR";
  const podeExcluir = senha.length > 0 && concordo && confirmacao === textoConfirmacao;

  async function handleExcluir() {
    if (!podeExcluir) return;
    setEnviando(true);
    setErro("");

    // Reautenticação por senha no cliente primeiro — dá feedback imediato
    // se a senha estiver errada, sem round-trip pro backend. Fase D1 do
    // AUDITORIA_E_PLANO_CADASTRO.md: o backend TAMBÉM valida a senha
    // server-side (enviada no body do DELETE abaixo) antes de excluir —
    // checagem no cliente sozinha não bastava (um JWT vazado/XSS ignora
    // este código e chama a API direto).
    const { error: erroSenha } = await supabase.auth.signInWithPassword({
      email: emailUsuario,
      password: senha,
    });
    if (erroSenha) {
      setErro("Senha incorreta.");
      setEnviando(false);
      return;
    }

    try {
      await api.delete("/conta", { data: { senha } });
      await supabase.auth.signOut();
      onExcluida();
    } catch (err) {
      setErro(err?.response?.data?.mensagem || "Não foi possível excluir a conta.");
      setEnviando(false);
    }
  }

  return (
    <section style={{ border: "1px solid #f2545b", borderRadius: 10, padding: 16 }}>
      <strong style={{ color: "#f2545b" }}>Excluir conta</strong>

      {ehMaster ? (
        <p style={{ fontSize: 13, opacity: 0.8, margin: "8px 0" }}>
          Você criou este grupo — excluir sua conta apaga <strong>o grupo inteiro</strong>:
          todos os membros, todos os gastos, entradas, despesas fixas e formas de
          pagamento. Também apaga seu login. <strong>Não tem como desfazer.</strong>
        </p>
      ) : (
        <p style={{ fontSize: 13, opacity: 0.8, margin: "8px 0" }}>
          Remove seus dados pessoais e sua vinculação ao grupo. Gastos e entradas já
          registrados no grupo permanecem para os demais membros — não são apagados.
          Seu login não é removido automaticamente (só o master do grupo pode pedir
          exclusão completa).
        </p>
      )}

      <Field>
        <label htmlFor="senha-exclusao">Confirme sua senha</label>
        <input
          id="senha-exclusao"
          type="password"
          value={senha}
          onChange={(e) => setSenha(e.target.value)}
        />
      </Field>

      <Field>
        <label htmlFor="confirmar-exclusao">Digite {textoConfirmacao} para confirmar</label>
        <input id="confirmar-exclusao" value={confirmacao} onChange={(e) => setConfirmacao(e.target.value)} />
      </Field>

      <label style={{ display: "flex", gap: 8, alignItems: "flex-start", fontSize: 13, marginTop: 8 }}>
        <input
          type="checkbox"
          checked={concordo}
          onChange={(e) => setConcordo(e.target.checked)}
          style={{ marginTop: 2 }}
        />
        <span>
          Entendo que essa ação é <strong>irreversível</strong>
          {ehMaster ? " e vai apagar os dados de todo o grupo, não só os meus." : "."}
        </span>
      </label>

      {erro && <Mensagem $tipo="erro">{erro}</Mensagem>}
      <button onClick={handleExcluir} disabled={!podeExcluir || enviando} style={{ marginTop: 12 }}>
        {enviando ? "Excluindo..." : "Excluir minha conta"}
      </button>
    </section>
  );
}
