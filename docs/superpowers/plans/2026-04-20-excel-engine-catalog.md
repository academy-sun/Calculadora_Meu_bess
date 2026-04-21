# Excel-Driven Engine + Catalog Management — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace incorrect Backup and Arbitragem calculation engines with Python implementations that match the engineer's Excel spreadsheets exactly, and add complete catalog management UI with all required fields.

**Architecture:** Python engines reimplement Excel formulas cell-by-cell (ROUNDUP → `math.ceil`, SUBTOTAL → `sum`, etc.). Catalog data (previously looked up via Excel XLOOKUP) comes from Supabase DB. The Excel files are reference documents only — not executed at runtime.

**Tech Stack:** FastAPI + SQLAlchemy async (backend), React + TypeScript + TanStack Query (frontend), Supabase PostgreSQL, openpyxl (import script only).

**Spec:** `docs/superpowers/specs/2026-04-20-excel-engine-catalog-design.md`

---

## File Map

**Created:**
- `backend/migrations/003_standard_loads_new_fields.sql`
- `backend/migrations/004_products_bess_eps_comercial.sql`
- `backend/scripts/import_cargas_excel.py`

**Modified — Backend:**
- `backend/app/catalog/models.py` — add 3 fields to `StandardLoad`; add `pot_ca_max_eps_kva` to `ProductBESS`
- `backend/app/catalog/schemas.py` — mirror model changes in Pydantic schemas; add `UpdateLoad` mutation
- `backend/app/catalog/service.py` — add `get_bess_comercial()`, `update_load()`
- `backend/app/catalog/router.py` — add `PUT /catalog/loads/{id}` endpoint
- `backend/app/engines/schemas.py` — rewrite `BackupInput`, `BackupResult`; rewrite `ArbitrageInput`, `ArbitrageResult`; keep `PeakShavingInput/Result`, `SolarInput/Result` unchanged
- `backend/app/engines/bess.py` — rewrite `calculate_backup()`; rewrite `calculate_arbitrage()` (new signature); keep `calculate_peak_shaving()` unchanged
- `backend/app/engines/compatibility.py` — update `find_compatible_kits()` to use `pot_ca_max_eps_kva` and `fase`; remove `find_arbitrage_kits()` (replaced by new engine)
- `backend/app/calculate/schemas.py` — extend `CalculateRequest` with backup/arbitrage fields; extend `CalculateResponse` with per-row table and arbitrage outputs
- `backend/app/calculate/service.py` — rewrite backup and arbitrage branches; keep peak_shaving/solar branches unchanged
- `backend/tests/test_engine_bess.py` — full rewrite with Excel-verified test cases
- `backend/tests/test_engine_compatibility.py` — update kit selection tests for new criteria

**Modified — Frontend:**
- `frontend/src/types/index.ts` — extend `StandardLoad`; add `BackupLoadRow`, `BackupRowResult`, `ArbitrageMonth`; extend `CalculateResponse`
- `frontend/src/hooks/useCatalog.ts` — add `useUpdateLoad()`
- `frontend/src/pages/NewProjectPage.tsx` — rebuild backup section; rebuild arbitragem section
- `frontend/src/pages/CatalogLoadsPage.tsx` — rebuild with new fields (TDIA, FD, IP/IN, editable)
- `frontend/src/pages/CatalogBESSPage.tsx` — add `pot_ca_max_eps_kva` field; add `bess_comercial` type option

---

## Task 1: DB Migration — standard_loads new fields

**Files:**
- Create: `backend/migrations/003_standard_loads_new_fields.sql`

Run this migration in Supabase SQL Editor (Dashboard → SQL Editor).

- [ ] **Step 1: Create migration file**

```sql
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
```

- [ ] **Step 2: Run in Supabase SQL Editor and verify**

Expected: `ALTER TABLE` success. Then verify:
```sql
SELECT column_name FROM information_schema.columns
WHERE table_name = 'standard_loads'
ORDER BY ordinal_position;
```
Expected output includes: `tdia_horas`, `fator_demanda`, `ip_in`.

- [ ] **Step 3: Commit**

```bash
git add backend/migrations/003_standard_loads_new_fields.sql
git commit -m "feat(db): add tdia_horas, fator_demanda, ip_in to standard_loads"
```

---

## Task 2: DB Migration — products_bess eps field + bess_comercial seed

**Files:**
- Create: `backend/migrations/004_products_bess_eps_comercial.sql`

- [ ] **Step 1: Create migration file**

```sql
-- backend/migrations/004_products_bess_eps_comercial.sql
-- Adds P_máx EPS field to inverters; seeds the commercial BESS unit for Arbitragem

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
```

- [ ] **Step 2: Run in Supabase SQL Editor and verify**

```sql
-- Verify column added
SELECT column_name FROM information_schema.columns
WHERE table_name = 'products_bess' AND column_name = 'pot_ca_max_eps_kva';

-- Verify BESS comercial seeded
SELECT modelo, tipo, capacidade_kwh, dod_percent, preco
FROM products_bess WHERE tipo = 'bess_comercial';
```

Expected: 1 row — `BESS Comercial 215kWh`, `bess_comercial`, 215, 90, 550000.

- [ ] **Step 3: Update existing inverters with P_máx EPS values**

Run in SQL Editor for the Intelbras inverters (values from the Excel "Dados dos Inversores"):

```sql
UPDATE products_bess SET pot_ca_max_eps_kva = 6  WHERE sku = 'SIW200H-M050-W00';
UPDATE products_bess SET pot_ca_max_eps_kva = 10 WHERE sku = 'SIW200H-M075-W00';
UPDATE products_bess SET pot_ca_max_eps_kva = 12 WHERE sku = 'SIW200H-M105-W00';
UPDATE products_bess SET pot_ca_max_eps_kva = 18 WHERE sku = 'SIW400H-T015-W00';
UPDATE products_bess SET pot_ca_max_eps_kva = 36 WHERE sku = 'SIW400H-T030-W00';
```

If SKUs differ, look up models in the catalog page and adjust accordingly.

- [ ] **Step 4: Commit**

```bash
git add backend/migrations/004_products_bess_eps_comercial.sql
git commit -m "feat(db): add pot_ca_max_eps_kva to products_bess; seed bess_comercial"
```

---

## Task 3: Backend Catalog Models, Schemas, Service, Router

**Files:**
- Modify: `backend/app/catalog/models.py`
- Modify: `backend/app/catalog/schemas.py`
- Modify: `backend/app/catalog/service.py`
- Modify: `backend/app/catalog/router.py`

- [ ] **Step 1: Add new fields to `StandardLoad` model**

In `backend/app/catalog/models.py`, update the `StandardLoad` class:

```python
class StandardLoad(Base):
    __tablename__ = "standard_loads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    categoria: Mapped[str] = mapped_column(Text, nullable=False)
    potencia_w: Mapped[float] = mapped_column(Numeric, nullable=False)
    fator_potencia: Mapped[float] = mapped_column(Numeric, default=1.0)
    tdia_horas: Mapped[float | None] = mapped_column(Numeric)
    fator_demanda: Mapped[float | None] = mapped_column(Numeric)
    ip_in: Mapped[float | None] = mapped_column(Numeric)
    tensao: Mapped[str] = mapped_column(Text, nullable=False)
    fase: Mapped[str] = mapped_column(Text, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
```

Also add `pot_ca_max_eps_kva` to `ProductBESS` (after `potencia_continua_kw`):

```python
    potencia_continua_kw: Mapped[float | None] = mapped_column(Numeric)
    pot_ca_max_eps_kva: Mapped[float | None] = mapped_column(Numeric)
    max_baterias: Mapped[int | None] = mapped_column(Integer)
```

- [ ] **Step 2: Update Pydantic schemas**

In `backend/app/catalog/schemas.py`, update `StandardLoadCreate` and `StandardLoadRead`:

```python
class StandardLoadCreate(BaseModel):
    nome: str
    categoria: str
    potencia_w: float
    fator_potencia: float = 1.0
    tdia_horas: Optional[float] = None
    fator_demanda: Optional[float] = None
    ip_in: Optional[float] = None
    tensao: str
    fase: str
    ativo: bool = True


class StandardLoadRead(StandardLoadCreate):
    id: uuid.UUID

    model_config = {"from_attributes": True}
```

Also add `pot_ca_max_eps_kva` to `ProductBESSCreate` (after `potencia_continua_kw`):

```python
    potencia_continua_kw: Optional[float] = None
    pot_ca_max_eps_kva: Optional[float] = None
    max_baterias: Optional[int] = None
```

- [ ] **Step 3: Add `update_load()` and `get_bess_comercial()` to service**

In `backend/app/catalog/service.py`, after `create_load()`, add:

```python
async def update_load(db: AsyncSession, load_id: uuid.UUID, data: StandardLoadCreate) -> StandardLoad | None:
    result = await db.execute(select(StandardLoad).where(StandardLoad.id == load_id))
    load = result.scalar_one_or_none()
    if not load:
        return None
    for key, value in data.model_dump().items():
        setattr(load, key, value)
    await db.commit()
    await db.refresh(load)
    return load


async def get_bess_comercial(db: AsyncSession) -> ProductBESS | None:
    """Returns the single commercial BESS unit used by the Arbitragem engine."""
    result = await db.execute(
        select(ProductBESS).where(ProductBESS.tipo == "bess_comercial").limit(1)
    )
    return result.scalar_one_or_none()
```

- [ ] **Step 4: Add `PUT /catalog/loads/{id}` to router**

In `backend/app/catalog/router.py`, after the `POST /catalog/loads` route, add:

