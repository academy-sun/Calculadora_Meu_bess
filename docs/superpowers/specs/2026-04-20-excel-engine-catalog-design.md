# Design: Excel-Driven Calculation Engine + Catalog Management

**Date:** 2026-04-20  
**Status:** Approved  
**Scope:** Replace broken Python calculation engines with formula-accurate implementations derived from the engineer's Excel spreadsheets; add complete catalog management UI for cargas, baterias, and inversores.

---

## 1. Background & Problem

The current Python calculation engines for Backup and Arbitragem produce incorrect results. The engineers already have two working Excel spreadsheets (`CALCULADORA BACKUP.xlsx` and `CALCULADORA ARBITRAGEM.xlsx`) with the correct formulas. The goal is to make the web application produce results identical to those spreadsheets.

The spreadsheets use `XLOOKUP` for catalog lookups (pulling equipment specs from the "Dados de Cargas" sheet). This function is not supported by Python Excel execution libraries. Since the catalog data can live in the database, the `XLOOKUP` is replaced by DB queries; only the arithmetic formulas are ported to Python.

The Excel files are uploaded to Supabase Storage bucket `calc-templates` as the authoritative reference documents. They are not executed at runtime — they are consulted by humans when formulas change.

---

## 2. Architecture Overview

```
Web Form (React)
    │
    ├── Catalog selections  ──► Supabase DB (standard_loads, products_bess)
    ├── Manual inputs
    │
    ▼
FastAPI Backend
    ├── BackupEngine      → Python replication of Excel formulas (cell-exact)
    ├── ArbitrageEngine   → Python replication of Excel formulas (cell-exact)
    └── KitSelector       → finds cheapest compatible inverter + battery qty
    │
    ▼
CalculateResponse (existing structure, extended)
```

**Separation of concerns:**
- **Python engines** handle arithmetic (ROUNDUP, SUM, MAX, AVERAGE, CEIL, etc.)
- **DB** handles catalog lookup (replaces XLOOKUP)
- **KitSelector** handles catalog traversal to find the best kit
- **Supabase Storage** stores the `.xlsx` files as read-only reference

---

## 3. Data Model Changes

### 3.1 `standard_loads` — new columns

```sql
ALTER TABLE standard_loads
  ADD COLUMN tdia_horas       FLOAT,        -- TDIA: hours of use per day
  ADD COLUMN fator_demanda    FLOAT,        -- FD: demand factor
  ADD COLUMN ip_in            FLOAT,        -- IP/IN: starting current ratio
  ADD COLUMN is_trifasico     BOOLEAN DEFAULT FALSE;
```

Existing columns retained: `nome`, `potencia_w` (= PNOM), `fator_potencia` (= FP), `categoria`, `ativo`.

### 3.2 `products_bess` — new column for inverters

```sql
ALTER TABLE products_bess
  ADD COLUMN pot_ca_max_eps_kva FLOAT;  -- P_máx EPS: max AC power in EPS mode
```

This is the "POT. CA MÁX (EPS)" column from the inverter catalog in the spreadsheet. Used in kit selection for Backup: inverter qualifies if `pot_ca_max_eps_kva >= Σ Pp`.

### 3.3 BESS Comercial product

The Arbitragem engine uses a single fixed commercial BESS unit (215 kWh, R$ 550.000). This is stored as a `products_bess` entry with `tipo = 'bess_comercial'` — a new valid value alongside the existing `'bateria'` and `'inversor_hibrido'`. The backend fetches this entry by type at calculation time. Fields used:
- `capacidade_kwh = 215`
- `dod_percent = 90`
- `preco = 550000`

When the commercial BESS specs change, the engineer updates this catalog entry — no code change needed.

### 3.4 Supabase Storage

Bucket `calc-templates` (private, admin-only upload):
- `backup/CALCULADORA BACKUP.xlsx`
- `arbitragem/CALCULADORA ARBITRAGEM.xlsx`

Upload via admin UI page (no runtime dependency on these files).

### 3.5 Data migration

A one-time Python script reads `CALCULADORA BACKUP.xlsx` → aba "Dados de Cargas" and inserts all equipment rows into `standard_loads`. Columns mapped:

