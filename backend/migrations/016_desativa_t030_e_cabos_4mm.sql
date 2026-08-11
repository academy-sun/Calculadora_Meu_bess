-- 016_desativa_t030_e_cabos_4mm.sql
--
-- Duas decisões comerciais, ambas via ativo_manual (preservado no sync).
--
-- 1. SIW400H T030 W10
--    Indisponível na plataforma MeuBESS. Ele já tinha SAÍDO da listagem do
--    sync — estava com o preço de 17/06, 55 dias congelado, e continuava
--    cotável. Marcar ativo_manual = false torna a exclusão explícita em vez
--    de depender do produto não voltar à listagem.
--
-- 2. Cabos solares de 4 mm²
--    A cotação deve usar só o de 6 mm². Isto MUDA o preço de todo kit FV:
--    _cabo_mc4_items() (backend/app/engines/pv_kit.py) escolhe o cabo mais
--    barato entre os candidatos, e hoje o mais barato é justamente o 4 mm² da
--    WEG a R$ 3,71/m. Com ele fora, assume o "A - CABO SOLAR 6MM 1,8KV" a
--    R$ 5,00/m — R$ 1,29/m a mais, em 2 lances (positivo e negativo).
--
-- FICA REGISTRADO, sem alterar agora
--   O filtro de cabo é por substring: `"cabo" in title` em list_pv_products.
--   Ele também aceita "W - CABO 50MM PT - 12/20KV" (média tensão, R$ 179,55) e
--   "W - CABO ALIMENTACAO 10m BATERIA EP5/EP10" (R$ 1.270,63), que não são
--   cabo de string FV. Nenhum dos dois é escolhido hoje porque a regra pega o
--   mais barato — ou seja, a proteção é o preço, não a classificação. Mesmo
--   padrão dos CFW500 e dos gabinetes BSCW.
--
-- ─────────────────────────────────────────────────────────────────────────────
-- PRÉ-CHECAGEM
-- ─────────────────────────────────────────────────────────────────────────────
-- select meubess_id, title, price from meubess_products
--  where coalesce(ativo_manual, active)
--    and (title ilike '%cabo%4mm%' or title ilike '%cabo%4 mm%'
--         or title ilike '%SIW400H T030%')
--  order by title;

begin;

update meubess_products
   set ativo_manual = false,
       validado_por = 'migration/016-t030-e-cabos-4mm',
       validado_em  = now()
 where title ilike '%SIW400H T030%';

-- Só cabo SOLAR/CC de 4 mm². Não pega o "Cabo MP Flex HEPR/NH 3x4mm²", que é
-- cabo de força tripolar do lado CA — outra discussão, não esta.
update meubess_products
   set ativo_manual = false,
       validado_por = 'migration/016-t030-e-cabos-4mm',
       validado_em  = now()
 where (title ilike '%cabo solar%4mm%' or title ilike '%cabo solar%4 mm%'
        or title ilike '%cabo cc%4mm%'  or title ilike '%cabo cc%4 mm%');

-- ─────────────────────────────────────────────────────────────────────────────
-- PÓS-CHECAGEM (dentro da transação; se divergir, `rollback`)
-- ─────────────────────────────────────────────────────────────────────────────

select 'DESATIVADOS AGORA' as check, meubess_id, title, price
  from meubess_products
 where validado_por = 'migration/016-t030-e-cabos-4mm'
 order by title;

-- Deve ser vazio: nenhum cabo de 4 mm² sobrando entre os candidatos.
select 'RESIDUAL cabo 4mm' as check, meubess_id, title
  from meubess_products
 where coalesce(ativo_manual, active)
   and coalesce(tipo_manual, tipo_auto) = 'acessorio'
   and title ilike '%cabo%'
   and (title ilike '%4mm%' or title ilike '%4 mm%')
   and title not ilike '%3x4%';

-- O cabo que o motor passa a escolher: o mais barato entre os que sobraram.
select 'CABO QUE SERA COTADO' as check, meubess_id, title, price
  from meubess_products
 where coalesce(ativo_manual, active)
   and coalesce(tipo_manual, tipo_auto) = 'acessorio'
   and title ilike '%cabo%'
   and price > 0
 order by price
 limit 3;

commit;

-- ─────────────────────────────────────────────────────────────────────────────
-- ROLLBACK
-- ─────────────────────────────────────────────────────────────────────────────
-- update meubess_products
--    set ativo_manual = null, validado_por = null, validado_em = null
--  where validado_por = 'migration/016-t030-e-cabos-4mm';
