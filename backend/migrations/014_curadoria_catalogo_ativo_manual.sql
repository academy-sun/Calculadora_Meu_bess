-- 014_curadoria_catalogo_ativo_manual.sql
--
-- Restringe o catálogo do motor ao que a MX3 realmente vende, e cria a camada
-- que faz essa decisão sobreviver ao sync.
--
-- POR QUE UMA COLUNA NOVA
--   `active` vem da MeuBESS e é reescrito a cada sync (de hora em hora, a
--   partir desta entrega). Desativar produto ali seria desfeito sozinho.
--   `ativo_manual` é a decisão humana, entra em _PRESERVE_ON_CONFLICT
--   (backend/app/catalog/sync.py) e o motor lê
--   coalesce(ativo_manual, active) — mesmo padrão de tipo_manual/tipo_auto.
--   NULL = segue a plataforma. FALSE = fora do motor por decisão nossa.
--   Nada aqui toca a MeuBESS, que é READ-ONLY.
--
-- O QUE SAI (pedido do time comercial)
--   1. Linha WEG SIW300H          → são 3, não 2: o M060 está classificado
--                                    como inversor_string, não híbrido.
--   2. Bateria SBW300 Luna
--   3. Todo inversor que não é WEG → 197 produtos
--   4. Todo módulo FV exceto o WEG 635 Wp LONGI MONOFACIAL 30mm (id 29740487),
--      escolhido entre os DOIS Longi 635 W que existiam (o outro é o N-Type,
--      id 19993196, a R$ 708,82 contra R$ 600,00).
--
-- Também reclassifica o "INVERSOR ALL IN ONE UNIPOWER ... COM BATERIA", que
-- está como inversor_string sendo um all-in-one com bateria integrada. Era o
-- único produto de 127 V do catálogo e por isso aparecia sozinho na matriz de
-- compatibilidade para o padrão de entrada monofásico 127 V.
--
-- ─────────────────────────────────────────────────────────────────────────────
-- PRÉ-CHECAGEM
-- ─────────────────────────────────────────────────────────────────────────────
-- select count(*) filter (where title ilike '%SIW300H%')                    as siw300h,
--        count(*) filter (where title ilike '%SBW300%' and title ilike '%Luna%') as luna,
--        count(*) filter (where coalesce(tipo_manual,tipo_auto) like 'inversor%'
--                           and coalesce(marca,'') not ilike '%WEG%')       as inv_nao_weg,
--        count(*) filter (where coalesce(tipo_manual,tipo_auto) = 'modulo_fv') as modulos
--   from meubess_products where active;
--   -- esperado: 3 | 2 | 197 | 82

begin;

alter table meubess_products
  add column if not exists ativo_manual boolean;

comment on column meubess_products.ativo_manual is
  'Decisao humana sobre o produto entrar no motor. NULL segue o active da MeuBESS. FALSE mantem fora mesmo que a plataforma reative. Preservado no upsert do sync.';

-- 1. Linha SIW300H (inclui o M060, classificado como string)
update meubess_products
   set ativo_manual = false,
       validado_por = 'migration/014-curadoria-catalogo',
       validado_em  = now()
 where title ilike '%SIW300H%';

-- 2. Bateria Luna
update meubess_products
   set ativo_manual = false,
       validado_por = 'migration/014-curadoria-catalogo',
       validado_em  = now()
 where title ilike '%SBW300%' and title ilike '%Luna%';

-- 3. Inversores de outras marcas
update meubess_products
   set ativo_manual = false,
       validado_por = 'migration/014-curadoria-catalogo',
       validado_em  = now()
 where coalesce(tipo_manual, tipo_auto) like 'inversor%'
   and coalesce(marca, '') not ilike '%WEG%';

-- 4. Módulos FV, exceto o Longi Monofacial 30mm
update meubess_products
   set ativo_manual = false,
       validado_por = 'migration/014-curadoria-catalogo',
       validado_em  = now()
 where coalesce(tipo_manual, tipo_auto) = 'modulo_fv'
   and meubess_id <> '29740487';

-- Garante que o escolhido fica ativo mesmo que a plataforma o desative.
update meubess_products
   set ativo_manual = true,
       validado_por = 'migration/014-curadoria-catalogo',
       validado_em  = now()
 where meubess_id = '29740487';

-- 5. All-in-one com bateria classificado como inversor solar string
update meubess_products
   set tipo_manual   = 'indefinido',
       needs_review  = false,
       ativo_manual  = false,
       validado_por  = 'migration/014-curadoria-catalogo',
       validado_em   = now(),
       overrides_tecnicos = coalesce(overrides_tecnicos, '{}'::jsonb)
                            || jsonb_build_object(
                                 'motivo_reclassificacao',
                                 'All-in-one com bateria integrada, não inversor solar string. Ver migration 014.')
 where coalesce(tipo_manual, tipo_auto) = 'inversor_string'
   and title ilike '%ALL IN ONE%';

-- ─────────────────────────────────────────────────────────────────────────────
-- PÓS-CHECAGEM (dentro da transação; se divergir, `rollback`)
-- ─────────────────────────────────────────────────────────────────────────────

-- O que sobra ATIVO para o motor, por tipo.
select 'ATIVO POR TIPO' as check,
       coalesce(tipo_manual, tipo_auto) as tipo,
       count(*) as n,
       count(*) filter (where price is not null) as com_preco
  from meubess_products
 where coalesce(ativo_manual, active)
 group by 2 order by 3 desc;

-- Deve ser vazio: nenhum inversor não-WEG ativo.
select 'RESIDUAL inversor nao-WEG' as check, meubess_id, title, marca
  from meubess_products
 where coalesce(ativo_manual, active)
   and coalesce(tipo_manual, tipo_auto) like 'inversor%'
   and coalesce(marca, '') not ilike '%WEG%';

-- Deve retornar exatamente 1 linha: o módulo escolhido.
select 'MODULO ATIVO' as check, meubess_id, title, price
  from meubess_products
 where coalesce(ativo_manual, active)
   and coalesce(tipo_manual, tipo_auto) = 'modulo_fv';

commit;

-- ─────────────────────────────────────────────────────────────────────────────
-- ROLLBACK
-- ─────────────────────────────────────────────────────────────────────────────
-- update meubess_products
--    set ativo_manual = null, validado_por = null, validado_em = null
--  where validado_por = 'migration/014-curadoria-catalogo';
-- (a coluna e a reclassificação do all-in-one seguem; remover à parte se preciso)
