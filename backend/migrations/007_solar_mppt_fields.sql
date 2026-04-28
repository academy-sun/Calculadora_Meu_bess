-- backend/migrations/007_solar_mppt_fields.sql
-- MPPT fields for hybrid inverters (products_bess)
ALTER TABLE products_bess
  ADD COLUMN IF NOT EXISTS mppt_v_min      FLOAT,
  ADD COLUMN IF NOT EXISTS mppt_v_max      FLOAT,
  ADD COLUMN IF NOT EXISTS mppt_i_max_a    FLOAT,
  ADD COLUMN IF NOT EXISTS mppt_qty        INTEGER;

-- Electrical specs for FV modules (products_solar)
ALTER TABLE products_solar
  ADD COLUMN IF NOT EXISTS voc_v   FLOAT,
  ADD COLUMN IF NOT EXISTS vmp_v   FLOAT,
  ADD COLUMN IF NOT EXISTS isc_a   FLOAT,
  ADD COLUMN IF NOT EXISTS imp_a   FLOAT;