```python
@router.put("/loads/{load_id}", response_model=StandardLoadRead)
async def update_load(
    load_id: uuid.UUID,
    data: StandardLoadCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    load = await service.update_load(db, load_id, data)
    if not load:
        raise HTTPException(status_code=404, detail="Carga não encontrada")
    return load
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/catalog/models.py backend/app/catalog/schemas.py \
        backend/app/catalog/service.py backend/app/catalog/router.py
git commit -m "feat(catalog): add tdia_horas/fator_demanda/ip_in to loads; pot_ca_max_eps_kva to bess; update_load endpoint"
```

---

## Task 4: Data Import Script

**Files:**
- Create: `backend/scripts/import_cargas_excel.py`

This script reads `CALCULADORA BACKUP.xlsx` → aba "Dados de Cargas" and inserts all equipment rows into `standard_loads`. Run once manually.

- [ ] **Step 1: Create the import script**

```python
#!/usr/bin/env python3
"""
backend/scripts/import_cargas_excel.py

Imports equipment catalog from Excel "Dados de Cargas" sheet into standard_loads.

Usage:
    cd backend
    SUPABASE_DB_URL=postgresql+asyncpg://... python scripts/import_cargas_excel.py \
        --excel /path/to/CALCULADORA\ BACKUP.xlsx

Requires: openpyxl, asyncpg, sqlalchemy
"""
import argparse
import asyncio
import sys

import openpyxl
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Column indices in "Dados de Cargas" sheet (0-based)
COL_NOME       = 0   # A: EQUIPAMENTO
COL_IP_IN      = 1   # B: IP/IN
COL_FP         = 2   # C: FP (fator de potência)
COL_PNOM_W     = 3   # D: POT(W)
COL_FD         = 4   # E: FD (fator de demanda)
COL_TDIA       = 5   # F: Hora/d
COL_TRIFASICO  = 6   # G: 3F? (0=mono, 1=tri)
COL_CATEGORIA  = 32  # AG: CAT


def parse_row(row):
    """Return dict or None if row should be skipped."""
    nome = row[COL_NOME]
    if not nome or str(nome).startswith('['):
        return None  # header / empty placeholder

    def safe_float(v, default=1.0):
        try:
            return float(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    def safe_bool(v):
        try:
            return bool(int(v)) if v is not None else False
        except (TypeError, ValueError):
            return False

    fase = 'trifasico' if safe_bool(row[COL_TRIFASICO]) else 'monofasico'
    cat = str(row[COL_CATEGORIA]).strip() if row[COL_CATEGORIA] else 'OUTRO'

    return {
        'nome': str(nome).strip(),
        'ip_in': safe_float(row[COL_IP_IN], 1.0),
        'fator_potencia': safe_float(row[COL_FP], 1.0),
        'potencia_w': safe_float(row[COL_PNOM_W], 0.0),
        'fator_demanda': safe_float(row[COL_FD], 1.0),
        'tdia_horas': safe_float(row[COL_TDIA], 4.0),
        'fase': fase,
        'categoria': cat,
        'tensao': '220',   # default; update manually if needed
        'ativo': True,
    }


async def run(db_url: str, excel_path: str, dry_run: bool):
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    ws = wb['Dados de Cargas']

    rows_data = []
    for i, row in enumerate(ws.iter_rows(min_row=1, values_only=True)):
        if i == 0:
            continue  # header
        parsed = parse_row(row)
        if parsed:
            rows_data.append(parsed)

    print(f"Found {len(rows_data)} equipment rows to import.")
    if dry_run:
        for r in rows_data[:5]:
            print(" ", r)
        print("  ... (dry run, not inserting)")
        return

    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    from sqlalchemy import text
    async with async_session() as session:
        # Clear existing catalog entries (re-import is idempotent)
        await session.execute(text("DELETE FROM standard_loads WHERE true"))
        for r in rows_data:
            await session.execute(
                text("""
                    INSERT INTO standard_loads
                      (nome, categoria, potencia_w, fator_potencia,
                       tdia_horas, fator_demanda, ip_in, tensao, fase, ativo)
                    VALUES
                      (:nome, :categoria, :potencia_w, :fator_potencia,
                       :tdia_horas, :fator_demanda, :ip_in, :tensao, :fase, :ativo)
                """),
                r
            )
        await session.commit()
    print(f"Imported {len(rows_data)} rows into standard_loads.")
    await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--excel', required=True)
    parser.add_argument('--db-url', required=True,
                        help='Async DB URL, e.g. postgresql+asyncpg://user:pass@host/db')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    asyncio.run(run(args.db_url, args.excel, args.dry_run))
```

- [ ] **Step 2: Test with dry run**

```bash
cd backend
pip install openpyxl --break-system-packages
python scripts/import_cargas_excel.py \
  --excel "/path/to/CALCULADORA BACKUP.xlsx" \
  --db-url "postgresql+asyncpg://..." \
  --dry-run
```

Expected: prints first 5 equipment rows, no DB changes.

- [ ] **Step 3: Run for real**

```bash
python scripts/import_cargas_excel.py \
  --excel "/path/to/CALCULADORA BACKUP.xlsx" \
  --db-url "postgresql+asyncpg://..."
```

Expected: `Imported N rows into standard_loads.`

Verify in Supabase: `SELECT count(*) FROM standard_loads;` — should be 100+ rows.

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/import_cargas_excel.py
git commit -m "feat(scripts): add Excel → standard_loads import script"
```

---

## Task 5: Backup Engine — Schemas + TDD

**Files:**
- Modify: `backend/app/engines/schemas.py`
- Modify: `backend/app/engines/bess.py`
- Modify: `backend/tests/test_engine_bess.py`

This task rewrites `BackupInput`, `BackupResult`, and `calculate_backup()` to match the Excel formulas exactly. Keep `PeakShavingInput/Result`, `ArbitrageKitEconomy`, and `SolarInput/Result` unchanged.

- [ ] **Step 1: Add new backup schemas to `engines/schemas.py`**

Replace `CargaItem`, `BackupInput`, `BackupResult` in `backend/app/engines/schemas.py` with:

```python
class LoadRow:
    """Uma linha da tabela de cargas do formulário Backup."""
    def __init__(
        self,
        qtd: int,
        pnom_w: float,
        fp: float,     # fator de potência
        fd: float,     # fator de demanda
        ip_in: float,  # relação corrente de partida / nominal
        tdia_h: float, # horas de uso por dia (Backup scenario)
    ):
        self.qtd = qtd
        self.pnom_w = pnom_w
        self.fp = fp
        self.fd = fd
        self.ip_in = ip_in
        self.tdia_h = tdia_h


class LoadRowResult:
    """Resultado calculado para uma linha da tabela de cargas."""
    def __init__(
        self,
        pn_kva: float,
        dmn_kva: float,
        pp_kva: float,
        dmp_kva: float,
        e_eps_kwh: float,
    ):
        self.pn_kva = pn_kva
        self.dmn_kva = dmn_kva
        self.pp_kva = pp_kva
        self.dmp_kva = dmp_kva
        self.e_eps_kwh = e_eps_kwh


class BackupInput:
    def __init__(
        self,
        cargas: list,               # list[LoadRow]
        tipo_instalacao: str,       # "monofasico" | "trifasico"
        autonomia_h: float = 4.0,   # for record; not used in E_EPS formula
        dod_percent: float = 90.0,  # 0-100; used in kit selection
        eficiencia_roundtrip: float = 90.0,  # for record
    ):
        self.cargas = cargas
        self.tipo_instalacao = tipo_instalacao
        self.autonomia_h = autonomia_h
        self.dod_percent = dod_percent
        self.eficiencia_roundtrip = eficiencia_roundtrip


class BackupResult:
    def __init__(
        self,
        rows: list,           # list[LoadRowResult]
        total_pn: float,
        total_dmn: float,
        total_pp: float,
        total_dmp: float,
        total_e_eps: float,
    ):
        self.rows = rows
        self.total_pn = total_pn
        self.total_dmn = total_dmn
        self.total_pp = total_pp
        self.total_dmp = total_dmp
        self.total_e_eps = total_e_eps
```

Keep all other existing classes (`ArbitrageInput`, `ArbitrageKitEconomy`, `PeakShavingInput`, `PeakShavingResult`, `SolarInput`, `SolarResult`, `ProductBESSRead`).

Also remove `CargaItem` — it is no longer used (was only used by the old backup engine).

- [ ] **Step 2: Write failing tests for `calculate_backup`**

Replace the `TestBackup` class in `backend/tests/test_engine_bess.py`:

```python
import math
import pytest
from app.engines.schemas import BackupInput, LoadRow
from app.engines.bess import calculate_backup


