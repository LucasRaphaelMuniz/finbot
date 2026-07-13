-- 013: flag de tutorial de primeiro login web (Fase C do
-- AUDITORIA_E_PLANO_CADASTRO.md, corrige F5).
--
-- Coluna no banco, não localStorage: sobrevive a troca de dispositivo ou
-- navegador (a pessoa loga no celular depois de ter visto o tour no PC, ou
-- vice-versa) e permite reexibir por suporte se precisar. NULL = ainda não
-- viu; timestamp = quando viu/pulou (ver services/conta.py:marcar_tutorial_visto).

ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS tutorial_web_visto_em TIMESTAMP;
