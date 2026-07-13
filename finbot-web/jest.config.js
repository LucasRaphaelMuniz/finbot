// jest.config.js — Fase 7 do PLANO_EXECUCAO.md ("Jest/RTL no Next.js para
// rotas críticas"). Usa next/jest: ele já resolve SWC (mesmo compilador do
// `next build`, sem precisar configurar Babel à parte) e faz mock automático
// de CSS/imagens — só falta apontar a raiz do projeto.
const nextJest = require("next/jest");

const createJestConfig = nextJest({ dir: "./" });

const customJestConfig = {
  setupFilesAfterEnv: ["<rootDir>/jest.setup.js"],
  testEnvironment: "jest-environment-jsdom",
  // next/jest NÃO lê o "paths" do jsconfig.json sozinho — isso resolve o
  // alias @/* em tempo de build (webpack/SWC), não em tempo de teste (Jest
  // usa o próprio resolver). Se