class TestBackup:
    """Tests verified against CALCULADORA BACKUP.xlsx formulas."""

    def _make_input(self, cargas, tipo="monofasico"):
        return BackupInput(cargas=cargas, tipo_instalacao=tipo, dod_percent=90)

    def test_single_load_ar_condicionado(self):
        """AR CONDICIONADO BTU 7500: qty=1, PNOM=800W, FP=0.75, FD=1, IP/IN=6, TDIA=6h"""
        # Pn = ceil(1 * 800/0.75) / 1000 = ceil(1066.67) / 1000 = 1067/1000 = 1.067
        cargas = [LoadRow(qtd=1, pnom_w=800, fp=0.75, fd=1.0, ip_in=6.0, tdia_h=6.0)]
        result = calculate_backup(self._make_input(cargas))

        assert result.rows[0].pn_kva == pytest.approx(1.067, abs=0.001)
        assert result.rows[0].dmn_kva == pytest.approx(1.067, abs=0.001)   # 1.067 * 1.0
        assert result.rows[0].pp_kva == pytest.approx(6.402, abs=0.001)    # 1.067 * 6
        assert result.rows[0].dmp_kva == pytest.approx(6.402, abs=0.001)   # 1.067 * 6
        assert result.rows[0].e_eps_kwh == pytest.approx(6.402, abs=0.001) # 1.067 * 6

    def test_single_load_abajur(self):
        """ABAJUR 45W INCAND: qty=2, PNOM=45W, FP=1.0, FD=0.9, IP/IN=1.0, TDIA=5h"""
        # Pn = ceil(2 * 45/1.0) / 1000 = 90 / 1000 = 0.09
        cargas = [LoadRow(qtd=2, pnom_w=45, fp=1.0, fd=0.9, ip_in=1.0, tdia_h=5.0)]
        result = calculate_backup(self._make_input(cargas))

        assert result.rows[0].pn_kva == pytest.approx(0.09, abs=0.001)
        assert result.rows[0].dmn_kva == pytest.approx(0.081, abs=0.001)   # 0.09 * 0.9
        assert result.rows[0].pp_kva == pytest.approx(0.09, abs=0.001)     # 0.09 * 1.0
        assert result.rows[0].dmp_kva == pytest.approx(0.081, abs=0.001)   # 0.081 * 1.0
        assert result.rows[0].e_eps_kwh == pytest.approx(0.45, abs=0.001)  # 0.09 * 5

    def test_multiple_loads_totals(self):
        """Two loads: verify SUBTOTAL sums."""
        cargas = [
            LoadRow(qtd=1, pnom_w=800, fp=0.75, fd=1.0, ip_in=6.0, tdia_h=6.0),  # Pn=1.067
            LoadRow(qtd=2, pnom_w=45,  fp=1.0,  fd=0.9, ip_in=1.0, tdia_h=5.0),  # Pn=0.090
        ]
        result = calculate_backup(self._make_input(cargas))

        assert len(result.rows) == 2
        assert result.total_pn    == pytest.approx(1.157, abs=0.001)   # 1.067 + 0.09
        assert result.total_dmn   == pytest.approx(1.148, abs=0.001)   # 1.067 + 0.081
        assert result.total_pp    == pytest.approx(6.492, abs=0.001)   # 6.402 + 0.09
        assert result.total_dmp   == pytest.approx(6.483, abs=0.001)   # 6.402 + 0.081
        assert result.total_e_eps == pytest.approx(6.852, abs=0.001)   # 6.402 + 0.45

    def test_roundup_behavior(self):
        """ROUNDUP is ceil for positive: ceil(800/0.75) = ceil(1066.67) = 1067"""
        cargas = [LoadRow(qtd=1, pnom_w=800, fp=0.75, fd=1.0, ip_in=1.0, tdia_h=1.0)]
        result = calculate_backup(self._make_input(cargas))
        # 1067 / 1000 = 1.067 (not 1.066)
        assert result.rows[0].pn_kva == pytest.approx(1.067, abs=0.0001)

    def test_raises_on_empty_cargas(self):
        with pytest.raises(ValueError, match="cargas"):
            calculate_backup(BackupInput(cargas=[], tipo_instalacao="monofasico"))
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
cd backend && python -m pytest tests/test_engine_bess.py::TestBackup -v 2>&1 | head -30
```

Expected: `FAILED` — `calculate_backup` has wrong signature or wrong formula.

- [ ] **Step 4: Rewrite `calculate_backup()` in `bess.py`**

Replace the existing `calculate_backup()` function in `backend/app/engines/bess.py`:

```python
import math

from app.engines.schemas import (
    BackupInput, BackupResult, LoadRowResult,
    PeakShavingInput, PeakShavingResult,
    ArbitrageInput, ArbitrageKitEconomy,
)


def calculate_backup(data: BackupInput) -> BackupResult:
    """
    Replicates CALCULADORA BACKUP.xlsx formulas exactly:
      Pn (kVA)  = ROUNDUP(qtd × (PNOM / FP), 0) / 1000
      Dmn (kVA) = Pn × FD
      Pp (kVA)  = Pn × IP/IN
      DMp (kVA) = Dmn × IP/IN
      E_EPS (kWh) = Pn × TDIA
    Totals via SUBTOTAL (= SUM of non-zero rows).
    """
    if not data.cargas:
        raise ValueError("cargas não pode ser vazia")

    row_results = []
    for row in data.cargas:
        if row.fp <= 0:
            raise ValueError(f"FP inválido para carga: {row.fp}")
        pn_kva   = math.ceil(row.qtd * (row.pnom_w / row.fp)) / 1000
        dmn_kva  = round(pn_kva * row.fd, 4)
        pp_kva   = round(pn_kva * row.ip_in, 4)
        dmp_kva  = round(dmn_kva * row.ip_in, 4)
        e_eps_kwh = round(pn_kva * row.tdia_h, 4)
        row_results.append(LoadRowResult(
            pn_kva=round(pn_kva, 3),
            dmn_kva=round(dmn_kva, 3),
            pp_kva=round(pp_kva, 3),
            dmp_kva=round(dmp_kva, 3),
            e_eps_kwh=round(e_eps_kwh, 3),
        ))

    return BackupResult(
        rows=row_results,
        total_pn=round(sum(r.pn_kva for r in row_results), 3),
        total_dmn=round(sum(r.dmn_kva for r in row_results), 3),
        total_pp=round(sum(r.pp_kva for r in row_results), 3),
        total_dmp=round(sum(r.dmp_kva for r in row_results), 3),
        total_e_eps=round(sum(r.e_eps_kwh for r in row_results), 3),
    )
```

Keep `calculate_peak_shaving()` and `calculate_arbitrage_economy()` functions unchanged below.

- [ ] **Step 5: Run tests to confirm they pass**

```bash
cd backend && python -m pytest tests/test_engine_bess.py::TestBackup -v
```

Expected: all 5 tests `PASSED`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/engines/schemas.py backend/app/engines/bess.py \
        backend/tests/test_engine_bess.py
git commit -m "feat(engine): rewrite backup engine with Excel-exact formulas (TDD)"
```

---

## Task 6: Arbitragem Engine — Schemas + TDD

**Files:**
- Modify: `backend/app/engines/schemas.py`
- Modify: `backend/app/engines/bess.py`
- Modify: `backend/tests/test_engine_bess.py`

- [ ] **Step 1: Add new arbitragem schemas to `engines/schemas.py`**

Append to `backend/app/engines/schemas.py` (keep the old `ArbitrageInput` class renamed or alongside; the new one uses a different interface):

```python
class ArbitrageInputV2:
    """
    Input para o novo motor de Arbitragem (baseado na planilha CALCULADORA ARBITRAGEM.xlsx).
    Substitui ArbitrageInput (tarifa-baseada) para o fluxo de Arbitragem Tarifária.
    """
    def __init__(
        self,
        consumo_ponta_kwh: list,      # 12 valores mensais (E4:E15)
        demanda_ponta_kw: list,        # 12 valores mensais (F4:F15)
        tarifa_ponta_kwh: float,       # I4
        tarifa_fora_ponta_kwh: float,  # I3
        bess_capacidade_kwh: float,    # capacidade nominal do BESS comercial
        bess_dod: float,               # DoD em 0-100, e.g. 90
        bess_preco: float,             # preço unitário R$
    ):
        if len(consumo_ponta_kwh) != 12:
            raise ValueError("consumo_ponta_kwh deve ter 12 valores")
        if len(demanda_ponta_kw) != 12:
            raise ValueError("demanda_ponta_kw deve ter 12 valores")
        self.consumo_ponta_kwh = consumo_ponta_kwh
        self.demanda_ponta_kw = demanda_ponta_kw
        self.tarifa_ponta_kwh = tarifa_ponta_kwh
        self.tarifa_fora_ponta_kwh = tarifa_fora_ponta_kwh
        self.bess_capacidade_kwh = bess_capacidade_kwh
        self.bess_dod = bess_dod
        self.bess_preco = bess_preco


class ArbitrageResult:
    def __init__(
        self,
        qty_bess: int,
        qty_consumo: int,
        qty_potencia: int,
        avg_consumo_ponta: float,
        max_demanda_ponta: float,
        economia_mensal: float,
        custo_total: float,
        payback_meses: float | None,
    ):
        self.qty_bess = qty_bess
        self.qty_consumo = qty_consumo
        self.qty_potencia = qty_potencia
        self.avg_consumo_ponta = avg_consumo_ponta
        self.max_demanda_ponta = max_demanda_ponta
        self.economia_mensal = economia_mensal
        self.custo_total = custo_total
        self.payback_meses = payback_meses
```

- [ ] **Step 2: Write failing tests for `calculate_arbitrage_v2`**

Add `TestArbitrageV2` class to `backend/tests/test_engine_bess.py`:

