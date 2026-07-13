"use client";

// app/(app)/importacao/page.jsx — Fase 5.3 do PLANO_EXECUCAO.md: upload de
// fatura (PDF/CSV) → revisão editável → confirmação em lote. Nada entra no
// banco antes do passo 3 (POST /api/importacao/confirmar) — os passos 1-2
// só leem o arquivo e mostram uma prévia.
//
// Aviso: o caminho PDF depende de ai.py:extrair_lancamentos_fatura, que
// NÃO foi testado contra uma fatura real (sem chave de API/arquivo de
// exemplo no ambiente de desenvolvimento). O caminho CSV é determinístico
// e tem testes automatizados (tests/test_importacao.py).
import { useState } from "react";
import api from "@/services/api";
import { brl, formatarDataBR } from "@/utils/format";
import FormaSelect from "@/components/FormaSelect";
import CategoriaSelect from "@/components/CategoriaSelect";
import Toast from "@/components/Toast";
import Loading from "@/components/Loading";
import { Card, AvisoDuplicata } from "./styles";

export default function ImportacaoPage() {
  const [formaId, setFormaId] = useState(null);
  const [arquivo, setArquivo] = useState(null);
  const [preview, setPreview] = useState(null); // {arquivo_nome, forma_pagamento_id, linhas}
  const [enviando, setEnviando] = useState(false);
  const [confirmando, setConfirmando] = useState(false);
  const [importacaoConcluida, setImportacaoConcluida] = useState(null);
  const [toast, setToast] = useState(null);

  function avisar(mensagem, tipo = "sucesso") {
    setToast({ mensagem, tipo });
    setTimeout(() => setToast(null), 4000);
  }

  async function handleUpload(e) {
    e.preventDefault();
    if (!arquivo || !formaId) {
      avisar("Selecione o arquivo e a forma de pagamento.", "erro");
      return;
    }
    setEnviando(true);
    try {
      const formData = new FormData();
      formData.append("arquivo", arquivo);
      formData.append("forma_pagamento_id", formaId);
      const { data } = await api.post("/importacao/upload", formData);
      const linhasComEstado = data.linhas.map((l) => ({
        ...l,
        incluir: !l.duplicata_provavel, // duplicata provável some desmarcada por padrão
        categoria_id: null,
      }));
      setPreview({ ...data, linhas: linhasComEstado });
    } catch (err) {
      avisar(err?.response?.data?.mensagem || "Não foi possível ler o arquivo.", "erro");
    } finally {
      setEnviando(false);
    }
  }

  function atualizarLinha(index, campo, valor) {
    setPreview((p) => ({
      ...p,
      linhas: p.linhas.map((l, i) => (i === index ? { ...l, [campo]: valor } : l)),
    }));
  }

  async function handleConfirmar() {
    const linhasIncluidas = preview.linhas.filter((l) => l.incluir);
    if (linhasIncluidas.length === 0) {
      avisar("Nenhum lançamento selecionado.", "erro");
      return;
    }
    if (linhasIncluidas.some((l) => !l.categoria_id)) {
      avisar("Escolha uma categoria para cada lançamento incluído.", "erro");
      return;
    }
    setConfirmando(true);
    try {
      const { data } = await api.post("/importacao/confirmar", {
        forma_pagamento_id: preview.forma_pagamento_id,
        arquivo_nome: preview.arquivo_nome,
        linhas: linhasIncluidas,
      });
      setImportacaoConcluida(data);
      setPreview(null);
      avisar(`${linhasIncluidas.length} lançamento(s) importado(s)!`);
    } catch (err) {
      avisar(err?.response?.data?.mensagem || "Não foi possível confirmar a importação.", "erro");
    } finally {
      setConfirmando(false);
    }
  }

  async function handleDesfazer() {
    try {
      await api.delete(`/importacao/${importacaoConcluida.id}`);
      avisar("Importação desfeita.");
      setImportacaoConcluida(null);
    } catch (err) {
      avisar(err?.response?.data?.mensagem || "Não foi possível desfazer.", "erro");
    }
  }

  return (
    <div>
      <h1 style={{ fontSize: 20, marginBottom: 24 }}>Importar fatura</h1>

      {importacaoConcluida ? (
        <Card>
          <p>✅ Importação concluída: {importacaoConcluida.linhas} lançamento(s) adicionado(s).</p>
          <button onClick={handleDesfazer} style={{ marginTop: 12 }}>Desfazer importação</button>
          <button onClick={() => setImportacaoConcluida(null)} style={{ marginTop: 12, marginLeft: 8 }}>
            Importar outra fatura
          </button>
        </Card>
      ) : !preview ? (
        <Card>
          <form onSubmit={handleUpload} style={{ display: "flex", flexDirection: "column", gap: 16, maxWidth: 420 }}>
            <div>
              <label style={{ fontSize: 13, opacity: 0.7 }}>Arquivo (PDF ou CSV)</label>
              <br />
              <input
                type="file" accept=".pdf,.csv"
                onChange={(e) => setArquivo(e.target.files?.[0] || null)}
              />
            </div>
            <div>
              <label style={{ fontSize: 13, opacity: 0.7 }}>Forma de pagamento</label>
              <FormaSelect value={formaId} onChange={setFormaId} />
            </div>
            <button type="submit" disabled={enviando}>
              {enviando ? "Lendo arquivo..." : "Enviar e revisar"}
            </button>
          </form>
        </Card>
      ) : (
        <Card>
          <p style={{ marginBottom: 16 }}>
            {preview.linhas.length} lançamento(s) encontrado(s) em <strong>{preview.arquivo_nome}</strong>.
            Revise, ajuste a categoria e desmarque o que não quiser importar.
          </p>

          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead>
              <tr>
                <th></th>
                <th style={{ textAlign: "left" }}>Data</th>
                <th style={{ textAlign: "left" }}>Descrição</th>
                <th style={{ textAlign: "left" }}>Categoria</th>
                <th style={{ textAlign: "right" }}>Valor</th>
              </tr>
            </thead>
            <tbody>
              {preview.linhas.map((linha, i) => (
                <tr key={i}>
                  <td>
                    <input
                      type="checkbox" checked={linha.incluir}
                      onChange={(e) => atualizarLinha(i, "incluir", e.target.checked)}
                    />
                  </td>
                  <td>{formatarDataBR(linha.data)}</td>
                  <td>
                    {linha.descricao}
                    {linha.duplicata_provavel && (
                      <AvisoDuplicata>⚠ possível duplicata</AvisoDuplicata>
                    )}
                  </td>
                  <td>
                    <CategoriaSelect
                      value={linha.categoria_id}
                      onChange={(v) => atualizarLinha(i, "categoria_id", v)}
                    />
                  </td>
                  <td style={{ textAlign: "right" }}>{brl(linha.valor)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div style={{ display: "flex", gap: 8, marginTop: 24 }}>
            <button onClick={() => setPreview(null)}>Cancelar</button>
            <button onClick={handleConfirmar} disabled={confirmando}>
              {confirmando ? "Importando..." : "Confirmar importação"}
            </button>
          </div>
        </Card>
      )}

      <Toast mensagem={toast?.mensagem} tipo={toast?.tipo} />
    </div>
  );
}
