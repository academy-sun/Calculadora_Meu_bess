-- Réplica fiel do catálogo MeuBESS (tabela única raw).
--
-- Substitui a ingestão destrutiva em products_bess / products_solar:
-- o sync passa a espelhar TODOS os campos relevantes do produto MeuBESS,
-- sem classificar/descartar. A classificação vira anotação não-destrutiva
-- (tipo_auto + needs_review), com override manual (tipo_manual / overrides_tecnicos).
--
-- Datas de compliance são geradas no Supabase (NÃO vêm da MeuBESS):
--   first_seen_at  → setada só no primeiro INSERT (data de entrada no banco)
--   last_synced_at → atualizada em todo sync

CREATE TABLE IF NOT EXISTS meubess_products (
    -- ── chave (id do produto na MeuBESS; alfanumérico, ex. 'WHS656200') ──────
    meubess_id          TEXT PRIMARY KEY,

    -- ── identidade / comercial ──────────────────────────────────────────────
    enterprise_id       TEXT,
    title               TEXT,
    original_title      TEXT,
    description         TEXT,
    sku                 TEXT,
    suplier_cod         TEXT,
    marca               TEXT,
    brand_id            TEXT,
    brand_title         TEXT,
    supplier_id         TEXT,
    supplier_title      TEXT,
    app                 TEXT,
    active              BOOLEAN,
    view                TEXT,
    section             TEXT,
    type                TEXT,
    groups              TEXT,
    availability        TEXT,

    -- ── categoria ───────────────────────────────────────────────────────────
    category_id         TEXT,
    category_title      TEXT,
    category_section    TEXT,

    -- ── elétricos / técnicos ────────────────────────────────────────────────
    power                           NUMERIC,
    voltage                         TEXT,
    phase                           TEXT,
    breaker                         TEXT,
    battery_inputs                  INTEGER,
    max_eps_power                   NUMERIC,
    max_output_power                NUMERIC,
    qty_mppt                        INTEGER,
    qty_inputs_per_mppt             INTEGER,
    voc_max_voltage                 NUMERIC,
    mppt_min_voltage                NUMERIC,
    output_voltage                  NUMERIC,
    string_current                  NUMERIC,
    short_circuit_current_inverter  NUMERIC,
    short_circuit_current_module    NUMERIC,
    max_power_current               NUMERIC,

    -- ── preço / fiscal / dimensão ───────────────────────────────────────────
    price               NUMERIC,
    price_sale          NUMERIC,
    price_sale_until    TEXT,
    ncm                 TEXT,
    unt_measure         TEXT,
    unt_multiples       TEXT,
    weight              NUMERIC,
    width               NUMERIC,
    height              NUMERIC,
    length              NUMERIC,
    volumes             NUMERIC,
    fixing_type         TEXT,
    fixing_capacity     INTEGER,

    -- ── mídia ───────────────────────────────────────────────────────────────
    images              JSONB,

    -- ── classificação automática (anotação, não filtro) ────────────────────
    tipo_auto               TEXT CHECK (tipo_auto IN (
                                'bateria', 'inversor_hibrido', 'inversor_string',
                                'modulo_fv', 'indefinido')),
    classificacao_confianca TEXT CHECK (classificacao_confianca IN ('alta', 'media', 'baixa')),
    needs_review            BOOLEAN NOT NULL DEFAULT false,

    -- ── override manual (vence o automático; preservado no upsert) ──────────
    tipo_manual         TEXT CHECK (tipo_manual IN (
                            'bateria', 'inversor_hibrido', 'inversor_string',
                            'modulo_fv', 'indefinido')),
    overrides_tecnicos  JSONB,
    validado_por        TEXT,
    validado_em         TIMESTAMPTZ,

    -- ── origem (permite produtos manuais coexistirem) ───────────────────────
    origem              TEXT NOT NULL DEFAULT 'meubess' CHECK (origem IN ('meubess', 'manual')),

    -- ── compliance (geradas no Supabase) ────────────────────────────────────
    first_seen_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_synced_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_meubess_products_tipo_auto    ON meubess_products (tipo_auto);
CREATE INDEX IF NOT EXISTS idx_meubess_products_tipo_manual  ON meubess_products (tipo_manual);
CREATE INDEX IF NOT EXISTS idx_meubess_products_brand_title  ON meubess_products (brand_title);
CREATE INDEX IF NOT EXISTS idx_meubess_products_app          ON meubess_products (app);
CREATE INDEX IF NOT EXISTS idx_meubess_products_needs_review ON meubess_products (needs_review);
CREATE INDEX IF NOT EXISTS idx_meubess_products_active       ON meubess_products (active);