```python
from statistics import mean
from app.engines.schemas import ArbitrageInputV2
from app.engines.bess import calculate_arbitrage_v2


class TestArbitrageV2:
    """Tests verified against CALCULADORA ARBITRAGEM.xlsx formulas."""

    # Fixed BESS product specs matching the seed in Task 2
    BESS_CAP  = 215.0
    BESS_DOD  = 90.0
    BESS_PRECO = 550_000.0

    def _make_input(self, consumo, demanda, tp=2.5, tfp=0.3):
        return ArbitrageInputV2(
            consumo_ponta_kwh=consumo,
            demanda_ponta_kw=demanda,
            tarifa_ponta_kwh=tp,
            tarifa_fora_ponta_kwh=tfp,
            bess_capacidade_kwh=self.BESS_CAP,
            bess_dod=self.BESS_DOD,
            bess_preco=self.BESS_PRECO,
        )

    def test_qty_driven_by_consumption(self):
        """
        avg_consumo = 10000 kWh
        fator = 22 × 215 × 0.9 × 0.9 = 3831.3
        qty_consumo = ceil(10000 / 3831.3) = ceil(2.609) = 3
        qty_potencia = ceil(250 / 100) = 3
        qty_bess = max(3, 3) = 3
        """
        consumo = [10000.0] * 12
        demanda = [250.0] * 12
        result = calculate_arbitrage_v2(self._make_input(consumo, demanda))

        assert result.qty_consumo == 3
        assert result.qty_potencia == 3
        assert result.qty_bess == 3
        assert result.avg_consumo_ponta == pytest.approx(10000.0, abs=0.01)

    def test_qty_driven_by_power(self):
        """
        avg_consumo = 500 kWh → qty_consumo = ceil(500/3831.3) = 1
        max_demanda = 450 kW → qty_potencia = ceil(450/100) = 5
        qty_bess = max(1, 5) = 5
        """
        consumo = [500.0] * 12
        demanda = [300.0] * 11 + [450.0]   # one month spikes
        result = calculate_arbitrage_v2(self._make_input(consumo, demanda))

        assert result.qty_consumo == 1
        assert result.qty_potencia == 5
        assert result.qty_bess == 5
        assert result.max_demanda_ponta == pytest.approx(450.0, abs=0.01)

    def test_economia_mensal(self):
        """economia = avg_consumo × (tarifa_ponta - tarifa_fora_ponta)"""
        consumo = [10000.0] * 12
        demanda = [250.0] * 12
        result = calculate_arbitrage_v2(self._make_input(consumo, demanda, tp=2.5, tfp=0.3))

        # 10000 × (2.5 - 0.3) = 22000
        assert result.economia_mensal == pytest.approx(22000.0, abs=0.01)

    def test_payback_meses(self):
        """payback = custo / economia"""
        consumo = [10000.0] * 12
        demanda = [250.0] * 12
        result = calculate_arbitrage_v2(self._make_input(consumo, demanda, tp=2.5, tfp=0.3))

        # qty=3, custo = 3 × 550000 = 1650000
        # payback = 1650000 / 22000 = 75.0
        assert result.custo_total == pytest.approx(1_650_000.0, abs=1.0)
        assert result.payback_meses == pytest.approx(75.0, abs=0.1)

    def test_raises_on_wrong_length(self):
        with pytest.raises(ValueError):
            ArbitrageInputV2(
                consumo_ponta_kwh=[100.0] * 11,  # wrong length
                demanda_ponta_kw=[100.0] * 12,
                tarifa_ponta_kwh=2.5,
                tarifa_fora_ponta_kwh=0.3,
                bess_capacidade_kwh=215, bess_dod=90, bess_preco=550000,
            )

    def test_payback_none_when_no_economia(self):
        """When tarifa_ponta <= tarifa_fora_ponta, economia <= 0, payback = None."""
        consumo = [1000.0] * 12
        demanda = [100.0] * 12
        result = calculate_arbitrage_v2(self._make_input(consumo, demanda, tp=0.3, tfp=0.5))
        assert result.payback_meses is None
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
cd backend && python -m pytest tests/test_engine_bess.py::TestArbitrageV2 -v 2>&1 | head -20
```

Expected: `FAILED` — `calculate_arbitrage_v2` not defined.

- [ ] **Step 4: Implement `calculate_arbitrage_v2()` in `bess.py`**

Add after `calculate_backup()` in `backend/app/engines/bess.py`:

```python
from statistics import mean as _mean

from app.engines.schemas import ArbitrageInputV2, ArbitrageResult


def calculate_arbitrage_v2(data: ArbitrageInputV2) -> ArbitrageResult:
    """
    Replicates CALCULADORA ARBITRAGEM.xlsx formulas exactly:
      E16 = AVERAGE(E4:E15)  → avg_consumo_ponta
      fator = 22 × cap × (DoD/100) × 0.9
      qty_consumo  = ROUNDUP(E16/22/(cap×dod×0.9), 0) = ceil(avg / fator)
      qty_potencia = ROUNDUP(LARGE(F4:F15, 1) / 100, 0)
      qty_bess     = MAX(qty_consumo, qty_potencia)
      economia     = E16 × (tarifa_ponta - tarifa_fora_ponta)   [I14]
      custo        = qty × preco                                 [I13]
      payback_meses = custo / economia                           [I15]
    """
    avg_consumo = round(_mean(data.consumo_ponta_kwh), 4)
    max_demanda = max(data.demanda_ponta_kw)

    fator = 22.0 * data.bess_capacidade_kwh * (data.bess_dod / 100.0) * 0.9
    qty_consumo  = math.ceil(avg_consumo / fator)
    qty_potencia = math.ceil(max_demanda / 100.0)
    qty_bess     = max(qty_consumo, qty_potencia)

    diff_tarifa     = data.tarifa_ponta_kwh - data.tarifa_fora_ponta_kwh
    economia_mensal = round(avg_consumo * diff_tarifa, 2)
    custo_total     = round(qty_bess * data.bess_preco, 2)

    if economia_mensal > 0:
        payback_meses = round(custo_total / economia_mensal, 1)
    else:
        payback_meses = None

    return ArbitrageResult(
        qty_bess=qty_bess,
        qty_consumo=qty_consumo,
        qty_potencia=qty_potencia,
        avg_consumo_ponta=round(avg_consumo, 2),
        max_demanda_ponta=round(max_demanda, 2),
        economia_mensal=economia_mensal,
        custo_total=custo_total,
        payback_meses=payback_meses,
    )
```

- [ ] **Step 5: Run all engine tests**

```bash
cd backend && python -m pytest tests/test_engine_bess.py -v
```

Expected: all tests `PASSED` (backup + arbitragem + any existing peak shaving tests).

- [ ] **Step 6: Commit**

```bash
git add backend/app/engines/schemas.py backend/app/engines/bess.py \
        backend/tests/test_engine_bess.py
git commit -m "feat(engine): add ArbitrageV2 engine with Excel-exact formulas (TDD)"
```

---

## Task 7: Kit Selection Update — TDD

**Files:**
- Modify: `backend/app/engines/compatibility.py`
- Modify: `backend/tests/test_engine_compatibility.py`

Update `find_compatible_kits()` to use `pot_ca_max_eps_kva >= total_pp` and `fase == tipo_instalacao`. Remove `find_arbitrage_kits()` (no longer used).

- [ ] **Step 1: Write failing tests for updated kit selection**

Add to `backend/tests/test_engine_compatibility.py`:

```python
from app.engines.compatibility import find_compatible_kits
from app.engines.schemas import ProductBESSRead


class TestKitSelectionV2:
    """Updated tests for Backup kit selection using P_max EPS and fase."""

    def _bat(self, cap=5.02, dod=90, preco=3000):
        return ProductBESSRead(
            marca='Intelbras', modelo='SBW CB050', sku='SBW-CB050',
            tipo='bateria', capacidade_kwh=cap, dod_percent=dod, preco=preco,
        )

    def _inv(self, eps_kva, fase='monofasico', preco=6000, pot_kw=5.0):
        inv = ProductBESSRead(
            marca='Intelbras', modelo=f'INV-{eps_kva}kVA', sku=f'INV-{eps_kva}',
            tipo='inversor_hibrido', potencia_continua_kw=pot_kw, preco=preco,
        )
        inv.pot_ca_max_eps_kva = eps_kva
        inv.fase = fase
        return inv

    def test_selects_inverter_by_eps_not_nominal(self):
        """Inverter with P_max EPS 10 kVA qualifies when total_pp = 8 kVA."""
        bat = self._bat()
        inv_small = self._inv(eps_kva=6.0, preco=5000)   # 6 < 8 → excluded
        inv_large = self._inv(eps_kva=10.0, preco=7000)  # 10 >= 8 → included

        kits = find_compatible_kits(
            baterias=[bat],
            inversores=[inv_small, inv_large],
            total_pp_kva=8.0,
            total_e_eps_kwh=4.518,   # exactly 1 × (5.02 × 0.9)
            tipo_instalacao='monofasico',
        )

        assert len(kits) == 1
        assert kits[0].inversor.modelo == 'INV-10.0kVA'

    def test_filters_by_fase(self):
        """Monofásico inversor excluded when trifásico installation."""
        bat = self._bat()
        inv_mono = self._inv(eps_kva=10.0, fase='monofasico', preco=5000)
        inv_tri  = self._inv(eps_kva=10.0, fase='trifasico',  preco=8000)

        kits = find_compatible_kits(
            baterias=[bat],
            inversores=[inv_mono, inv_tri],
            total_pp_kva=8.0,
            total_e_eps_kwh=4.518,
            tipo_instalacao='trifasico',
        )

        assert len(kits) == 1
        assert kits[0].inversor.fase == 'trifasico'

    def test_battery_quantity_formula(self):
        """qty = ceil(E_EPS / (cap × dod/100))"""
        # 5.02 kWh bat, 90% DoD → usable = 4.518 kWh
        # E_EPS = 9.5 → ceil(9.5 / 4.518) = ceil(2.10) = 3
        bat = self._bat(cap=5.02, dod=90)
        inv = self._inv(eps_kva=20.0)

        kits = find_compatible_kits(
            baterias=[bat],
            inversores=[inv],
            total_pp_kva=5.0,
            total_e_eps_kwh=9.5,
            tipo_instalacao='monofasico',
        )

        assert len(kits) == 1
        assert kits[0].qtd_baterias == 3

    def test_returns_cheapest_first(self):
        bat = self._bat()
        inv_cheap = self._inv(eps_kva=10.0, preco=5000)
        inv_pricey = self._inv(eps_kva=10.0, preco=9000)

        kits = find_compatible_kits(
            baterias=[bat],
            inversores=[inv_cheap, inv_pricey],
            total_pp_kva=8.0,
            total_e_eps_kwh=4.518,
            tipo_instalacao='monofasico',
        )

        assert kits[0].inversor.preco <= kits[-1].inversor.preco

    def test_returns_empty_when_no_eligible_inverter(self):
        bat = self._bat()
        inv = self._inv(eps_kva=4.0)   # 4 < 8 → excluded

        kits = find_compatible_kits(
            baterias=[bat], inversores=[inv],
            total_pp_kva=8.0, total_e_eps_kwh=4.518,
            tipo_instalacao='monofasico',
        )

        assert kits == []
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && python -m pytest tests/test_engine_compatibility.py::TestKitSelectionV2 -v 2>&1 | head -20
```

