-- backend/migrations/004_products_bess_eps_comercial.sql
-- Adds P_máx EPS field to inverters; seeds the commercial BESS unit for Arbitragem

-- Expand tipo CHECK constraint to accept bess_comercial
ALTER TABLE products_bess DROP CONSTRAINT IF EXISTS products_bess_tipo_check;
ALTER TABLE products_bess ADD CONSTRAINT products_bess_tipo_check
  CHECK (tipo IN ('bateria', 'inversor_hibrido', 'bess_comercial'));

ALTER TABLE products_bess
  ADD COLUMN IF NOT EXISTS pot_ca_max_eps_kva FLOAT;

COMMENT ON COLUMN products_bess.pot_ca_max_eps_kva IS
  'Potência CA máxima em modo EPS (kVA) — usado na seleção de inversor para Backup';

-- Seed commercial BESS unit used in Arbitragem engine
-- Update price/capacity here when product specs change
INSERT INTO products_bess (
  marca, modelo, sku, tipo,
  capacidade_kwh, dod_percent, preco, disponivel
) VALUES (
  'Intelbras', 'BESS Comercial 215kWh', 'BESS-215-COM', 'bess_comercial',
  215, 90, 550000, true
)
ON CONFLICT (sku) DO UPDATE SET
  capacidade_kwh = EXCLUDED.capacidade_kwh,
  dod_percent    = EXCLUDED.dod_percent,
  preco          = EXCLUDED.preco;

-- Update existing Intelbras inverters with P_máx EPS values
-- Values from "Dados dos Inversores" sheet in CALCULADORA BACKUP.xlsx
-- Adjust SKUs below if they differ in your catalog
UPDATE products_bess SET pot_ca_max_eps_kva = 6  WHERE sku = 'SIW200H-M050-W00';
UPDATE products_bess SET pot_ca_max_eps_kva = 10 WHERE sku = 'SIW200H-M075-W00';
UPDATE products_bess SET pot_ca_max_eps_kva = 12 WHERE sku = 'SIW200H-M105-W00';
UPDATE products_bess SET pot_ca_max_eps_kva = 18 WHERE sku = 'SIW400H-T015-W00';
UPDATE products_bess SET pot_ca_max_eps_kva = 36 WHERE sku = 'SIW400H-T030-W00';
