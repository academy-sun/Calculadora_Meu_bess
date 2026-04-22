-- backend/migrations/006_seed_catalog_products.sql
-- Inserts Intelbras BESS batteries and hybrid inverters from
-- "Catalogo de inversores e baterias.xlsx"
--
-- IMPORTANT: Update the preco values below before going to production.
-- The values here are placeholders.
-- "Energia Utilizável" from the catalog is stored directly as capacidade_kwh
-- with dod_percent = 100 (usable energy already factored in).

-- ── Baterias ─────────────────────────────────────────────────────────────────
INSERT INTO products_bess (marca, modelo, sku, tipo, capacidade_kwh, dod_percent, tensao_nominal_v, corrente_max_descarga_a, preco, disponivel)
VALUES
  ('Intelbras', 'SBW CB050 W00', 'SBW-CB050-W00', 'bateria', 5.02,  100, 192, 27, 15000, true),
  ('Intelbras', 'SBW CB100 W00', 'SBW-CB100-W00', 'bateria', 10.07, 100, 384, 27, 28000, true)
ON CONFLICT (sku) DO UPDATE SET
  capacidade_kwh         = EXCLUDED.capacidade_kwh,
  dod_percent            = EXCLUDED.dod_percent,
  tensao_nominal_v       = EXCLUDED.tensao_nominal_v,
  corrente_max_descarga_a = EXCLUDED.corrente_max_descarga_a,
  preco                  = EXCLUDED.preco,
  disponivel             = EXCLUDED.disponivel;

-- ── Inversores Híbridos ───────────────────────────────────────────────────────
-- fase: 'monofasico' or 'trifasico'
-- pot_ca_max_eps_kva: potência CA máxima no modo EPS (off-grid backup)
-- potencia_continua_kw: potência nominal (PNOM da planilha)
INSERT INTO products_bess (marca, modelo, sku, tipo, fase, potencia_continua_kw, pot_ca_max_eps_kva, preco, disponivel)
VALUES
  ('Intelbras', 'SIW200H M050 W00', 'SIW200H-M050-W00', 'inversor_hibrido', 'monofasico',  5.0,  6,  12000, true),
  ('Intelbras', 'SIW200H M075 W00', 'SIW200H-M075-W00', 'inversor_hibrido', 'monofasico',  7.5,  10, 16000, true),
  ('Intelbras', 'SIW200H M105 W00', 'SIW200H-M105-W00', 'inversor_hibrido', 'monofasico', 10.5,  12, 20000, true),
  ('Intelbras', 'SIW400H T015 W00', 'SIW400H-T015-W00', 'inversor_hibrido', 'trifasico',  15.0,  18, 35000, true),
  ('Intelbras', 'SIW400H T030 W00', 'SIW400H-T030-W00', 'inversor_hibrido', 'trifasico',  30.0,  36, 50000, true)
ON CONFLICT (sku) DO UPDATE SET
  fase                 = EXCLUDED.fase,
  potencia_continua_kw = EXCLUDED.potencia_continua_kw,
  pot_ca_max_eps_kva   = EXCLUDED.pot_ca_max_eps_kva,
  preco                = EXCLUDED.preco,
  disponivel           = EXCLUDED.disponivel;