Expected: `FAILED` — wrong `find_compatible_kits` signature.

- [ ] **Step 3: Rewrite `find_compatible_kits()` in `compatibility.py`**

Replace the existing `find_compatible_kits()` and `find_arbitrage_kits()` in `backend/app/engines/compatibility.py` with:

```python
import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class KitBESS:
    bateria: object       # ProductBESSRead
    inversor: object      # ProductBESSRead
    qtd_baterias: int
    qtd_inversores: int
    capacidade_total_kwh: float
    potencia_total_kw: float
    preco_total: float
    economia_mensal: Optional[float] = None
    payback_anos: Optional[float] = None


def find_compatible_kits(
    baterias: list,
    inversores: list,
    total_pp_kva: float,
    total_e_eps_kwh: float,
    tipo_instalacao: str,          # "monofasico" | "trifasico"
) -> list:
    """
    For each (bateria, inversor) pair of the same brand:
    1. Filter by fase == tipo_instalacao
    2. Filter by pot_ca_max_eps_kva >= total_pp_kva
    3. Calculate battery qty = ceil(E_EPS / (cap × DoD))
    4. Sort by total price ascending.
    """
    kits = []

    for bat in baterias:
        if not bat.capacidade_kwh or not bat.dod_percent or not bat.preco:
            continue
        usable_kwh = float(bat.capacidade_kwh) * (float(bat.dod_percent) / 100.0)
        if usable_kwh <= 0:
            continue
        qtd_baterias = math.ceil(total_e_eps_kwh / usable_kwh)

        for inv in inversores:
            if bat.marca != inv.marca:
                continue

            inv_fase = getattr(inv, 'fase', None)
            if inv_fase and inv_fase != tipo_instalacao:
                continue

            eps_kva = getattr(inv, 'pot_ca_max_eps_kva', None)
            if eps_kva is not None and float(eps_kva) < total_pp_kva:
                continue

            pot_kw = float(inv.potencia_continua_kw) if inv.potencia_continua_kw else 0.0
            preco_total = float(bat.preco) * qtd_baterias + float(inv.preco)

            kits.append(KitBESS(
                bateria=bat,
                inversor=inv,
                qtd_baterias=qtd_baterias,
                qtd_inversores=1,
                capacidade_total_kwh=round(usable_kwh * qtd_baterias, 2),
                potencia_total_kw=round(pot_kw, 2),
                preco_total=round(preco_total, 2),
            ))

    kits.sort(key=lambda k: k.preco_total)
    return kits
```

- [ ] **Step 4: Run all compatibility tests**

```bash
cd backend && python -m pytest tests/test_engine_compatibility.py -v
```

Expected: `TestKitSelectionV2` all pass. Any old tests that used the previous signature will fail — remove or update them to use the new signature.

- [ ] **Step 5: Commit**

```bash
git add backend/app/engines/compatibility.py backend/tests/test_engine_compatibility.py
git commit -m "feat(engine): rewrite kit selection using P_max EPS and fase filters (TDD)"
```

---

## Task 8: Calculate Schemas + Service Layer Wiring

**Files:**
- Modify: `backend/app/calculate/schemas.py`
- Modify: `backend/app/calculate/service.py`

- [ ] **Step 1: Extend `CalculateRequest` and `CalculateResponse`**

In `backend/app/calculate/schemas.py`, add the new backup/arbitragem fields:

```python
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel


class OrigemInfo(BaseModel):
    origem: Literal["ploomes", "interno"]
    negocio_id: Optional[str] = None
    negocio_nome: Optional[str] = None
    solicitante_id: str
    solicitante_nome: str
    solicitado_em: datetime


# ── Backup load row ───────────────────────────────────────────────────────────

class BackupLoadRow(BaseModel):
    """One row from the backup load table (pre-filled from catalog, user-editable)."""
    nome: str
    qtd: int = 1
    pnom_w: float
    fp: float = 1.0
    fd: float = 1.0
    ip_in: float = 1.0
    tdia_h: float = 4.0


class BackupRowResult(BaseModel):
    nome: str
    pn_kva: float
    dmn_kva: float
    pp_kva: float
    dmp_kva: float
    e_eps_kwh: float


# ── Legacy load item (kept for peak shaving) ─────────────────────────────────

class LoadItem(BaseModel):
    nome: str
    potencia_w: float
    quantidade: int = 1
    horas_uso_dia: float


# ── Request ───────────────────────────────────────────────────────────────────

class CalculateRequest(BaseModel):
    origem_info: OrigemInfo
    tipo_calculo: Literal["backup", "peak_shaving", "arbitragem", "solar", "solar_storage"]

    # ── Backup ────────────────────────────────────────────────────────────────
    cargas_backup: Optional[list[BackupLoadRow]] = None
    tipo_instalacao: Optional[Literal["monofasico", "trifasico"]] = None
    autonomia_horas: Optional[float] = None
    dod_percent: Optional[float] = None
    eficiencia_roundtrip: Optional[float] = None
    tensao_instalacao_v: Optional[float] = None

    # ── Arbitragem ────────────────────────────────────────────────────────────
    consumo_ponta_kwh: Optional[list[float]] = None   # 12 values
    demanda_ponta_kw: Optional[list[float]] = None    # 12 values
    tarifa_ponta_rs_kwh: Optional[float] = None
    tarifa_fora_ponta_rs_kwh: Optional[float] = None

    # ── Peak Shaving ──────────────────────────────────────────────────────────
    curva_carga_kw: Optional[list[float]] = None
    cargas: Optional[list[LoadItem]] = None
    demanda_alvo_kw: Optional[float] = None
    tarifa_demanda_rs_kw: Optional[float] = None

    # ── Solar ─────────────────────────────────────────────────────────────────
    irradiacao_kwh_m2_dia: Optional[float] = None
    area_disponivel_m2: Optional[float] = None


# ── Kit info ──────────────────────────────────────────────────────────────────

class KitInfo(BaseModel):
    marca: str
    bateria_modelo: str
    inversor_modelo: str
    qtd_baterias: int
    qtd_inversores: int = 1
    capacidade_total_kwh: float
    potencia_total_kw: float
    preco_total: float
    economia_mensal_rs: Optional[float] = None
    payback_anos: Optional[float] = None


# ── Response ─────────────────────────────────────────────────────────────────

class CalculateResponse(BaseModel):
    projeto_id: str
    tipo_calculo: str
    origem: str
    negocio_id: Optional[str]
    solicitado_em: datetime
    calculado_em: datetime

    capacidade_kwh: float
    potencia_kw: float

    # Backup-specific
    backup_rows: Optional[list[BackupRowResult]] = None
    total_pn_kva: Optional[float] = None
    total_dmn_kva: Optional[float] = None
    total_pp_kva: Optional[float] = None
    total_dmp_kva: Optional[float] = None

    # Arbitragem-specific
    qty_bess: Optional[int] = None
    qty_consumo: Optional[int] = None
    qty_potencia: Optional[int] = None
    avg_consumo_ponta: Optional[float] = None
    max_demanda_ponta: Optional[float] = None

    kit_selecionado: Optional[KitInfo] = None
    economia_mensal_rs: Optional[float] = None
    economia_anual_rs: Optional[float] = None
    payback_meses: Optional[float] = None
    alternativas: list[KitInfo] = []
```

- [ ] **Step 2: Rewrite backup and arbitragem branches in `service.py`**

Replace the backup and arbitragem branches in `backend/app/calculate/service.py`. Keep the peak_shaving and solar branches unchanged.

The full `run_calculation` function (replace `if req.tipo_calculo == "backup":` and `elif req.tipo_calculo == "arbitragem":` blocks):

