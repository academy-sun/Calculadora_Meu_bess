-- Users
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       TEXT UNIQUE NOT NULL,
    nome        TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('engineer', 'admin')),
    ativo       BOOLEAN NOT NULL DEFAULT true,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Catalog BESS
CREATE TABLE IF NOT EXISTS products_bess (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    marca                   TEXT NOT NULL,
    modelo                  TEXT NOT NULL,
    sku                     TEXT UNIQUE NOT NULL,
    tipo                    TEXT NOT NULL CHECK (tipo IN ('bateria', 'inversor_hibrido')),
    fase                    TEXT CHECK (fase IN ('monofasico', 'trifasico')),
    tensao_nominal_v        NUMERIC,
    tensao_min_dc_v         NUMERIC,
    tensao_max_dc_v         NUMERIC,
    corrente_max_carga_a    NUMERIC,
    corrente_max_descarga_a NUMERIC,
    corrente_max_dc_a       NUMERIC,
    capacidade_kwh          NUMERIC,
    dod_percent             NUMERIC,
    potencia_continua_kw    NUMERIC,
    preco                   NUMERIC NOT NULL,
    disponivel              BOOLEAN NOT NULL DEFAULT true,
    atualizado_em           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Catalog Solar
CREATE TABLE IF NOT EXISTS products_solar (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    marca               TEXT NOT NULL,
    modelo              TEXT NOT NULL,
    sku                 TEXT UNIQUE NOT NULL,
    tipo                TEXT NOT NULL CHECK (tipo IN ('modulo_fv', 'inversor_solar')),
    potencia_pico_wp    NUMERIC,
    eficiencia_pct      NUMERIC,
    potencia_nominal_kw NUMERIC,
    mppt_min_v          NUMERIC,
    mppt_max_v          NUMERIC,
    fase                TEXT CHECK (fase IN ('monofasico', 'trifasico')),
    preco               NUMERIC NOT NULL,
    disponivel          BOOLEAN NOT NULL DEFAULT true
);

-- Catalog Standard Loads
CREATE TABLE IF NOT EXISTS standard_loads (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome            TEXT NOT NULL,
    categoria       TEXT NOT NULL,
    potencia_w      NUMERIC NOT NULL,
    fator_potencia  NUMERIC NOT NULL DEFAULT 1.0,
    tensao          TEXT NOT NULL,
    fase            TEXT NOT NULL CHECK (fase IN ('monofasico', 'trifasico')),
    ativo           BOOLEAN NOT NULL DEFAULT true
);

-- Projects
CREATE TABLE IF NOT EXISTS projects (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tipo_calculo        TEXT NOT NULL,
    estado              TEXT NOT NULL DEFAULT 'calculando' CHECK (estado IN ('calculando', 'concluido', 'erro')),
    versao              INTEGER NOT NULL DEFAULT 1,
    parametros          JSONB,
    origem              TEXT NOT NULL CHECK (origem IN ('ploomes', 'interno')),
    negocio_id          TEXT,
    negocio_nome        TEXT,
    solicitante_id      TEXT NOT NULL,
    solicitante_nome    TEXT NOT NULL,
    solicitado_em       TIMESTAMPTZ NOT NULL,
    calculado_em        TIMESTAMPTZ,
    user_id             UUID REFERENCES users(id)
);

-- Load Curves
CREATE TABLE IF NOT EXISTS load_curves (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    origem      TEXT NOT NULL CHECK (origem IN ('upload', 'sintetica')),
    dados       JSONB NOT NULL,
    unidade     TEXT NOT NULL DEFAULT 'kW',
    resolucao   TEXT NOT NULL DEFAULT '1h'
);

-- Project Loads
CREATE TABLE IF NOT EXISTS project_loads (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    standard_load_id    UUID REFERENCES standard_loads(id),
    nome                TEXT NOT NULL,
    potencia_w          NUMERIC NOT NULL,
    quantidade          INTEGER NOT NULL DEFAULT 1,
    horas_uso_dia       NUMERIC NOT NULL
);

-- Calculation Results
CREATE TABLE IF NOT EXISTS calculation_results (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    engine      TEXT NOT NULL CHECK (engine IN ('bess', 'solar', 'compatibilizacao')),
    inputs      JSONB NOT NULL,
    outputs     JSONB NOT NULL,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);
