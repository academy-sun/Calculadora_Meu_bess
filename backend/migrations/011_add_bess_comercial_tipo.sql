-- Permite marcar uma unidade BESS comercial (usada pela arbitragem) na réplica,
-- com origem='manual' e tipo_manual='bess_comercial'. A arbitragem usa
-- usable_capacity_kwh, dod_percent e preco dessa unidade.

ALTER TABLE meubess_products DROP CONSTRAINT IF EXISTS meubess_products_tipo_auto_check;
ALTER TABLE meubess_products ADD CONSTRAINT meubess_products_tipo_auto_check
    CHECK (tipo_auto IN ('bateria','inversor_hibrido','inversor_string',
                         'modulo_fv','acessorio','indefinido','bess_comercial'));

ALTER TABLE meubess_products DROP CONSTRAINT IF EXISTS meubess_products_tipo_manual_check;
ALTER TABLE meubess_products ADD CONSTRAINT meubess_products_tipo_manual_check
    CHECK (tipo_manual IN ('bateria','inversor_hibrido','inversor_string',
                          'modulo_fv','acessorio','indefinido','bess_comercial'));
