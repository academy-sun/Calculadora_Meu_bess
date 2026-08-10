-- 012_reclassify_cfw500_frequency_inverters.sql
--
-- Reclassifica a linha WEG CFW (inversores de FREQUÊNCIA, para acionamento de
-- motores) que estava anotada como 'inversor_string' (inversor solar).
--
-- Por que isso importa
--   Hoje nenhum CFW entra em cotação, mas a proteção é ACIDENTAL: vem da
--   ausência de dado, não da classificação. dc_capacity_modules()
--   (backend/app/engines/pv_kit.py:150-155) retorna 0 quando voc_max_voltage ou
--   qty_mppt são nulos, e os CFW estão sem esses campos. Se um sync ou um
--   preenchimento manual completar esses dois campos, um acionamento de motor
--   de ~R$ 1.700 passa a competir por PREÇO em _select_string_inverter_for()
--   (pv_kit.py:330) e pode vencer o inversor solar correto.
--
-- Por que 'indefinido'
--   'indefinido' é o único valor do vocabulário fechado de tipos que NENHUM
--   caminho do motor consome. Os consumidores de meubess_products são:
--     • list_pv_products()   → modulo_fv, inversor_string, acessorio
--     • list_kit_products()  → inversor_hibrido, bateria, acessorio
--     • get_bess_comercial() → bess_comercial
--   (backend/app/catalog/service.py:96-147, 307-316)
--   'acessorio' NÃO serve: é consumido e filtrado por substring de
--   título/categoria (cabo/mc4/conector/jbw/estrutura) — proteção frágil.
--   'indefinido' também já existe no frontend (TipoProduto em
--   frontend/src/types/index.ts:71-72, badge vermelho em ProductsPage.tsx),
--   então não exige mudança de código. Um valor novo como
--   'inversor_frequencia' renderizaria label undefined sem classe de cor.
--
-- tipo_manual é a camada de decisão humana: _PRESERVE_ON_CONFLICT em
-- backend/app/catalog/sync.py:276-282 garante que o próximo sync não sobrescreve.
-- A plataforma MeuBESS é READ-ONLY — nada aqui toca nela.
--
-- ─────────────────────────────────────────────────────────────────────────────
-- PRÉ-CHECAGEM (rodar antes; conferir que o total é 51)
-- ─────────────────────────────────────────────────────────────────────────────
-- select count(*) as total,
--        count(voc_max_voltage) as com_voc,
--        count(qty_mppt)        as com_mppt
--   from meubess_products
--  where coalesce(tipo_manual, tipo_auto) = 'inversor_string'
--    and title ilike '%CFW%';
--
-- select meubess_id, title, marca, price, tipo_auto, tipo_manual,
--        voc_max_voltage, qty_mppt
--   from meubess_products
--  where coalesce(tipo_manual, tipo_auto) = 'inversor_string'
--    and title ilike '%CFW%'
--  order by title;
--
-- Se `com_voc` ou `com_mppt` > 0, algum CFW JÁ está elegível hoje — pare e
-- rode a matriz de cenários ANTES de corrigir, para saber se ele venceu
-- alguma cotação da linha de base.

begin;

-- Idempotente: só toca linhas cujo tipo efetivo ainda é 'inversor_string'.
-- O filtro '%CFW%' cobre toda a família de inversores de frequência WEG
-- (CFW500, CFW300, CFW11, CFW700) — todos acionamento de motor, nenhum solar.
update meubess_products
   set tipo_manual   = 'indefinido',
       needs_review  = false,
       validado_por  = 'migration/012-cfw-frequency-inverters',
       validado_em   = now(),
       -- merge preserva overrides técnicos reais que já existam na linha
       overrides_tecnicos = coalesce(overrides_tecnicos, '{}'::jsonb)
                            || jsonb_build_object(
                                 'motivo_reclassificacao',
                                 'Inversor de frequência (acionamento de motor), não inversor solar string. Ver migration 012.'
                               )
 where coalesce(tipo_manual, tipo_auto) = 'inversor_string'
   and title ilike '%CFW%';

-- ─────────────────────────────────────────────────────────────────────────────
-- PÓS-CHECAGEM (dentro da transação; se algo divergir, `rollback`)
-- ─────────────────────────────────────────────────────────────────────────────

-- Deve retornar 0 linhas.
select 'RESIDUAL — deveria ser vazio' as check, meubess_id, title
  from meubess_products
 where coalesce(tipo_manual, tipo_auto) = 'inversor_string'
   and title ilike '%CFW%';

-- Deve retornar 51.
select 'RECLASSIFICADOS' as check, count(*) as total
  from meubess_products
 where tipo_manual = 'indefinido'
   and validado_por = 'migration/012-cfw-frequency-inverters';

commit;

-- ─────────────────────────────────────────────────────────────────────────────
-- ROLLBACK (se necessário depois do commit)
-- ─────────────────────────────────────────────────────────────────────────────
-- update meubess_products
--    set tipo_manual  = null,
--        validado_por = null,
--        validado_em  = null,
--        overrides_tecnicos = nullif(overrides_tecnicos - 'motivo_reclassificacao', '{}'::jsonb)
--  where validado_por = 'migration/012-cfw-frequency-inverters';
--
-- ─────────────────────────────────────────────────────────────────────────────
-- VERIFICAÇÃO DE COMPORTAMENTO (obrigatória, após o commit)
-- ─────────────────────────────────────────────────────────────────────────────
-- A matriz de cenários bate na API de PRODUÇÃO (não no banco direto), então
-- precisa só de API_KEY — não de DATABASE_URL:
--
--   cd backend && API_KEY=<railway> python scripts/cenarios.py --comparar
--
-- Nenhuma linha deve mudar. Se mudou, algum CFW estava sendo usado em cotação
-- e a linha de base em docs/cenarios-esperados.json estava contaminada.
