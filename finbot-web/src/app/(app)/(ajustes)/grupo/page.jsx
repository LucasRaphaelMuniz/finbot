"use client";

// app/(app)/grupo/page.jsx — Fase 5.4 do PLANO_EXECUCAO.md: nome do grupo,
// membros (apelido/telefone/conta web?), editar/remover membro, gerar
// convite (código + link), convites pendentes/expirados.
import { useState } from "react";
import { useApi } from "@/hooks/useApi";
import api from "@/services/api";
import DataTable from "@/components/DataTable";
import { AcaoBtn } from "@/components/DataTable/styles";
import Modal from "@/components/Modal";
import ConfirmDialog from "@/components/ConfirmDialog";
import Toast from "@/components/Toast";
import { Field, Botao as BotaoAuth } from "@/components/AuthCard/styles";
import TelefoneInput from "@/components/TelefoneInput";
import { Secao, SecaoHeader, Titulo, NomeGrupoForm, InputInline, Botao, CodigoBox, CampoTelefone, ErroCampo } from "./styles";
import { formatarTelefoneExibicao } from "@/utils/format";

export default function GrupoPage() {
  const { dados: grupo, loading, refetch } = useApi("/grupo");
  const { dados: convitesData, refetch: refetchConvites } = useApi("/convites");
  const [toast, setToast] = useState(null);
  const [nomeGrupo, setNomeGrupo] = useState(null); // null = ainda não editado
  const [membroEditando, setMembroEditando] = useState(null);
  const [membroRemovendo, setMembroRemovendo] = useState(null);
  const [gerandoConvite, setGerandoConvite] = useState(false);
  const [ultimoConvite, setUltimoConvite] = useState(null);
  const [telefoneNovoMembro, setTelefoneNovoMembro] = useState("");
  const [adicionandoMembro, setAdicionandoMembro] = useState(false);
  // Erro inline do telefone (auditoria de UX): o botão ficava desabilitado
  // até digitar algo, sem explicar por quê. Agora o botão está sempre
  // ativo; validação no blur/submit, e o erro some ao editar o campo.
  const [erroTelefone, setErroTelefone] = useState("");

  function validarTelefone(valor) {
    if (!valor) return "Informe o telefone com DDD.";
    if (valor.length < 10) return "Telefone incompleto: use DDD + número (10 ou 11 dígitos).";
    return "";
  }

  function avisar(mensagem, tipo = "sucesso") {
    setToast({ mensagem, tipo });
    setTimeout(() => setToast(null), 3000);
  }

  async function adicionarMembroPorTelefone(e) {
    e.preventDefault();
    const erro = validarTelefone(telefoneNovoMembro);
    setErroTelefone(erro);
    if (erro) return;
    setAdicionandoMembro(true);
    try {
      // Equivalente web do comando "grupo add 44912345678" do bot — mesmo
      // endpoint (POST /api/grupo/membros) que já existia no backend desde
      // a Fase 4.3, só faltava um formulário na tela usando ele: até aqui
      // só dava pra adicionar gente por convite (código/link), nunca direto
      // por telefone como no bot.
      await api.post("/grupo/membros", { telefone: telefoneNovoMembro });
      avisar("Membro adicionado ao grupo!");
      setTelefoneNovoMembro("");
      refetch();
    } catch (err) {
      avisar(err?.response?.data?.mensagem || "Não foi possível adicionar.", "erro");
    } finally {
      setAdicionandoMembro(false);
    }
  }

  async function salvarNomeGrupo(e) {
    e.preventDefault();
    try {
      await api.put("/grupo", { nome: nomeGrupo });
      avisar("Nome do grupo atualizado.");
      setNomeGrupo(null);
      refetch();
    } catch (err) {
      avisar(err?.response?.data?.mensagem || "Não foi possível salvar.", "erro");
    }
  }

  async function gerarConvite() {
    setGerandoConvite(true);
    try {
      const { data } = await api.post("/convites", {});
      setUltimoConvite(data);
      refetchConvites();
    } catch (err) {
      avisar(err?.response?.data?.mensagem || "Não foi possível gerar o convite.", "erro");
    } finally {
      setGerandoConvite(false);
    }
  }

  async function removerMembro() {
    try {
      await api.delete(`/grupo/membros/${membroRemovendo.id}`);
      avisar("Membro removido do grupo.");
      setMembroRemovendo(null);
      refetch();
    } catch (err) {
      avisar(err?.response?.data?.mensagem || "Não foi possível remover.", "erro");
    }
  }

  const linkConvite = ultimoConvite
    ? `${typeof window !== "undefined" ? window.location.origin : ""}/convite/${ultimoConvite.codigo}`
    : null;

  return (
    <div>
      <h2 style={{ fontSize: 17, marginBottom: 16 }}>Grupo</h2>
      <Secao>
        <SecaoHeader>
          <Titulo id="titulo-nome-grupo">Nome do grupo</Titulo>
        </SecaoHeader>
        {!loading && grupo && (
          <NomeGrupoForm onSubmit={salvarNomeGrupo}>
            <InputInline
              aria-labelledby="titulo-nome-grupo"
              value={nomeGrupo ?? grupo.nome}
              onChange={(e) => setNomeGrupo(e.target.value)}
            />
            <Botao type="submit">Salvar nome</Botao>
          </NomeGrupoForm>
        )}
      </Secao>

      <Secao>
        <SecaoHeader>
          <Titulo>Membros</Titulo>
        </SecaoHeader>

        <CampoTelefone>
          <label htmlFor="telefone-novo-membro">Adicionar por WhatsApp (DDD + número)</label>
          <NomeGrupoForm onSubmit={adicionarMembroPorTelefone} noValidate>
            <div style={{ flex: "1 1 200px" }}>
              <TelefoneInput
                id="telefone-novo-membro"
                value={telefoneNovoMembro}
                onChange={(v) => {
                  setTelefoneNovoMembro(v);
                  if (erroTelefone) setErroTelefone("");
                }}
                onBlur={() => telefoneNovoMembro && setErroTelefone(validarTelefone(telefoneNovoMembro))}
                placeholder="44912345678"
                aria-invalid={!!erroTelefone}
                aria-describedby={erroTelefone ? "erro-telefone-novo-membro" : undefined}
              />
            </div>
            <Botao type="submit" disabled={adicionandoMembro}>
              {adicionandoMembro ? "Adicionando..." : "Adicionar membro"}
            </Botao>
          </NomeGrupoForm>
          {erroTelefone && <ErroCampo id="erro-telefone-novo-membro">{erroTelefone}</ErroCampo>}
        </CampoTelefone>

        <DataTable
          columns={[
            { key: "nome", label: "Nome" },
            { key: "telefone", label: "Telefone", render: (m) => formatarTelefoneExibicao(m.telefone) },
            { key: "conta_web", label: "Conta web?", render: (m) => (m.auth_user_id ? "Sim" : "Não") },
          ]}
          rows={grupo?.membros}
          loading={loading}
          vazio={{ titulo: "Nenhum membro ainda" }}
          acoes={(m) => (
            <>
              <AcaoBtn onClick={() => setMembroEditando(m)}>Editar</AcaoBtn>
              <AcaoBtn $perigo onClick={() => setMembroRemovendo(m)}>Remover</AcaoBtn>
            </>
          )}
        />
      </Secao>

      <Secao>
        <SecaoHeader>
          <Titulo>Convites</Titulo>
          <Botao onClick={gerarConvite} disabled={gerandoConvite}>
            {gerandoConvite ? "Gerando..." : "+ Gerar convite"}
          </Botao>
        </SecaoHeader>

        {ultimoConvite && (
          <CodigoBox style={{ marginBottom: 16 }}>
            <div>
              <strong>{ultimoConvite.codigo}</strong>
              <div style={{ fontSize: 12, opacity: 0.7 }}>{linkConvite}</div>
            </div>
            <Botao
              type="button"
              onClick={() => {
                navigator.clipboard?.writeText(linkConvite);
                avisar("Link copiado!");
              }}
            >
              Copiar link
            </Botao>
          </CodigoBox>
        )}

        <DataTable
          columns={[
            { key: "codigo", label: "Código" },
            {
              key: "status",
              label: "Status",
              render: (c) =>
                c.usado_em ? "Usado" :
                new Date(c.expira_em) < new Date() ? "Expirado" : "Pendente",
            },
          ]}
          rows={convitesData?.itens}
          loading={!convitesData}
          vazio={{ titulo: "Nenhum convite gerado ainda" }}
        />
      </Secao>

      {membroEditando && (
        <Modal aberto titulo="Editar membro" onFechar={() => setMembroEditando(null)}>
          <FormEditarMembro
            membro={membroEditando}
            onSalvo={() => {
              setMembroEditando(null);
              avisar("Membro atualizado.");
              refetch();
            }}
            onErro={(msg) => avisar(msg, "erro")}
          />
        </Modal>
      )}

      <ConfirmDialog
        aberto={!!membroRemovendo}
        titulo="Remover membro"
        textoConfirmar="Remover membro"
        mensagem={`Remover ${membroRemovendo?.nome} do grupo? A pessoa volta a ter uma conta individual.`}
        onConfirmar={removerMembro}
        onCancelar={() => setMembroRemovendo(null)}
      />

      <Toast mensagem={toast?.mensagem} tipo={toast?.tipo} />
    </div>
  );
}

function FormEditarMembro({ membro, onSalvo, onErro }) {
  const [nome, setNome] = useState(membro.nome || "");
  const [telefone, setTelefone] = useState(membro.telefone || "");
  const [enviando, setEnviando] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setEnviando(true);
    try {
      await api.put(`/grupo/membros/${membro.id}`, { nome, telefone });
      onSalvo();
    } catch (err) {
      onErro(err?.response?.data?.mensagem || "Não foi possível salvar.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Field>
        <label htmlFor="nome-membro">Nome</label>
        <input id="nome-membro" value={nome} onChange={(e) => setNome(e.target.value)} />
      </Field>
      <Field>
        <label htmlFor="telefone-membro">Telefone</label>
        <TelefoneInput id="telefone-membro" value={telefone} onChange={setTelefone} />
      </Field>
      <BotaoAuth type="submit" disabled={enviando}>
        {enviando ? "Salvando..." : "Salvar"}
      </BotaoAuth>
    </form>
  );
}
