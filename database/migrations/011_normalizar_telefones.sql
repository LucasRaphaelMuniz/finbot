-- 011: normaliza telefones salvos crus pela web (Fase A4 do
-- AUDITORIA_E_PLANO_CADASTRO.md, corrige F1).
--
-- Antes da Fase A, `services/onboarding.py` e `services/grupos.py` salvavam
-- `usuarios.telefone` exatamente como a pessoa digitava no formulário web
-- (ex: '44912345678'), enquanto o bot sempre salva no formato JID
-- ('5544912345678@s.whatsapp.net'). Isso inclui a própria conta do Lucas,
-- criada pelo web antes desta correção existir.
--
-- Esta migração converte pro mesmo formato canônico que utils/telefone.py
-- usa (mesma lógica, reimplementada em PL/pgSQL porque migração roda direto
-- no Postgres, sem Python no meio). Se duas linhas normalizariam pro MESMO
-- JID (ex: usuário duplicado pelo próprio F1 — a pessoa já existia via bot
-- E criou conta nova pela web), a migração NÃO faz merge automático —
-- só avisa via RAISE NOTICE e deixa a linha como está, pra decisão manual
-- (risco listado no plano: merge automático de histórico é arriscado
-- demais pra fazer sem supervisão).
--
-- Placeholders internos ('web:...', 'excluido:...', usados por
-- services/convites.py e services/conta.py) são preservados como estão —
-- não são telefone de verdade, não fazem sentido normalizar.

DO $$
DECLARE
    r RECORD;
    raw_digits TEXT;
    local_part TEXT;
    novo_jid TEXT;
    ja_existe INT;
BEGIN
    FOR r IN
        SELECT id, telefone FROM usuarios
        WHERE telefone IS NOT NULL
          AND telefone NOT LIKE '%@%'          -- já não é JID
          AND telefone NOT LIKE 'web:%'        -- placeholder de convite web-only
          AND telefone NOT LIKE 'excluido:%'   -- placeholder de conta excluída
    LOOP
        raw_digits := regexp_replace(r.telefone, '\D', '', 'g');

        IF raw_digits = '' THEN
            RAISE NOTICE 'usuarios.id=% telefone=% -> vazio após limpeza, não normalizado (revisar manualmente)', r.id, r.telefone;
            CONTINUE;
        END IF;

        IF length(raw_digits) IN (10, 11) THEN
            raw_digits := '55' || raw_digits;
        END IF;

        IF length(raw_digits) = 12 AND left(raw_digits, 2) = '55' THEN
            local_part := substring(raw_digits FROM 5);
            IF left(local_part, 1) = '9' THEN
                raw_digits := left(raw_digits, 4) || '9' || local_part;
            END IF;
        END IF;

        IF length(raw_digits) NOT IN (12, 13) THEN
            RAISE NOTICE 'usuarios.id=% telefone=% -> formato não reconhecido (%), não normalizado (revisar manualmente)', r.id, r.telefone, raw_digits;
            CONTINUE;
        END IF;

        novo_jid := raw_digits || '@s.whatsapp.net';

        SELECT COUNT(*) INTO ja_existe FROM usuarios WHERE telefone = novo_jid AND id != r.id;
        IF ja_existe > 0 THEN
            RAISE NOTICE 'usuarios.id=% telefone=% normalizaria para % que JÁ EXISTE em outro usuário — provável duplicata do bug F1, NÃO mesclado automaticamente. Resolver manualmente.', r.id, r.telefone, novo_jid;
            CONTINUE;
        END IF;

        UPDATE usuarios SET telefone = novo_jid WHERE id = r.id;
        RAISE NOTICE 'usuarios.id=% telefone % -> %', r.id, r.telefone, novo_jid;
    END LOOP;
END $$;
