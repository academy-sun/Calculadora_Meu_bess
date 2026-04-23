-- backend/migrations/006_seed_catalog_products.sql
-- Inserts WEG BESS batteries and hybrid inverters from
-- "Dados de Equipamentos.xlsx" (marca = WEG, preços reais)
--
-- "Energia Utilizável" do catálogo é armazenada diretamente como capacidade_kwh
-- com dod_percent = 100 (energia já usável, sem desconto de DoD adicional).
-- O motor de seleção de kits usa: usable = capacidade_kwh × dod_percent/100

-- ── Baterias ─────────────────────────────────────────────────────────────────
INSERT INTO products_bess
  (marca, modelo, sku, tipo, capacidade_kwh, dod_percent,
   tensao_nominal_v, corrente_max_descarga_a, preco, disponivel)
VALUES
  ('WEG', 'SBW CB050 W00', 'SBW-CB050-W00', 'bateria',  5.02, 100, 192, 27,  6532.72, true),
  ('WEG', 'SBW CB100 W00', 'SBW-CB100-W00', 'bateria', 10.07, 100, 384, 27, 12799.27, true)
ON CONFLICT (sku) DO UPDATE SET
  marca                   = EXCLUDED.marca,
  capacidade_kwh          = EXCLUDED.capacidade_kwh,
  dod_percent             = EXCLUDED.dod_percent,
  tensao_nominal_v        = EXCLUDED.tensao_nominal_v,
  corrente_max_descarga_a = EXCLUDED.corrente_max_descarga_a,
  preco                   = EXCLUDED.preco,
  disponivel              = EXCLUDED.disponivel;

-- ── Inversores Híbridos ───────────────────────────────────────────────────────
-- pot_ca_max_eps_kva = coluna "POT. CA MÁX (EPS)" do catálogo
-- potencia_continua_kw = coluna PNOM
INSERT INTO products_bess
  (marca, modelo, sku, tipo, fase, potencia_continua_kw,
   pot_ca_max_eps_kva, preco, disponivel)
VALUES
  ('WEG', 'SIW200H M050 W00', 'SIW200H-M050-W00', 'inversor_hibrido', 'monofasico',  5.0,  6, 7547.40,  true),
  ('WEG', 'SIW200H M075 W00', 'SIW200H-M075-W00', 'inversor_hibrido', 'monofasico',  7.5, 10, 8967.40,  true),
  ('WEG', 'SIW200H M105 W00', 'SIW200H-M105-W00', 'inversor_hibrido', 'monofasico', 10.5, 12, 11436.13, true),
  ('WEG', 'SIW400H T015 W00', 'SIW400H-T015-W00', 'inversor_hibrido', 'trifasico',  15.0, 18, 20057.52, true),
  ('WEG', 'SIW400H T030 W00', 'SIW400H-T030-W00', 'inversor_hibrido', 'trifasico',  30.0, 36, 16050.59, true)
ON CONFLICT (sku) DO UPDATE SET
  marca                = EXCLUDED.marca,
  fase                 = EXCLUDED.fase,
  potencia_continua_kw = EXCLUDED.potencia_continua_kw,
  pot_ca_max_eps_kva   = EXCLUDED.pot_ca_max_eps_kva,
  preco                = EXCLUDED.preco,
  disponivel           = EXCLUDED.disponivel;
