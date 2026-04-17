ALTER TABLE products_bess
  ADD COLUMN IF NOT EXISTS max_baterias INTEGER;

COMMENT ON COLUMN products_bess.max_baterias
  IS 'Para inversores: quantidade máxima de baterias suportada por unidade de inversor (conforme datasheet do fabricante)';