| Excel col | DB field         |
|-----------|-----------------|
| A: EQUIPAMENTO | `nome`      |
| B: IP/IN       | `ip_in`     |
| C: FP          | `fator_potencia` |
| D: POT(W)      | `potencia_w` |
| E: FD          | `fator_demanda` |
| F: Hora/d      | `tdia_horas` |
| G: 3F?         | `is_trifasico` |
| AG: CAT        | `categoria`  |

---

## 4. Calculation Engines

### 4.1 Backup Engine (`calculate_backup`)

Replaces current implementation in `backend/app/engines/bess.py`.

**Inputs:**
```python
@dataclass
class LoadRow:
    qtd: int
    pnom_w: float
    fp: float       # fator de potência
    fd: float       # fator de demanda
    ip_in: float    # relação corrente de partida
    tdia_h: float   # horas de uso por dia

@dataclass
class BackupInput:
    cargas: list[LoadRow]
    autonomia_h: float          # captured for record; TDIA per load already encodes duration
    dod_percent: float          # stored as 0–100 (e.g. 90); divided by 100 only in kit selection
    eficiencia_roundtrip: float # captured for record; not applied in E_EPS formula per Excel
    tipo_instalacao: Literal["monofasico", "trifasico"]
```

**Per-row formulas (exact Excel replication):**
```python
pn_kva   = math.ceil(row.qtd * (row.pnom_w / row.fp)) / 1000   # ROUNDUP(...,0)/1000
dmn_kva  = pn_kva * row.fd
pp_kva   = pn_kva * row.ip_in
dmp_kva  = dmn_kva * row.ip_in
e_eps_kwh = pn_kva * row.tdia_h
```

**Totals:**
```python
total_pn    = sum(row.pn_kva)
total_dmn   = sum(row.dmn_kva)
total_pp    = sum(row.pp_kva)
total_dmp   = sum(row.dmp_kva)
total_e_eps = sum(row.e_eps_kwh)
```

**Outputs returned to frontend:**
- Per-row: `pn_kva`, `dmn_kva`, `pp_kva`, `dmp_kva`, `e_eps_kwh`
- Totals: `total_pn`, `total_dmn`, `total_pp`, `total_dmp`, `total_e_eps`
- Kit recommendation (see Section 4.3)

### 4.2 Arbitragem Engine (`calculate_arbitrage`)

Replaces current implementation entirely.

**Inputs:**
```python
@dataclass
class ArbitrageInput:
    consumo_ponta_kwh: list[float]      # 12 monthly values (E4:E15)
    demanda_ponta_kw: list[float]       # 12 monthly values (F4:F15)
    tarifa_ponta_kwh: float             # I4
    tarifa_fora_ponta_kwh: float        # I3
    # BESS product specs (from catalog, tipo='bess_comercial'):
    bess_capacidade_kwh: float          # e.g. 215
    bess_dod: float                     # e.g. 0.90
    bess_preco: float                   # e.g. 550000
```

**Formulas (exact Excel replication):**
```python
avg_consumo_ponta = mean(consumo_ponta_kwh)                      # E16 = AVERAGE(E4:E15)
max_demanda_ponta = max(demanda_ponta_kw)                        # LARGE(F4:F15, 1)

fator = 22 * bess_capacidade_kwh * bess_dod * 0.9               # 22 × 215 × 0.9 × 0.9
qty_consumo  = math.ceil(avg_consumo_ponta / fator)              # ROUNDUP(E16/22/(cap×dod×0.9), 0)
qty_potencia = math.ceil(max_demanda_ponta / 100)                # ROUNDUP(LARGE/100, 0)
qty_bess     = max(qty_consumo, qty_potencia)                    # MAX(...)

diff_tarifa      = tarifa_ponta_kwh - tarifa_fora_ponta_kwh      # I5
economia_mensal  = avg_consumo_ponta * diff_tarifa               # I14 = E16 × I5
custo_total      = qty_bess * bess_preco                         # I13
payback_meses    = custo_total / economia_mensal                 # I15
```

