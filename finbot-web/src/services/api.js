// services/api.js — instância única do axios usada por toda a aplicação
// (padrão CLAUDE.md: services/ concentra integração externa, componentes
// não chamam fetch/axios diretamente). Injeta o JWT da sessão Supabase em
// toda requisição e trata 401 centralizadamente (sessão expirada/inválida
// → redireciona pro login em vez de cada tela tratar isso na mão).
import axios from "axios";
import { supabase } from "@/lib/supabase";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
});

api.interceptors.request.use(async (config) => {
  const { data } = await supabase.auth.getSession();
  const token = data?.session?.access_token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401 && typeof window !== "undefined") {
      // Sessão inválida/expirada — derruba pro login. Não usa router.push
      // aqui de propósito: este arquivo não é um componente React, um
      // redirect "duro" garante que qualquer estado em memória da tela
      // anterior (ex: formulário aberto) é descartado junto.
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export default api;
