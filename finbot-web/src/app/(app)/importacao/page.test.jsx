// page.test.jsx — Fase 7 do PLANO_EXECUCAO.md ("Jest/RTL ... rotas críticas
// (revisão de fatura...)"). Cobre a parte que mais importa dessa tela: nada
// pode ir pro banco sem passar pela revisão explícita (checkbox "incluir" +
// categoria escolhida) — ver services/importacao.py:confirmar_importacao e
// o comentário no topo de page.jsx ("Nada entra no banco antes do passo 3").
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ImportacaoPage from "./page";
import api from "@/services/api";

jest.mock("@/services/api", () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn(), delete: jest.fn() },
}));

const FORMAS = { itens: [{ id: 1, nome: "Cartão" }] };
const CATEGORIAS = { itens: [{ id: 10, nome: "Mercado", grupo_id: null }] };

const PREVIEW_RESPOSTA = {
  arquivo_nome: "fatura.csv",
  forma_pagamento_id: 1,
  linhas: [
    { data: "2026-07-01", descricao: "Supermercado X", valor: 150.5, duplicata_provavel: false },
    { data: "2026-07-03", descricao: "Posto Y", valor: 200, duplicata_provavel: true },
  ],
};

function mockApiGet() {
  api.get.mockImplementation((url) => {
    if (url === "/formas") return Promise.resolve({ data: FORMAS });
    if (url === "/categorias") return Promise.resolve({ data: CATEGORIAS });
    return Promise.resolve({ data: {} });
  });
}

beforeEach(() => {
  jest.clearAllMocks();
  mockApiGet();
});

async function chegarNaRevisao(user) {
  render(<ImportacaoPage />);

  const arquivo = new File(["data"], "fatura.csv", { type: "text/csv" });
  const inputArquivo = document.querySelector('input[type="file"]');
  await user.upload(inputArquivo, arquivo);

  // FormaSelect é populado de forma assíncrona (useApi -> GET /formas).
  await waitFor(() => expect(screen.getByRole("option", { name: "Cartão" })).toBeInTheDocument());
  await user.selectOptions(screen.getByDisplayValue("Selecione...") || screen.getAllByRole("combobox")[0], "1");

  api.post.mockResolvedValueOnce({ data: PREVIEW_RESPOSTA });
  await user.click(screen.getByRole("button", { name: /enviar e revisar/i }));

  await waitFor(() => expect(screen.getByText(/Supermercado X/)).toBeInTheDocument());
}

test("linha com duplicata provável some desmarcada por padrão na revisão", async () => {
  const user = userEvent.setup();
  await chegarNaRevisao(user);

  const checkboxes = screen.getAllByRole("checkbox");
  // 1ª linha (não duplicata) marcada, 2ª (duplicata_provavel) desmarcada —
  // services/importacao.py já resolve isso no backend, o front só reflete.
  expect(checkboxes[0]).toBeChecked();
  expect(checkboxes[1]).not.toBeChecked();
});

test("bloqueia a confirmação se algum lançamento incluído não tem categoria", async () => {
  const user = userEvent.setup();
  await chegarNaRevisao(user);

  await user.click(screen.getByRole("button", { name: /confirmar importação/i }));

  expect(await screen.findByText(/escolha uma categoria/i)).toBeInTheDocument();
  expect(api.post).not.toHaveBeenCalledWith("/importacao/confirmar", expect.anything());
});

test("confirma só os lançamentos marcados, com categoria, e nada mais", async () => {
  const user = userEvent.setup();
  await chegarNaRevisao(user);

  await waitFor(() => expect(screen.getByRole("option", { name: "Mercado (padrão)" })).toBeInTheDocument());
  const categoriaSelects = screen.getAllByRole("combobox").filter((el) => el.id === undefined || true);
  // 1º combobox restante após o de forma é o CategoriaSelect da 1ª linha
  // (única linha marcada por padrão, já que a 2ª veio com duplicata_provavel).
  const categoriaDaLinha1 = screen.getAllByRole("option", { name: "Mercado (padrão)" })[0].closest("select");
  await user.selectOptions(categoriaDaLinha1, "10");

  api.post.mockResolvedValueOnce({ data: { id: 1, linhas: 1 } });
  await user.click(screen.getByRole("button", { name: /confirmar importação/i }));

  await waitFor(() =>
    expect(api.post).toHaveBeenCalledWith(
      "/importacao/confirmar",
      expect.objectContaining({
        forma_pagamento_id: 1,
        arquivo_nome: "fatura.csv",
        linhas: [expect.objectContaining({ descricao: "Supermercado X", categoria_id: 10 })],
      })
    )
  );
  expect(await screen.findByText(/1 lançamento\(s\) importado/i)).toBeInTheDocument();
});