**Outputs:**
- `qty_bess`, `qty_consumo`, `qty_potencia`
- `avg_consumo_ponta`, `max_demanda_ponta`
- `economia_mensal`, `custo_total`, `payback_meses`

### 4.3 Kit Selection — Backup

After `calculate_backup` returns `total_pp` and `total_e_eps`:

**Inverter selection:**
```
eligible = [inv for inv in inversores
            if inv.fase == tipo_instalacao
            and inv.pot_ca_max_eps_kva >= total_pp]
best_inverter = min(eligible, key=lambda i: i.preco)
```

**Battery quantity:**
```python
qtd_baterias = math.ceil(total_e_eps / (bat.capacidade_kwh * bat.dod_percent / 100))
```

Returns the cheapest valid inverter + calculated battery quantity + total price.

---

## 5. Frontend Forms

### 5.1 Backup Form (`NewProjectPage.tsx` — backup section)

**Fields:**
- Tipo de instalação: radio `Monofásico / Trifásico`
- Autonomia (h), DoD (%), Eficiência roundtrip (%) — numeric inputs with defaults (24h, 90%, 90%)
- Load table (dynamic rows):
  - Dropdown: select equipment from `standard_loads` catalog (searchable)
  - On select: auto-fills Qtd=1, PNOM, TDIA, FP, FD, IP/IN from DB
  - All 6 fields remain editable (user can override catalog values)
  - Add row / remove row buttons
- "Calcular" button

**Result display:**
- Table showing per-row Pn, Dmn, Pp, DMp, E_EPS
- Totals row
- Kit card: inversor modelo, qtd baterias, preço total

### 5.2 Arbitragem Form

**Fields:**
- Tarifa fora ponta (R$/kWh), Tarifa ponta (R$/kWh)
- Table with 12 rows (Janeiro–Dezembro), 2 editable columns: Consumo Ponta (kWh), Demanda Ponta (kW)
- "Calcular" button

**Result display:**
- Qty BESS recomendado (and which constraint drove it: consumo vs. potência)
- Média consumo ponta / Maior demanda ponta
- Economia mensal estimada (R$)
- Payback (meses / anos)

---

## 6. Catalog Management Pages

### 6.1 Catálogo de Cargas (`CatalogLoadsPage` — rebuilt)

Full CRUD for `standard_loads`. Table columns: Nome, PNOM (W), TDIA (h), FP, FD, IP/IN, Trifásico, Categoria, Ativo. Searchable by nome. Filter by categoria. Edit/create modal with all fields.

Initial population via migration script (one-time, from Excel).

### 6.2 Catálogo BESS (`CatalogBESSPage` — extended)

Add `pot_ca_max_eps_kva` field to inverter create/edit form and table display. Add `tipo = 'bess_comercial'` as selectable type. Ensure BESS Comercial 215 kWh entry exists (seeded in migration).

### 6.3 Admin: Upload Reference Excel

Simple admin page at `/admin/templates`:
- Two upload slots: "Backup Template" and "Arbitragem Template"
- Uploads to Supabase Storage bucket `calc-templates`
- Shows current file name + upload date
- No runtime effect — reference only

---

## 7. Test Strategy

Each engine function gets unit tests that verify outputs against manually computed values from the Excel spreadsheets:

**Backup tests:**
- Single load: verify Pn, Dmn, Pp, DMp, E_EPS against hand-calculated Excel values
- Multiple loads: verify totals
- Edge: zero TDIA, FP=1, IP/IN=1

**Arbitragem tests:**
- Known 12-month dataset: verify qty_bess, economia_mensal, payback_meses
- Constraint driven by consumption vs. by power (test both paths)

**Kit selection tests:**
- Verifies phase filtering
- Verifies P_máx EPS threshold
- Verifies battery quantity formula

---

## 8. Out of Scope

- Peak Shaving and Solar calculations: not changed in this spec
- Ploomes integration: unaffected
- Authentication: unaffected
- The Excel files are **not** executed at runtime (reference only)
- Fora Ponta columns (C, D) in Arbitragem are collected but not used in calculation today

---

## 9. Open Questions

None — all resolved during brainstorming.
