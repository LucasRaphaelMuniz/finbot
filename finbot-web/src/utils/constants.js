// utils/constants.js — chaves compartilhadas entre páginas/componentes que
// não têm uma relação direta de import (evita acoplar um componente a um
// arquivo de rota app/(auth)/.../page.jsx, que o Next trata de forma especial).
export const CONVITE_PENDENTE_KEY = "finbot_convite_pendente";

// WhatsApp opcional informado no formulário de cadastro (page.jsx) —
// atravessa o hiato de confirmação de e-mail via localStorage, mesmo
// padrão de CONVITE_PENDENTE_KEY, porque o clique no link de confirmação
// recarrega a página do zero (perde qualquer state em memória). Só
// pré-preenche o passo de telefone em CompletarCadastro — o OTP continua
// obrigatório (F2 da auditoria: nenhum telefone é aceito sem verificação).
export const WHATSAPP_PENDENTE_KEY = "finbot_whatsapp_pendente";

// Fase C do AUDITORIA_E_PLANO_CADASTRO.md: guarda se o cadastro que acabou
// de terminar veio de um merge com conta já existente do bot, ou foi criado
// do zero — usado só pra escolher qual variante do TourPrimeiroLogin
// mostrar (ver components/CompletarCadastro e components/TourPrimeiroLogin).
// sessionStorage (não localStorage): é um dado de "acabou de acontecer
// nesta sessão de cadastro", não precisa sobreviver a longo prazo — se
// sumir, o tour cai na variante "cadastro novo" por padrão, que é inofensivo.
export const VEIO_DO_BOT_KEY = "finbot_veio_do_bot";
