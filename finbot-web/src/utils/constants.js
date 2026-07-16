// utils/constants.js — chaves compartilhadas entre páginas/componentes que
// não têm uma relação direta de import (evita acoplar um componente a um
// arquivo de rota app/(auth)/.../page.jsx, que o Next trata de forma especial).
export const CONVITE_PENDENTE_KEY = "finbot_convite_pendente";

// Fase C do AUDITORIA_E_PLANO_CADASTRO.md: guarda se o cadastro que acabou
// de terminar veio de um merge com conta já existente do bot, ou foi criado
// do zero — usado só pra escolher qual variante do TourPrimeiroLogin
// mostrar (ver components/CompletarCadastro e components/TourPrimeiroLogin).
// sessionStorage (não localStorage): é um dado de "acabou de acontecer
// nesta sessão de cadastro", não precisa sobreviver a longo prazo — se
// sumir, o tour cai na variante "cadastro novo" por padrão, que é inofensivo.
export const VEIO_DO_BOT_KEY = "finbot_veio_do_bot";
