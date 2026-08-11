-- 013_linha_k_potencia_por_configuracao.sql
--
-- A linha K do SIW400H tem DUAS potências, não uma. É o mesmo equipamento
-- reconfigurável, e o título do produto carrega os dois modelos:
--
--   "SIW400H K008 T015"  →  8,6 kW ligado em 220/127  |  15 kW em 380/220
--   "SIW400H K017 T030"  → 17,3 kW ligado em 220/127  |  30 kW em 380/220
--
-- Os valores de 380 V são os do T015 e do T030 já cadastrados como produtos
-- próprios (15 kW / 18 kVA de pico e 30 kW / 36 kVA), que é o que o sufixo do
-- título indica. Confirmado pelo engenheiro na revisão da matriz de
-- compatibilidade ("se atentar com a linha k pois nesse cenário a potência
-- dele seria a menor" / "nesse cenário seria a potência maior").
--
-- Sem isso o motor usava só a potência menor em qualquer rede: subdimensionava
-- a linha K em rede 380 V e escalava para dois inversores sem necessidade.
--
-- Lido por _potencias_da_configuracao() em backend/app/engines/kit_builder.py,
-- chaveado pela tensão ENTRE FASES da rede. Modelos de configuração única não
-- têm essa chave e seguem lendo max_eps_power / peak_power_kw normalmente.
--
-- tipo_manual/overrides_tecnicos estão em _PRESERVE_ON_CONFLICT
-- (backend/app/catalog/sync.py) — o próximo sync não sobrescreve.
-- A plataforma MeuBESS é READ-ONLY: nada aqui toca nela.
--
-- ─────────────────────────────────────────────────────────────────────────────
-- PRÉ-CHECAGEM (deve retornar exatamente 2 linhas, K008 e K017)
-- ─────────────────────────────────────────────────────────────────────────────
-- select meubess_id, title,
--        overrides_tecnicos->>'max_eps_power'  as nominal_hoje,
--        overrides_tecnicos->>'peak_power_kw'  as pico_hoje,
--        overrides_tecnicos->'potencia_por_configuracao' as ja_tem
--   from meubess_products
--  where title ilike '%SIW400H K0%';

begin;

update meubess_products
   set overrides_tecnicos = coalesce(overrides_tecnicos, '{}'::jsonb)
                            || jsonb_build_object(
                                 'potencia_por_configuracao',
                                 jsonb_build_object(
                                   '220', jsonb_build_object(
                                            'max_eps_power', 8.6,
                                            'peak_power_kw', 9.5),
                                   '380', jsonb_build_object(
                                            'max_eps_power', 15.0,
                                            'peak_power_kw', 18.0)
                                 )
                               ),
       validado_por = 'migration/013-linha-k-potencia-por-config',
       validado_em  = now()
 where title ilike '%SIW400H K008%';

update meubess_products
   set overrides_tecnicos = coalesce(overrides_tecnicos, '{}'::jsonb)
                            || jsonb_build_object(
                                 'potencia_por_configuracao',
                                 jsonb_build_object(
                                   '220', jsonb_build_object(
                                            'max_eps_power', 17.3,
                                            'peak_power_kw', 19.0),
                                   '380', jsonb_build_object(
                                            'max_eps_power', 30.0,
                                            'peak_power_kw', 36.0)
                                 )
                               ),
       validado_por = 'migration/013-linha-k-potencia-por-config',
       validado_em  = now()
 where title ilike '%SIW400H K017%';

-- ─────────────────────────────────────────────────────────────────────────────
-- PÓS-CHECAGEM (dentro da transação; se divergir, `rollback`)
-- ─────────────────────────────────────────────────────────────────────────────

-- Deve retornar 2 linhas, cada uma com as duas configurações preenchidas.
select 'GRAVADO' as check, title,
       overrides_tecnicos->'potencia_por_configuracao'->'220' as em_220_127,
       overrides_tecnicos->'potencia_por_configuracao'->'380' as em_380_220
  from meubess_products
 where validado_por = 'migration/013-linha-k-potencia-por-config'
 order by title;

-- A potência da configuração 220 tem de bater com o que já estava no cadastro:
-- esta migration ACRESCENTA a configuração de 380, não altera a de 220.
select 'DIVERGENCIA 220 — deveria ser vazio' as check, title,
       overrides_tecnicos->>'max_eps_power' as antes,
       overrides_tecnicos->'potencia_por_configuracao'->'220'->>'max_eps_power' as agora
  from meubess_products
 where validado_por = 'migration/013-linha-k-potencia-por-config'
   and overrides_tecnicos->>'max_eps_power'
       is distinct from overrides_tecnicos->'potencia_por_configuracao'->'220'->>'max_eps_power';

commit;

-- ─────────────────────────────────────────────────────────────────────────────
-- ROLLBACK
-- ─────────────────────────────────────────────────────────────────────────────
-- update meubess_products
--    set overrides_tecnicos = overrides_tecnicos - 'potencia_por_configuracao',
--        validado_por = null, validado_em = null
--  where validado_por = 'migration/013-linha-k-potencia-por-config';
