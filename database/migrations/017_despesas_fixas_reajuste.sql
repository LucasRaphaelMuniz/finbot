-- 017: reajuste de despesa fixa com vigência ("só a partir de quando")
--
-- Problema: o lançador copia despesas_fixas.valor pro gasto no momento do
-- lançamento (snapshot) — editar valor hoje já NÃO afeta gasto de mês
-- anterior, isso sempre funcionou de graça. A única ambiguidade real é
-- quando o dia_lancamento deste mês AINDA NÃO passou: editar valor agora
-- muda também o lançamento iminente deste mês, sem opção de dizer "só a
-- partir do mês que vem". valor_pendente resolve só esse caso — não é uma
-- tabela de histórico completa, é só 1 valor "na fila" esperando a
-- competência certa pra virar o valor efetivo.
ALTER TABLE despesas_fixas ADD COLUMN IF NOT EXISTS valor_pendente DECIMAL;
ALTER TABLE despesas_fixas ADD COLUMN IF NOT EXISTS valor_pendente_a_partir DATE;
