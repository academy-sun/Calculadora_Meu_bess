-- Atributos técnicos de dimensionamento de kit (contrato da skill
-- dimensionamento-kit-bess-hibrido) que NÃO vêm da API MeuBESS.
--
-- Colunas dedicadas (não JSONB): mais query-áveis e claras. O sync NÃO as
-- sobrescreve — ele só escreve os campos que mapeia da API (ver _map_to_raw em
-- app/catalog/sync.py) —, então valores preenchidos manualmente persistem entre
-- sincronizações. Todas nulas; preenchidas por modelo (datasheet) no cadastro.
--
-- A pendência ("faltam dados técnicos") é derivada por NULL nos campos
-- obrigatórios do tipo (inversor_hibrido / bateria), não por uma flag fixa.

ALTER TABLE meubess_products
  -- ── Inversor híbrido ─────────────────────────────────────────────────────
  ADD COLUMN IF NOT EXISTS peak_power_kw                NUMERIC,   -- potência de pico EPS
  ADD COLUMN IF NOT EXISTS peak_power_duration_s        INTEGER,   -- duração do pico (ex. 60)
  ADD COLUMN IF NOT EXISTS battery_input_max_current_a  NUMERIC,   -- corrente máx POR ENTRADA de bateria
  ADD COLUMN IF NOT EXISTS battery_voltage_min_v        NUMERIC,   -- faixa de tensão de bateria aceita
  ADD COLUMN IF NOT EXISTS battery_voltage_max_v        NUMERIC,
  ADD COLUMN IF NOT EXISTS eps_output_voltage           TEXT,      -- ex. "220", "127/220", "380/220", "380/220;220/127"
  ADD COLUMN IF NOT EXISTS split_phase                  BOOLEAN,   -- alimenta 127 e 220 mono simultâneo
  ADD COLUMN IF NOT EXISTS max_parallel_units           INTEGER,   -- nº máx de inversores em paralelo
  -- ── Bateria ──────────────────────────────────────────────────────────────
  ADD COLUMN IF NOT EXISTS usable_capacity_kwh          NUMERIC,
  ADD COLUMN IF NOT EXISTS nominal_capacity_kwh         NUMERIC,
  ADD COLUMN IF NOT EXISTS dod_percent                  NUMERIC,
  ADD COLUMN IF NOT EXISTS max_parallel_batteries       INTEGER,   -- máx em paralelo POR string (datasheet da bateria)
  ADD COLUMN IF NOT EXISTS max_continuous_current_a     NUMERIC,
  ADD COLUMN IF NOT EXISTS peak_discharge_current_a     NUMERIC,
  ADD COLUMN IF NOT EXISTS nominal_voltage_v            NUMERIC,
  ADD COLUMN IF NOT EXISTS operating_voltage_min_v      NUMERIC,
  ADD COLUMN IF NOT EXISTS operating_voltage_max_v      NUMERIC,
  ADD COLUMN IF NOT EXISTS chemistry                    TEXT,
  ADD COLUMN IF NOT EXISTS compatible_inverters         TEXT;      -- lista declarada no datasheet (autoritativa)
