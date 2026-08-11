-- 015_modulo_longi_635_specs_eletricas.sql
--
-- Preenche Voc, Imp e Isc do único módulo FV que o catálogo curado deixa ativo:
-- "W - 635WP - LONGI MONOFACIAL 30mm" (id 29740487).
--
-- POR QUE ISTO BLOQUEIA TUDO
--   _attrs_modulo() (backend/app/engines/pv_kit.py) exige voc_max_voltage e
--   max_power_current. Sem eles select_module() devolve (None, 0) e NENHUM kit
--   fotovoltaico é montado — nem on-grid puro, nem a parte FV do combinado.
--   Foi o que aconteceu quando a migration 014 deixou só este módulo ativo:
--   os 3 cenários on-grid voltaram vazios em produção.
--
-- FONTE
--   Datasheet LONGi Horizon LR7-72HVH 620~655M (BGV03, 20250324), coluna
--   LR7-72HVH-635M, condição STC:
--     Pmax 635 W | Voc 53,60 V | Isc 15,05 A | Vmp 44,26 V | Imp 14,35 A
--   Confere com o título do produto: dimensões 2382×1134×30mm, vidro único
--   (monofacial), 30 mm de espessura.
--
--   Os valores foram lidos de imagem do datasheet: a extração de texto do PDF
--   devolve os dígitos corrompidos (a fonte não traz mapa Unicode para
--   numerais). Registrado aqui porque o próximo que abrir o PDF vai bater na
--   mesma parede.
--
-- ATENÇÃO PARA DEPOIS
--   O produto "W - 635 Wp - LONGI - Módulo N-Type" (id 19993196, hoje
--   desativado pela curadoria) já tinha exatamente estes mesmos três valores em
--   overrides_tecnicos. Ou é o mesmo módulo cadastrado duas vezes, ou as specs
--   do N-Type foram preenchidas com o datasheet errado. Sem efeito hoje porque
--   ele está fora do motor — mas confira antes de reativá-lo.
--
-- ─────────────────────────────────────────────────────────────────────────────
-- PRÉ-CHECAGEM
-- ─────────────────────────────────────────────────────────────────────────────
-- select meubess_id, title, power, voc_max_voltage, max_power_current,
--        short_circuit_current_module, overrides_tecnicos
--   from meubess_products where meubess_id = '29740487';
--   -- esperado: power 0.635, os três elétricos nulos, overrides nulo

begin;

update meubess_products
   set overrides_tecnicos = coalesce(overrides_tecnicos, '{}'::jsonb)
                            || jsonb_build_object(
                                 'voc_max_voltage',              53.60,
                                 'max_power_current',            14.35,
                                 'short_circuit_current_module', 15.05,
                                 'fonte_specs',
                                 'Datasheet LONGi Horizon LR7-72HVH-635M (BGV03 20250324), STC'
                               ),
       needs_review = false,
       validado_por = 'migration/015-modulo-longi-635',
       validado_em  = now()
 where meubess_id = '29740487';

-- ─────────────────────────────────────────────────────────────────────────────
-- PÓS-CHECAGEM (dentro da transação; se divergir, `rollback`)
-- ─────────────────────────────────────────────────────────────────────────────

-- Deve retornar 1 linha com os três valores.
select 'GRAVADO' as check, meubess_id, title,
       overrides_tecnicos->>'voc_max_voltage'              as voc,
       overrides_tecnicos->>'max_power_current'            as imp,
       overrides_tecnicos->>'short_circuit_current_module' as isc
  from meubess_products
 where validado_por = 'migration/015-modulo-longi-635';

-- Deve ser exatamente 1: o motor precisa de pelo menos um módulo com dados
-- completos, senão o caminho FV inteiro fica sem saída.
select 'MODULOS ATIVOS COM SPEC COMPLETA' as check, count(*) as n
  from meubess_products
 where coalesce(ativo_manual, active)
   and coalesce(tipo_manual, tipo_auto) = 'modulo_fv'
   and coalesce((overrides_tecnicos->>'voc_max_voltage')::numeric, voc_max_voltage) is not null
   and coalesce((overrides_tecnicos->>'max_power_current')::numeric, max_power_current) is not null;

commit;

-- ─────────────────────────────────────────────────────────────────────────────
-- ROLLBACK
-- ─────────────────────────────────────────────────────────────────────────────
-- update meubess_products
--    set overrides_tecnicos = overrides_tecnicos
--                             - 'voc_max_voltage' - 'max_power_current'
--                             - 'short_circuit_current_module' - 'fonte_specs',
--        validado_por = null, validado_em = null
--  where meubess_id = '29740487';
