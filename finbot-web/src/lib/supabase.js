// lib/supabase.js — client Supabase, usado SÓ para autenticação (D6 do
// PLANO_EXECUCAO.md: dados financeiros nunca são lidos/escritos direto do
// browser via supabase-js; toda leitura/escrita de dados passa pela API
// Flask em services/api.js, que valida o JWT e aplica as regras de negócio
// — RLS no Supabase fica como 2ª camada de defesa, não a única).
import { createClient } from "@supabase/supabase-js";

export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
);