```python
        if req.tipo_calculo == "backup":
            if not req.cargas_backup:
                raise ValueError("cargas_backup é obrigatório para backup")
            from app.engines.schemas import BackupInput, LoadRow
            from app.engines.bess import calculate_backup

            cargas_engine = [
                LoadRow(
                    qtd=c.qtd,
                    pnom_w=c.pnom_w,
                    fp=c.fp,
                    fd=c.fd,
                    ip_in=c.ip_in,
                    tdia_h=c.tdia_h,
                )
                for c in req.cargas_backup
            ]

            backup_result = calculate_backup(BackupInput(
                cargas=cargas_engine,
                tipo_instalacao=req.tipo_instalacao or "monofasico",
                dod_percent=req.dod_percent or 90.0,
                autonomia_h=req.autonomia_horas or 4.0,
                eficiencia_roundtrip=req.eficiencia_roundtrip or 90.0,
            ))

            capacidade_kwh = backup_result.total_e_eps
            potencia_kw = backup_result.total_pp

            from app.engines.compatibility import find_compatible_kits
            kits = find_compatible_kits(
                baterias=baterias,
                inversores=inversores,
                total_pp_kva=backup_result.total_pp,
                total_e_eps_kwh=backup_result.total_e_eps,
                tipo_instalacao=req.tipo_instalacao or "monofasico",
            )
            kit_selecionado, alternativas = _kits_to_response(kits)

            # Build per-row results for frontend table
            from app.calculate.schemas import BackupRowResult
            backup_rows = [
                BackupRowResult(
                    nome=req.cargas_backup[i].nome,
                    pn_kva=r.pn_kva,
                    dmn_kva=r.dmn_kva,
                    pp_kva=r.pp_kva,
                    dmp_kva=r.dmp_kva,
                    e_eps_kwh=r.e_eps_kwh,
                )
                for i, r in enumerate(backup_result.rows)
            ]

        elif req.tipo_calculo == "arbitragem":
            if not req.consumo_ponta_kwh or not req.demanda_ponta_kw:
                raise ValueError("consumo_ponta_kwh e demanda_ponta_kw são obrigatórios")

            from app.engines.schemas import ArbitrageInputV2
            from app.engines.bess import calculate_arbitrage_v2
            from app.catalog.service import get_bess_comercial

            bess_com = await get_bess_comercial(db)
            if not bess_com:
                raise ValueError("Produto BESS Comercial não encontrado no catálogo")

            arb_result = calculate_arbitrage_v2(ArbitrageInputV2(
                consumo_ponta_kwh=req.consumo_ponta_kwh,
                demanda_ponta_kw=req.demanda_ponta_kw,
                tarifa_ponta_kwh=req.tarifa_ponta_rs_kwh or 0.0,
                tarifa_fora_ponta_kwh=req.tarifa_fora_ponta_rs_kwh or 0.0,
                bess_capacidade_kwh=float(bess_com.capacidade_kwh),
                bess_dod=float(bess_com.dod_percent),
                bess_preco=float(bess_com.preco),
            ))

            capacidade_kwh = arb_result.qty_bess * float(bess_com.capacidade_kwh) * (float(bess_com.dod_percent) / 100)
            potencia_kw = 0.0
            economia_mensal = arb_result.economia_mensal
            payback_meses = arb_result.payback_meses
            backup_rows = None
```

Also update the `CalculateResponse(...)` constructor call at the bottom of `run_calculation` to include the new fields:

```python
        return CalculateResponse(
            projeto_id=str(project.id),
            tipo_calculo=req.tipo_calculo,
            origem=req.origem_info.origem,
            negocio_id=req.origem_info.negocio_id,
            solicitado_em=solicitado_em,
            calculado_em=calculado_em,
            capacidade_kwh=capacidade_kwh,
            potencia_kw=potencia_kw,
            backup_rows=backup_rows if req.tipo_calculo == "backup" else None,
            total_pn_kva=backup_result.total_pn if req.tipo_calculo == "backup" else None,
            total_dmn_kva=backup_result.total_dmn if req.tipo_calculo == "backup" else None,
            total_pp_kva=backup_result.total_pp if req.tipo_calculo == "backup" else None,
            total_dmp_kva=backup_result.total_dmp if req.tipo_calculo == "backup" else None,
            qty_bess=arb_result.qty_bess if req.tipo_calculo == "arbitragem" else None,
            qty_consumo=arb_result.qty_consumo if req.tipo_calculo == "arbitragem" else None,
            qty_potencia=arb_result.qty_potencia if req.tipo_calculo == "arbitragem" else None,
            avg_consumo_ponta=arb_result.avg_consumo_ponta if req.tipo_calculo == "arbitragem" else None,
            max_demanda_ponta=arb_result.max_demanda_ponta if req.tipo_calculo == "arbitragem" else None,
            kit_selecionado=kit_selecionado,
            economia_mensal_rs=economia_mensal,
            economia_anual_rs=economia_anual,
            payback_meses=payback_meses,
            alternativas=alternativas,
        )
```

Note: `backup_result` and `arb_result` are scoped to their respective branches — initialize them to `None` at the top of `run_calculation` alongside the other variables, and reference them safely.

- [ ] **Step 3: Run backend tests**

```bash
cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: all engine tests pass. Fix any import errors from the refactor.

- [ ] **Step 4: Commit**

```bash
git add backend/app/calculate/schemas.py backend/app/calculate/service.py
git commit -m "feat(service): wire new Backup/ArbitrageV2 engines into calculate pipeline"
```

---

## Task 9: Frontend Types + Hooks

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/hooks/useCatalog.ts`

- [ ] **Step 1: Update `StandardLoad` type and add new calculation types**

In `frontend/src/types/index.ts`, update `StandardLoad`:

```typescript
export interface StandardLoad {
  id: string
  nome: string
  categoria: string
  potencia_w: number
  fator_potencia: number
  tdia_horas?: number
  fator_demanda?: number
  ip_in?: number
  tensao: string
  fase: 'monofasico' | 'trifasico'
  ativo: boolean
}
```

Add new types for backup form:

```typescript
export interface BackupLoadRow {
  nome: string
  qtd: number
  pnom_w: number
  fp: number
  fd: number
  ip_in: number
  tdia_h: number
}

export interface BackupRowResult {
  nome: string
  pn_kva: number
  dmn_kva: number
  pp_kva: number
  dmp_kva: number
  e_eps_kwh: number
}
```

Update `KitInfo`:

```typescript
export interface KitInfo {
  marca: string
  bateria_modelo: string
  inversor_modelo: string
  qtd_baterias: number
  qtd_inversores?: number
  capacidade_total_kwh: number
  potencia_total_kw: number
  preco_total: number
  economia_mensal_rs?: number
  payback_anos?: number
}
```

Update `CalculateResponse`:

```typescript
export interface CalculateResponse {
  projeto_id: string
  tipo_calculo: TipoCalculo
  origem: string
  negocio_id?: string
  solicitado_em: string
  calculado_em: string
  capacidade_kwh: number
  potencia_kw: number

  // Backup
  backup_rows?: BackupRowResult[]
  total_pn_kva?: number
  total_dmn_kva?: number
  total_pp_kva?: number
  total_dmp_kva?: number

  // Arbitragem
  qty_bess?: number
  qty_consumo?: number
  qty_potencia?: number
  avg_consumo_ponta?: number
  max_demanda_ponta?: number

  kit_selecionado?: KitInfo
  economia_mensal_rs?: number
  economia_anual_rs?: number
  payback_meses?: number
  alternativas: KitInfo[]
}
```

- [ ] **Step 2: Add `useUpdateLoad` hook**

In `frontend/src/hooks/useCatalog.ts`, add after `useCreateLoad`:

```typescript
export function useUpdateLoad() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...data }: StandardLoad) =>
      apiPut<StandardLoad>(`/catalog/loads/${id}`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['catalog', 'loads'] }),
  })
}
```

Also import `apiPut` if not already imported.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/hooks/useCatalog.ts
git commit -m "feat(frontend): update types for new backup/arbitragem engine outputs"
```

---

## Task 10: Frontend — Backup Form

**Files:**
- Modify: `frontend/src/pages/NewProjectPage.tsx`

Replace the backup section of the form. Keep peak_shaving, solar, and resultado sections intact.

- [ ] **Step 1: Add new state variables for backup**

In `NewProjectPage.tsx`, replace the backup-related state (removing `autonomia`, keeping `tensao`, `dod`):

```typescript
// ── Backup ────────────────────────────────────────────────────────────────────
type BackupRow = {
  id: string
  nome: string
  qtd: number
  pnom_w: number
  fp: number
  fd: number
  ip_in: number
  tdia_h: number
}

// Inside component:
const [tipoInstalacao, setTipoInstalacao] = useState<'monofasico' | 'trifasico'>('monofasico')
const [autonomia, setAutonomia] = useState('4')
const [dod, setDod] = useState('90')
const [backupRows, setBackupRows] = useState<BackupRow[]>([])
```

- [ ] **Step 2: Add helper functions for backup row management**

```typescript
function addBackupRow(load: StandardLoad) {
  const id = crypto.randomUUID()
  setBackupRows(prev => [...prev, {
    id,
    nome: load.nome,
    qtd: 1,
    pnom_w: load.potencia_w,
    fp: load.fator_potencia ?? 1,
    fd: load.fator_demanda ?? 1,
    ip_in: load.ip_in ?? 1,
    tdia_h: load.tdia_horas ?? 4,
  }])
}

function updateBackupRow(id: string, field: keyof Omit<BackupRow, 'id' | 'nome'>, value: number) {
  setBackupRows(prev => prev.map(r => r.id === id ? { ...r, [field]: value } : r))
}

function removeBackupRow(id: string) {
  setBackupRows(prev => prev.filter(r => r.id !== id))
}
```

- [ ] **Step 3: Update payload assembly for backup**

In `handleSubmit`, replace the backup payload block:

```typescript
    if (tipo === 'backup') {
      payload.cargas_backup = backupRows.map(({ id: _id, ...r }) => r)
      payload.tipo_instalacao = tipoInstalacao
      payload.autonomia_horas = parseFloat(autonomia)
      payload.dod_percent = parseFloat(dod)
      payload.eficiencia_roundtrip = 90
    }
