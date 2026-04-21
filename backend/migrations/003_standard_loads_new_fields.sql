-- backend/migrations/003_standard_loads_new_fields.sql
-- Adds TDIA, FD, IP/IN to standard_loads for Backup engine
-- Note: 'fase' (monofasico/trifasico) already exists; no separate is_trifasico needed

ALTER TABLE standard_loads
  ADD COLUMN IF NOT EXISTS tdia_horas    FLOAT,
  ADD COLUMN IF NOT EXISTS fator_demanda FLOAT,
  ADD COLUMN IF NOT EXISTS ip_in         FLOAT;

COMMENT ON COLUMN standard_loads.tdia_horas    IS 'TDIA: horas de uso por dia (Backup engine)';
COMMENT ON COLUMN standard_loads.fator_demanda IS 'FD: fator de demanda';
COMMENT ON COLUMN standard_loads.ip_in         IS 'IP/IN: relação corrente de partida / nominal';
