// page.test.jsx — Fase 7.5 do PLANO_EXECUCAO.md (revisão do Lucas em
// 11/07/2026): exclusão de conta virou uma ação destrutiva e irreversível
// pro master do grupo (apaga tudo, inclusive o login). Esses testes cobrem
// exatamente as travas que impedem apagar por engano — é a parte mais
// arriscada da tela, por isso é a que mais vale testar.
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ContaPage from "./page";
import api from "@/services/api";
import { supabase } from "@/lib/supabase";

const replace = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

jest.mock("@/services/api", () => ({
  __esModule: true,
  default: { get: jest.fn(), put: jest.fn(), delete: jest.fn() },
}));

jest.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      updateUser: jest.fn().mockResolvedValue({ error: null }),
      signInWithPassword: jest.fn(),
      signOut: jest.fn().mockResolvedValue({}),
    },
  },
}));

jest.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({
    user: { id: "auth-eu", email: "lucas@exemplo.com", user_metadata: { nome: "Lucas" } },
    signOut: jest.fn(),
  }),
}));

// Um mock por teste decide se "eu" sou o master (criador_id === meu id) ou
// um membro comum — é essa distinção que muda o texto de confirmação
// exigido e o que a exclusão realmente apaga (ver services/conta.py).
function mockGrupo(criadorId) {
  api.get.mockImplementation((url) => {
    if (url === "/grupo") {
      return Promise.resolve({
        data: {
          id: 1,
          criador_id: criadorId,
          membros: [{ id: 99, auth_user_id: "auth-eu", nome: "Lucas" }],
        },
      });
    }
    return Promise.resolve({ data: {} });
  });
}

beforeEach(() => {
  jest.clearAllMocks();
});

test("master precisa digitar EXCLUIR TUDO — EXCLUIR sozinho não libera o botão", async () => {
  mockGrupo(99); // criador_id === id do "eu" mockado acima
  const user = userEvent.setup();
  render(<ContaPage />);

  await waitFor(() => expect(screen.getByText(/grupo inteiro/i)).toBeInTheDocument());

  await user.type(screen.getByLabelText(/confirme sua senha/i), "minhasenha");
  await user.click(screen.getByLabelText(/entendo que essa ação é irreversível/i));
  await user.type(screen.getByLabelText(/digite exclu/i), "EXCLUIR");

  expect(screen.getByRole("button", { name: /excluir minha conta/i })).toBeDisabled();
});

test("membro comum só precisa digitar EXCLUIR, e o aviso não menciona o grupo inteiro", async () => {
  mockGrupo(1); // criador_id !== id do "eu" (99) -> não é master
  const user = userEvent.setup();
  render(<ContaPage />);

  await waitFor(() => expect(screen.getByText(/permanecem para os demais membros/i)).toBeInTheDocument());
  expect(screen.queryByText(/grupo inteiro/i)).not.toBeInTheDocument();

  await user.type(screen.getByLabelText(/confirme sua senha/i), "minhasenha");
  await user.click(screen.getByLabelText(/entendo que essa ação é irreversível/i));
  await user.type(screen.getByLabelText(/digite exclu/i), "EXCLUIR");

  expect(screen.getByRole("button", { name: /excluir minha conta/i })).toBeEnabled();
});

test("senha errada bloqueia a exclusão — DELETE /api/conta nunca é chamado", async () => {
  mockGrupo(99);
  supabase.auth.signInWithPassword.mockResolvedValue({ error: { message: "Invalid login credentials" } });
  const user = userEvent.setup();
  render(<ContaPage />);

  await waitFor(() => expect(screen.getByText(/grupo inteiro/i)).toBeInTheDocument());
  await user.type(screen.getByLabelText(/confirme sua senha/i), "senhaerrada");
  await user.click(screen.getByLabelText(/entendo que essa ação é irreversível/i));
  await user.type(screen.getByLabelText(/digite exclu/i), "EXCLUIR TUDO");
  await user.click(screen.getByRole("button", { name: /excluir minha conta/i }));

  expect(await screen.findByText(/senha incorreta/i)).toBeInTheDocument();
  expect(api.delete).not.toHaveBeenCalled();
});

test("senha certa + confirmação completa: reautentica antes de excluir e depois redireciona pro login", async () => {
  mockGrupo(99);
  supabase.auth.signInWithPassword.mockResolvedValue({ error: null });
  api.delete.mockResolvedValue({ data: { excluida: true, grupo_apagado: true } });
  const user = userEvent.setup();
  render(<ContaPage />);

  await waitFor(() => expect(screen.getByText(/grupo inteiro/i)).toBeInTheDocument());
  await user.type(screen.getByLabelText(/confirme sua senha/i), "senhacerta");
  await user.click(screen.getByLabelText(/entendo que essa ação é irreversível/i));
  await user.type(screen.getByLabelText(/digite exclu/i), "EXCLUIR TUDO");
  await user.click(screen.getByRole("button", { name: /excluir minha conta/i }));

  await waitFor(() =>
    expect(supabase.auth.signInWithPassword).toHaveBeenCalledWith({
      email: "lucas@exemplo.com",
      password: "senhacerta",
    })
  );
  // Fase D1 do AUDITORIA_E_PLANO_CADASTRO.md — senha vai no body do DELETE
  // pra validação server-side também (não só