```

- [ ] **Step 4: Replace backup form JSX**

Replace the `{tipo === 'backup' && (...)}` block in the dados step:

```tsx
{tipo === 'backup' && (
  <>
    {/* Tipo de instalação */}
    <div>
      <label className="mb-1 block text-sm font-medium text-gray-700">Tipo de Instalação</label>
      <div className="flex gap-3">
        {(['monofasico', 'trifasico'] as const).map(t => (
          <button key={t} type="button"
            onClick={() => setTipoInstalacao(t)}
            className={`flex-1 rounded-lg border-2 py-2 text-sm font-medium transition-colors ${
              tipoInstalacao === t ? 'border-primary bg-primary/5 text-primary' : 'border-gray-200 text-gray-600 hover:border-gray-300'
            }`}>
            {t === 'monofasico' ? 'Monofásico' : 'Trifásico'}
          </button>
        ))}
      </div>
    </div>

    {/* Parâmetros */}
    <div className="grid grid-cols-2 gap-3">
      <Field label="Autonomia (h)" value={autonomia} onChange={setAutonomia} placeholder="4" required />
      <Field label="DoD (%)" value={dod} onChange={setDod} placeholder="90" required />
    </div>

    {/* Tabela de cargas */}
    <div>
      <label className="mb-2 block text-sm font-medium text-gray-700">Cargas da Instalação</label>
      {loads && loads.length > 0 && (
        <select
          className="mb-2 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
          onChange={e => {
            const load = loads.find(l => l.id === e.target.value)
            if (load) { addBackupRow(load); e.target.value = '' }
          }}
        >
          <option value="">+ Adicionar carga do catálogo...</option>
          {loads.map(l => (
            <option key={l.id} value={l.id}>{l.nome} ({l.potencia_w}W)</option>
          ))}
        </select>
      )}

      {backupRows.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="w-full text-xs">
            <thead className="bg-gray-50">
              <tr>
                {['Equipamento', 'Qtd', 'PNOM (W)', 'TDIA (h)', 'FP', 'FD', 'IP/IN', ''].map(h => (
                  <th key={h} className="px-2 py-2 text-left text-gray-500 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {backupRows.map(row => (
                <tr key={row.id} className="border-t border-gray-100">
                  <td className="px-2 py-1 text-gray-700">{row.nome}</td>
                  {(['qtd', 'pnom_w', 'tdia_h', 'fp', 'fd', 'ip_in'] as const).map(f => (
                    <td key={f} className="px-1 py-1">
                      <input type="number" value={row[f]} step="any" min={0}
                        onChange={e => updateBackupRow(row.id, f, parseFloat(e.target.value))}
                        className="w-16 rounded border border-gray-200 px-1 py-0.5 text-center text-xs focus:border-primary focus:outline-none" />
                    </td>
                  ))}
                  <td className="px-1 py-1">
                    <button type="button" onClick={() => removeBackupRow(row.id)}
                      className="text-red-400 hover:text-red-600">✕</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {backupRows.length === 0 && (
        <p className="text-xs text-gray-400">Adicione ao menos uma carga do catálogo.</p>
      )}
    </div>
  </>
)}
```

- [ ] **Step 5: Update result display to show backup table**

In the resultado step, add before the kit card:

```tsx
{result?.backup_rows && result.backup_rows.length > 0 && (
  <div className="mb-4 overflow-x-auto rounded-lg border border-gray-200">
    <table className="w-full text-xs">
      <thead className="bg-gray-50">
        <tr>
          {['Equipamento', 'Pn (kVA)', 'Dmn (kVA)', 'Pp (kVA)', 'DMp (kVA)', 'E_EPS (kWh)'].map(h => (
            <th key={h} className="px-3 py-2 text-left text-gray-500 font-medium">{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {result.backup_rows.map((r, i) => (
          <tr key={i} className="border-t border-gray-100">
            <td className="px-3 py-1 text-gray-700">{r.nome}</td>
            <td className="px-3 py-1">{r.pn_kva}</td>
            <td className="px-3 py-1">{r.dmn_kva}</td>
            <td className="px-3 py-1">{r.pp_kva}</td>
            <td className="px-3 py-1">{r.dmp_kva}</td>
            <td className="px-3 py-1 font-medium">{r.e_eps_kwh}</td>
          </tr>
        ))}
        <tr className="border-t-2 border-gray-300 bg-gray-50 font-semibold">
          <td className="px-3 py-1">TOTAL</td>
          <td className="px-3 py-1">{result.total_pn_kva}</td>
          <td className="px-3 py-1">{result.total_dmn_kva}</td>
          <td className="px-3 py-1">{result.total_pp_kva}</td>
          <td className="px-3 py-1">{result.total_dmp_kva}</td>
          <td className="px-3 py-1">{result.capacidade_kwh} kWh</td>
        </tr>
      </tbody>
    </table>
  </div>
)}
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/NewProjectPage.tsx
git commit -m "feat(frontend): rebuild Backup form with load table and per-row results"
```

---

## Task 11: Frontend — Arbitragem Form

**Files:**
- Modify: `frontend/src/pages/NewProjectPage.tsx`

- [ ] **Step 1: Add arbitragem state**

Inside `NewProjectPage` component, add:

```typescript
// ── Arbitragem ────────────────────────────────────────────────────────────────
const MONTHS = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho',
                'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']
const [arbConsumoPonta, setArbConsumoPonta] = useState<string[]>(Array(12).fill(''))
const [arbDemandaPonta, setArbDemandaPonta] = useState<string[]>(Array(12).fill(''))
const [arbTarifaPonta, setArbTarifaPonta] = useState('2.50')
const [arbTarifaForaPonta, setArbTarifaForaPonta] = useState('0.30')
```

- [ ] **Step 2: Update arbitragem payload**

In `handleSubmit`, replace the `else if (tipo === 'arbitragem')` block:

```typescript
    } else if (tipo === 'arbitragem') {
      payload.consumo_ponta_kwh = arbConsumoPonta.map(v => parseFloat(v) || 0)
      payload.demanda_ponta_kw  = arbDemandaPonta.map(v => parseFloat(v) || 0)
      payload.tarifa_ponta_rs_kwh = parseFloat(arbTarifaPonta)
      payload.tarifa_fora_ponta_rs_kwh = parseFloat(arbTarifaForaPonta)
    }
```

- [ ] **Step 3: Replace arbitragem form JSX**

Replace the `{tipo === 'arbitragem' && (...)}` block:

```tsx
{tipo === 'arbitragem' && (
  <>
    <div className="grid grid-cols-2 gap-3">
      <Field label="Tarifa Fora da Ponta (R$/kWh)" value={arbTarifaForaPonta}
        onChange={setArbTarifaForaPonta} placeholder="ex: 0.30" required />
      <Field label="Tarifa na Ponta (R$/kWh)" value={arbTarifaPonta}
        onChange={setArbTarifaPonta} placeholder="ex: 2.50" required />
    </div>

    <div>
      <label className="mb-2 block text-sm font-medium text-gray-700">
        Consumo e Demanda na Ponta — dados da fatura (12 meses)
      </label>
      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-3 py-2 text-left text-gray-500 font-medium w-28">Mês</th>
              <th className="px-3 py-2 text-left text-gray-500 font-medium">Consumo Ponta (kWh)</th>
              <th className="px-3 py-2 text-left text-gray-500 font-medium">Demanda Ponta (kW)</th>
            </tr>
          </thead>
          <tbody>
            {MONTHS.map((mes, i) => (
              <tr key={mes} className="border-t border-gray-100">
                <td className="px-3 py-1 text-gray-500">{mes}</td>
                <td className="px-2 py-1">
                  <input type="number" step="any" min={0}
                    value={arbConsumoPonta[i]}
                    placeholder="0"
                    onChange={e => setArbConsumoPonta(prev => {
                      const next = [...prev]; next[i] = e.target.value; return next
                    })}
                    className="w-full rounded border border-gray-200 px-2 py-1 text-sm focus:border-primary focus:outline-none" />
                </td>
                <td className="px-2 py-1">
                  <input type="number" step="any" min={0}
                    value={arbDemandaPonta[i]}
                    placeholder="0"
                    onChange={e => setArbDemandaPonta(prev => {
                      const next = [...prev]; next[i] = e.target.value; return next
                    })}
                    className="w-full rounded border border-gray-200 px-2 py-1 text-sm focus:border-primary focus:outline-none" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  </>
)}
```

- [ ] **Step 4: Update arbitragem result display**

In the resultado step, add after the capacidade/potência/payback cards when `tipo === 'arbitragem'`:

```tsx
{result?.qty_bess !== undefined && (
  <div className="mb-4 rounded-xl border border-gray-200 bg-white p-4">
    <p className="mb-3 text-xs font-bold uppercase text-gray-500">Dimensionamento Arbitragem</p>
    <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
      <div>
        <p className="text-xs text-gray-400">Qtd BESS</p>
        <p className="text-2xl font-bold text-primary">{result.qty_bess}</p>
        <p className="text-xs text-gray-400">
          {result.qty_bess === result.qty_consumo ? 'limitado por consumo' : 'limitado por demanda'}
        </p>
      </div>
      <div>
        <p className="text-xs text-gray-400">Média Consumo Ponta</p>
        <p className="font-semibold">{result.avg_consumo_ponta?.toFixed(1)} kWh/mês</p>
      </div>
      <div>
        <p className="text-xs text-gray-400">Maior Demanda Ponta</p>
        <p className="font-semibold">{result.max_demanda_ponta?.toFixed(1)} kW</p>
      </div>
      <div>
        <p className="text-xs text-gray-400">Economia Estimada</p>
        <p className="font-semibold text-green-700">
          R$ {result.economia_mensal_rs?.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}/mês
        </p>
      </div>
    </div>
  </div>
)}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/NewProjectPage.tsx
git commit -m "feat(frontend): rebuild Arbitragem form with 12-month table and dimensionamento results"
```

---

## Task 12: Frontend — Catalog Loads Page

**Files:**
- Modify: `frontend/src/pages/CatalogLoadsPage.tsx`

Rebuild with new fields (TDIA, FD, IP/IN) in table and create/edit modal.

- [ ] **Step 1: Replace `CatalogLoadsPage.tsx`**

```tsx
import { useState } from 'react'
import { useStandardLoads, useCreateLoad, useUpdateLoad } from '@/hooks/useCatalog'
import type { StandardLoad } from '@/types'

type LoadForm = Omit<StandardLoad, 'id'>

const EMPTY_FORM: LoadForm = {
  nome: '', categoria: '', potencia_w: 0,
  fator_potencia: 1, tdia_horas: 4, fator_demanda: 1, ip_in: 1,
  tensao: '220', fase: 'monofasico', ativo: true,
}

export function CatalogLoadsPage() {
  const { data: loads, isLoading } = useStandardLoads()
  const createMutation = useCreateLoad()
  const updateMutation = useUpdateLoad()

  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<StandardLoad | null>(null)
  const [form, setForm] = useState<LoadForm>(EMPTY_FORM)
  const [search, setSearch] = useState('')
  const [error, setError] = useState<string | null>(null)

  function set(field: keyof LoadForm, value: unknown) {
    setForm(prev => ({ ...prev, [field]: value }))
  }

  function openCreate() { setForm(EMPTY_FORM); setEditing(null); setShowForm(true) }
  function openEdit(l: StandardLoad) {
    const { id: _id, ...rest } = l
    setForm(rest as LoadForm); setEditing(l); setShowForm(true)
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault(); setError(null)
    try {
      if (editing) await updateMutation.mutateAsync({ id: editing.id, ...form })
      else await createMutation.mutateAsync(form)
      setShowForm(false)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erro ao salvar')
    }
  }

  const filtered = (loads ?? []).filter(l =>
    l.nome.toLowerCase().includes(search.toLowerCase()) ||
    l.categoria.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Catálogo de Cargas</h1>
          <p className="text-sm text-gray-500">Equipamentos para Backup</p>
        </div>
        <button onClick={openCreate}
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-dark">
          + Nova Carga
        </button>
      </div>

      <input
        type="text" value={search} onChange={e => setSearch(e.target.value)}
        placeholder="Buscar por nome ou categoria..."
        className="mb-4 w-full max-w-sm rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
      />

      {isLoading ? (
        <p className="text-sm text-gray-400">Carregando...</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-200">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                {['Nome', 'PNOM (W)', 'TDIA (h)', 'FP', 'FD', 'IP/IN', 'Fase', 'Cat.', 'Ativo', ''].map(h => (
                  <th key={h} className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filtered.map(l => (
                <tr key={l.id} className="hover:bg-gray-50">
                  <td className="px-3 py-2 font-medium">{l.nome}</td>
                  <td className="px-3 py-2">{l.potencia_w}</td>
                  <td className="px-3 py-2">{l.tdia_horas ?? '—'}</td>
                  <td className="px-3 py-2">{l.fator_potencia}</td>
                  <td className="px-3 py-2">{l.fator_demanda ?? '—'}</td>
                  <td className="px-3 py-2">{l.ip_in ?? '—'}</td>
                  <td className="px-3 py-2 capitalize">{l.fase}</td>
                  <td className="px-3 py-2 text-xs text-gray-500">{l.categoria}</td>
                  <td className="px-3 py-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${l.ativo ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                      {l.ativo ? 'Ativo' : 'Inativo'}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <button onClick={() => openEdit(l)} className="text-xs text-primary hover:underline">Editar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 && (
            <p className="py-8 text-center text-sm text-gray-400">Nenhuma carga encontrada.</p>
          )}
        </div>
      )}

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
            <h2 className="mb-4 text-lg font-bold">{editing ? 'Editar Carga' : 'Nova Carga'}</h2>
            <form onSubmit={handleSave} className="space-y-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-600">Nome</label>
                <input required value={form.nome} onChange={e => set('nome', e.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:outline-none" />
              </div>
              <div className="grid grid-cols-3 gap-3">
                {([
                  { label: 'PNOM (W)', field: 'potencia_w' },
                  { label: 'TDIA (h)', field: 'tdia_horas' },
                  { label: 'FP', field: 'fator_potencia' },
                  { label: 'FD', field: 'fator_demanda' },
                  { label: 'IP/IN', field: 'ip_in' },
                ] as { label: string; field: keyof LoadForm }[]).map(({ label, field }) => (
                  <div key={field}>
                    <label className="mb-1 block text-xs font-medium text-gray-600">{label}</label>
                    <input type="number" step="any"
                      value={form[field] as number ?? ''}
                      onChange={e => set(field, parseFloat(e.target.value))}
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:outline-none" />
                  </div>
                ))}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs font-medium text-gray-600">Fase</label>
                  <select value={form.fase} onChange={e => set('fase', e.target.value)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm">
                    <option value="monofasico">Monofásico</option>
                    <option value="trifasico">Trifásico</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-gray-600">Categoria</label>
                  <input value={form.categoria} onChange={e => set('categoria', e.target.value)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:outline-none" />
                </div>
              </div>
              <div className="flex items-center gap-2">
                <input type="checkbox" checked={form.ativo} onChange={e => set('ativo', e.target.checked)} id="ativo" />
                <label htmlFor="ativo" className="text-sm text-gray-700">Ativo</label>
              </div>
              {error && <p className="rounded bg-red-50 px-3 py-2 text-xs text-red-600">{error}</p>}
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setShowForm(false)}
                  className="rounded-lg border border-gray-300 px-4 py-2 text-sm hover:bg-gray-50">
                  Cancelar
                </button>
                <button type="submit"
                  className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-dark">
                  Salvar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/CatalogLoadsPage.tsx
git commit -m "feat(frontend): rebuild CatalogLoadsPage with TDIA, FD, IP/IN fields"
```

---

## Task 13: Frontend — Catalog BESS Page Extension

**Files:**
- Modify: `frontend/src/pages/CatalogBESSPage.tsx`
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Add `pot_ca_max_eps_kva` to `ProductBESS` type**

In `frontend/src/types/index.ts`, update `ProductBESS`:

```typescript
export interface ProductBESS {
  id: string
  marca: string
  modelo: string
  sku: string
  tipo: 'bateria' | 'inversor_hibrido' | 'bess_comercial'  // add bess_comercial
  fase?: 'monofasico' | 'trifasico'
  tensao_nominal_v?: number
  tensao_min_dc_v?: number
  tensao_max_dc_v?: number
  corrente_max_carga_a?: number
  corrente_max_descarga_a?: number
  corrente_max_dc_a?: number
  capacidade_kwh?: number
  dod_percent?: number
  potencia_continua_kw?: number
  pot_ca_max_eps_kva?: number      // ← NEW
  max_baterias?: number
  preco: number
  disponivel: boolean
  atualizado_em: string
}
```

- [ ] **Step 2: Add `pot_ca_max_eps_kva` to BESS create/edit form**

In `frontend/src/pages/CatalogBESSPage.tsx`, update `EMPTY_FORM` to include the new field:

```typescript
const EMPTY_FORM: BESSForm = {
  marca: '', modelo: '', sku: '', tipo: 'bateria', disponivel: true, preco: 0,
  pot_ca_max_eps_kva: undefined,
}
```

Add the field to the form JSX — after `potencia_continua_kw` field, add:

```tsx
<div>
  <label className="mb-1 block text-xs font-medium text-gray-600">P_máx EPS (kVA)</label>
  <input type="number" step="any"
    value={form.pot_ca_max_eps_kva ?? ''}
    onChange={e => set('pot_ca_max_eps_kva', e.target.value ? parseFloat(e.target.value) : undefined)}
    placeholder="EPS power — inversors only"
    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:outline-none" />
</div>
```

Add `tipo = 'bess_comercial'` option to the tipo dropdown:

```tsx
<select value={form.tipo} onChange={e => set('tipo', e.target.value)}
  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm">
  <option value="bateria">Bateria</option>
  <option value="inversor_hibrido">Inversor Híbrido</option>
  <option value="bess_comercial">BESS Comercial</option>
</select>
```

Add `pot_ca_max_eps_kva` column to the product table (show for inverters):

```tsx
<td className="px-3 py-2">{p.pot_ca_max_eps_kva ? `${p.pot_ca_max_eps_kva} kVA` : '—'}</td>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/CatalogBESSPage.tsx frontend/src/types/index.ts
git commit -m "feat(frontend): add pot_ca_max_eps_kva and bess_comercial type to BESS catalog"
```

---

## Self-Review Checklist

**Spec coverage:**
- ✅ §3.1 — Task 1 (standard_loads new fields migration)
- ✅ §3.2 — Task 2 (products_bess eps field + seed) + Task 3 (service: get_bess_comercial) + Task 13 (frontend type)
- ✅ §3.3 — Task 2 (bess_comercial seed) + Task 3 (catalog schema update)
- ✅ §3.4 — Storage upload: left for a future iteration (low priority, admin tool)
- ✅ §3.5 — Task 4 (import script)
- ✅ §4.1 — Task 5 (Backup engine TDD)
- ✅ §4.2 — Task 6 (Arbitragem engine TDD)
- ✅ §4.3 — Task 7 (Kit selection TDD)
- ✅ §5.1 — Task 10 (Backup form)
- ✅ §5.2 — Task 11 (Arbitragem form)
- ✅ §6.1 — Task 12 (CatalogLoads rebuilt)
- ✅ §6.2 — Task 13 (CatalogBESS extended)
- ⏭️ §6.3 Admin template upload — deferred (low risk, no runtime dependency)
- ✅ §7 — Tests in Tasks 5, 6, 7

**Type consistency verified:**
- `LoadRow` defined in Task 5 → used in Task 8 service
- `ArbitrageInputV2` / `ArbitrageResult` defined in Task 6 → used in Task 8
- `BackupLoadRow` in Task 9 types → sent by Task 10 form → received by Task 8 service
- `find_compatible_kits(baterias, inversores, total_pp_kva, total_e_eps_kwh, tipo_instalacao)` defined Task 7 → called Task 8

**No placeholders confirmed** — all code blocks are complete.
