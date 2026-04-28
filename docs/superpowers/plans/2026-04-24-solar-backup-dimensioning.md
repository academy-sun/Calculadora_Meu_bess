# Solar Backup Dimensioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional solar module sizing step to the Backup calculation flow, which selects the best FV module from the catalog and computes the optimal string configuration respecting the selected hybrid inverter's MPPT electrical limits.

**Architecture:** New engine function `size_solar_strings()` in `backend/app/engines/solar_strings.py` receives the selected inverter, all available solar modules, and the required kWp; it returns a `SolarStringsResult` dataclass. The backup branch in `calculate/service.py` calls this after `find_compatible_kits()` and maps the result to a new `SolarDimensionamento` Pydantic model returned in `CalculateResponse`. The frontend adds a city autocomplete component backed by a static JSON file (~5500 cities) and renders the solar result below the BESS kit card.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy (backend), React 18 / TypeScript / Tailwind (frontend), Supabase PostgreSQL (DB), Vite (build).

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/migrations/007_solar_mppt_fields.sql` | Create | Add 8 new nullable columns to DB |
| `backend/app/catalog/models.py` | Modify | Add 4 MPPT cols to ProductBESS, 4 electrical cols to ProductSolar |
| `backend/app/catalog/schemas.py` | Modify | Add same fields to Pydantic Create/Read schemas |
| `backend/app/engines/schemas.py` | Modify | Add `SolarStringsInput` and `SolarStringsResult` dataclasses |
| `backend/app/engines/solar_strings.py` | Create | `size_solar_strings()` algorithm |
| `backend/app/calculate/schemas.py` | Modify | Add `SolarDimensionamento` model + 2 request fields + 1 response field |
| `backend/app/calculate/service.py` | Modify | Call `size_solar_strings()` in backup branch |
| `frontend/scripts/generate_irradiacao.py` | Create | Parse irradiacao.txt → irradiacao.json |
| `frontend/src/data/irradiacao.json` | Create | ~5500 cities with HSP avg |
| `frontend/src/types/index.ts` | Modify | Add 8 catalog fields + `SolarDimensionamento` type |
| `frontend/src/components/CityCombobox.tsx` | Create | Searchable city autocomplete |
| `frontend/src/pages/NewProjectPage.tsx` | Modify | 2 new form fields + solar result section |
| `frontend/src/pages/CatalogBESSPage.tsx` | Modify | 4 MPPT fields in inverter form |
| `frontend/src/pages/CatalogSolarPage.tsx` | Modify | 4 electrical fields in module form |

---

## Task 1: Database Migration

**Files:**
- Create: `backend/migrations/007_solar_mppt_fields.sql`

- [ ] **Step 1: Create the migration file**

```sql
-- backend/migrations/007_solar_mppt_fields.sql
-- MPPT fields for hybrid inverters (products_bess)
ALTER TABLE products_bess
  ADD COLUMN IF NOT EXISTS mppt_v_min      FLOAT,
  ADD COLUMN IF NOT EXISTS mppt_v_max      FLOAT,
  ADD COLUMN IF NOT EXISTS mppt_i_max_a    FLOAT,
  ADD COLUMN IF NOT EXISTS mppt_qty        INTEGER;

-- Electrical specs for FV modules (products_solar)
ALTER TABLE products_solar
  ADD COLUMN IF NOT EXISTS voc_v   FLOAT,
  ADD COLUMN IF NOT EXISTS vmp_v   FLOAT,
  ADD COLUMN IF NOT EXISTS isc_a   FLOAT,
  ADD COLUMN IF NOT EXISTS imp_a   FLOAT;
```

- [ ] **Step 2: Run the migration in Supabase**

Open the Supabase SQL Editor for project `debiageyayshcvbpivdq` and paste the contents of `007_solar_mppt_fields.sql`. Click **Run**.

Expected: `Success. No rows returned.`

- [ ] **Step 3: Verify columns exist**

```sql
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name IN ('products_bess', 'products_solar')
  AND column_name IN ('mppt_v_min','mppt_v_max','mppt_i_max_a','mppt_qty','voc_v','vmp_v','isc_a','imp_a')
ORDER BY table_name, column_name;
```

Expected: 8 rows returned (4 for each table).

- [ ] **Step 4: Commit the migration file**

```bash
cd /path/to/Calculadora_Meu_bess
git add backend/migrations/007_solar_mppt_fields.sql
git commit -m "feat(db): add MPPT and FV module electrical fields migration 007"
```

---

## Task 2: Backend ORM Models

**Files:**
- Modify: `backend/app/catalog/models.py`

- [ ] **Step 1: Add 4 MPPT columns to `ProductBESS`**

In `backend/app/catalog/models.py`, after the `pot_ca_max_eps_kva` line, add:

```python
    pot_ca_max_eps_kva: Mapped[float | None] = mapped_column(Numeric)
    mppt_v_min: Mapped[float | None] = mapped_column(Numeric)
    mppt_v_max: Mapped[float | None] = mapped_column(Numeric)
    mppt_i_max_a: Mapped[float | None] = mapped_column(Numeric)
    mppt_qty: Mapped[int | None] = mapped_column(Integer)
    max_baterias: Mapped[int | None] = mapped_column(Integer)
```

- [ ] **Step 2: Add 4 electrical columns to `ProductSolar`**

In `backend/app/catalog/models.py`, after the `eficiencia_pct` line, add:

```python
    eficiencia_pct: Mapped[float | None] = mapped_column(Numeric)
    voc_v: Mapped[float | None] = mapped_column(Numeric)
    vmp_v: Mapped[float | None] = mapped_column(Numeric)
    isc_a: Mapped[float | None] = mapped_column(Numeric)
    imp_a: Mapped[float | None] = mapped_column(Numeric)
    potencia_nominal_kw: Mapped[float | None] = mapped_column(Numeric)
```

The complete `ProductSolar` class should now be:

```python
class ProductSolar(Base):
    __tablename__ = "products_solar"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    marca: Mapped[str] = mapped_column(Text, nullable=False)
    modelo: Mapped[str] = mapped_column(Text, nullable=False)
    sku: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    potencia_pico_wp: Mapped[float | None] = mapped_column(Numeric)
    eficiencia_pct: Mapped[float | None] = mapped_column(Numeric)
    voc_v: Mapped[float | None] = mapped_column(Numeric)
    vmp_v: Mapped[float | None] = mapped_column(Numeric)
    isc_a: Mapped[float | None] = mapped_column(Numeric)
    imp_a: Mapped[float | None] = mapped_column(Numeric)
    potencia_nominal_kw: Mapped[float | None] = mapped_column(Numeric)
    mppt_min_v: Mapped[float | None] = mapped_column(Numeric)
    mppt_max_v: Mapped[float | None] = mapped_column(Numeric)
    fase: Mapped[str | None] = mapped_column(Text)
    preco: Mapped[float] = mapped_column(Numeric, nullable=False)
    disponivel: Mapped[bool] = mapped_column(Boolean, default=True)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/catalog/models.py
git commit -m "feat(catalog): add MPPT and FV electrical fields to ORM models"
```

---

## Task 3: Backend Catalog Schemas (Pydantic)

**Files:**
- Modify: `backend/app/catalog/schemas.py`

- [ ] **Step 1: Add 4 MPPT fields to `ProductBESSCreate`**

After `pot_ca_max_eps_kva`, add:

```python
    pot_ca_max_eps_kva: Optional[float] = None
    mppt_v_min: Optional[float] = None
    mppt_v_max: Optional[float] = None
    mppt_i_max_a: Optional[float] = None
    mppt_qty: Optional[int] = None
    max_baterias: Optional[int] = None
```

- [ ] **Step 2: Add 4 electrical fields to `ProductSolarCreate`**

The complete `ProductSolarCreate` should be:

```python
class ProductSolarCreate(BaseModel):
    marca: str
    modelo: str
    sku: str
    tipo: str
    potencia_pico_wp: Optional[float] = None
    eficiencia_pct: Optional[float] = None
    voc_v: Optional[float] = None
    vmp_v: Optional[float] = None
    isc_a: Optional[float] = None
    imp_a: Optional[float] = None
    potencia_nominal_kw: Optional[float] = None
    mppt_min_v: Optional[float] = None
    mppt_max_v: Optional[float] = None
    fase: Optional[str] = None
    preco: float
    disponivel: bool = True
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/catalog/schemas.py
git commit -m "feat(catalog): add MPPT and FV electrical fields to Pydantic schemas"
```

---

## Task 4: Engine Schemas — SolarStringsInput and SolarStringsResult

**Files:**
- Modify: `backend/app/engines/schemas.py`

- [ ] **Step 1: Add two new classes at the end of `engines/schemas.py`**

```python
class SolarStringsInput:
    """Input para o dimensionamento de strings FV no backup."""
    def __init__(
        self,
        consumo_medio_mensal_kwh: float,
        hsp_media: float,
    ):
        self.consumo_medio_mensal_kwh = consumo_medio_mensal_kwh
        self.hsp_media = hsp_media


class SolarStringsResult:
    """Resultado do dimensionamento de strings FV."""
    def __init__(
        self,
        modulo_marca: str,
        modulo_modelo: str,
        modulo_wp: float,
        qty_modulos: int,
        n_serie: int,
        n_paralelo: int,
        mppt_qty: int,
        kwp_instalado: float,
        cobertura_pct: float,
    ):
        self.modulo_marca = modulo_marca
        self.modulo_modelo = modulo_modelo
        self.modulo_wp = modulo_wp
        self.qty_modulos = qty_modulos
        self.n_serie = n_serie
        self.n_paralelo = n_paralelo
        self.mppt_qty = mppt_qty
        self.kwp_instalado = kwp_instalado
        self.cobertura_pct = cobertura_pct
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/engines/schemas.py
git commit -m "feat(engines): add SolarStringsInput and SolarStringsResult schemas"
```

---

## Task 5: Solar Strings Engine

**Files:**
- Create: `backend/app/engines/solar_strings.py`

- [ ] **Step 1: Create the engine file**

```python
# backend/app/engines/solar_strings.py
import math
from typing import Optional

from app.engines.schemas import SolarStringsInput, SolarStringsResult

EFICIENCIA_SISTEMA = 0.8
DIAS_MES = 30


def _kwp_necessario(consumo_mensal: float, hsp: float) -> float:
    return consumo_mensal / (hsp * EFICIENCIA_SISTEMA * DIAS_MES)


def _size_module(inversor, modulo, kwp_necessario: float) -> Optional[SolarStringsResult]:
    mppt_v_min = getattr(inversor, 'mppt_v_min', None)
    mppt_v_max = getattr(inversor, 'mppt_v_max', None)
    mppt_i_max_a = getattr(inversor, 'mppt_i_max_a', None)
    mppt_qty = getattr(inversor, 'mppt_qty', None)
    voc_v = getattr(modulo, 'voc_v', None)
    vmp_v = getattr(modulo, 'vmp_v', None)
    imp_a = getattr(modulo, 'imp_a', None)
    wp = getattr(modulo, 'potencia_pico_wp', None)

    if any(v is None for v in [mppt_v_min, mppt_v_max, mppt_i_max_a, mppt_qty,
                                voc_v, vmp_v, imp_a, wp]):
        return None

    mppt_v_min = float(mppt_v_min)
    mppt_v_max = float(mppt_v_max)
    mppt_i_max_a = float(mppt_i_max_a)
    mppt_qty = int(mppt_qty)
    voc_v = float(voc_v)
    vmp_v = float(vmp_v)
    imp_a = float(imp_a)
    wp = float(wp)

    if vmp_v <= 0 or voc_v <= 0 or imp_a <= 0 or wp <= 0:
        return None

    n_serie_min = math.ceil(mppt_v_min / vmp_v)
    n_serie_max = math.floor(mppt_v_max / voc_v)

    if n_serie_min > n_serie_max or n_serie_max < 1:
        return None

    n_serie = n_serie_max
    n_paralelo_max = math.floor(mppt_i_max_a / imp_a)
    if n_paralelo_max < 1:
        return None

    n_strings_necessarias = math.ceil(kwp_necessario * 1000 / (n_serie * wp))
    n_paralelo = math.ceil(n_strings_necessarias / mppt_qty)
    n_paralelo = min(n_paralelo, n_paralelo_max)

    qty_modulos = n_serie * n_paralelo * mppt_qty
    kwp_instalado = round(qty_modulos * wp / 1000, 3)
    cobertura_pct = round(min(kwp_instalado / kwp_necessario * 100, 999.9), 1)

    return SolarStringsResult(
        modulo_marca=str(modulo.marca),
        modulo_modelo=str(modulo.modelo),
        modulo_wp=wp,
        qty_modulos=qty_modulos,
        n_serie=n_serie,
        n_paralelo=n_paralelo,
        mppt_qty=mppt_qty,
        kwp_instalado=kwp_instalado,
        cobertura_pct=cobertura_pct,
    )


def size_solar_strings(
    inversor,
    modulos: list,
    solar_input: SolarStringsInput,
) -> Optional[SolarStringsResult]:
    """
    Seleciona o melhor módulo FV e retorna configuração ótima de strings.
    Retorna None se nenhum módulo for compatível ou inversor sem dados MPPT.
    """
    kwp_nec = _kwp_necessario(
        solar_input.consumo_medio_mensal_kwh,
        solar_input.hsp_media,
    )

    candidatos = []
    for modulo in modulos:
        if not getattr(modulo, 'disponivel', True):
            continue
        result = _size_module(inversor, modulo, kwp_nec)
        if result is not None:
            candidatos.append((modulo, result))

    if not candidatos:
        return None

    def score(item):
        modulo, r = item
        penalty = 0 if r.kwp_instalado <= kwp_nec * 1.2 else 1000
        distance = abs(r.kwp_instalado - kwp_nec)
        preco_total = float(modulo.preco) * r.qty_modulos if modulo.preco else float('inf')
        return (penalty, distance, preco_total)

    candidatos.sort(key=score)
    return candidatos[0][1]
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/engines/solar_strings.py
git commit -m "feat(engines): add solar string sizing engine"
```

---

## Task 6: Calculate Schemas — SolarDimensionamento

**Files:**
- Modify: `backend/app/calculate/schemas.py`

- [ ] **Step 1: Add `SolarDimensionamento` Pydantic model**

After the `KitInfo` class definition, add:

```python
class SolarDimensionamento(BaseModel):
    modulo_marca: str
    modulo_modelo: str
    modulo_wp: float
    qty_modulos: int
    n_serie: int
    n_paralelo: int
    mppt_qty: int
    kwp_instalado: float
    cobertura_pct: float
```

- [ ] **Step 2: Add 2 optional fields to `CalculateRequest`**

In the `# ── Backup ──` section, add:

```python
    # ── Solar (opcional, dentro do backup) ───────────────────────────────────
    consumo_medio_mensal_kwh: Optional[float] = None
    hsp_media: Optional[float] = None
```

- [ ] **Step 3: Add 1 field to `CalculateResponse`**

After `alternativas: list[KitInfo] = []`, add:

```python
    solar_dimensionamento: Optional[SolarDimensionamento] = None
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/calculate/schemas.py
git commit -m "feat(calculate): add SolarDimensionamento schema and request/response fields"
```

---

## Task 7: Calculate Service — Call Solar Sizing

**Files:**
- Modify: `backend/app/calculate/service.py`

- [ ] **Step 1: Add imports at top of `service.py`**

Add to the existing imports block:

```python
from app.engines.solar_strings import size_solar_strings
from app.engines.schemas import (
    BackupInput, LoadRow,
    ArbitrageInputV2,
    PeakShavingInput, SolarInput,
    PeakShavingResult, SolarResult,
    SolarStringsInput,           # ← new
)
from app.calculate.schemas import (
    BackupLoadRow, BackupRowResult,
    CalculateRequest, CalculateResponse, KitInfo, LoadItem,
    SolarDimensionamento,        # ← new
)
```

- [ ] **Step 2: Add solar sizing variable and list_solar import**

At the top of `run_calculation`, add a new variable alongside the existing ones:

```python
        solar_dim_result = None  # SolarStringsResult | None
```

And add the solar products fetch alongside `todos_bess`:

```python
        from app.catalog.service import list_bess, get_bess_comercial, list_solar
        todos_bess = await list_bess(db, disponivel_only=True)
        baterias = [p for p in todos_bess if p.tipo == "bateria"]
        inversores = [p for p in todos_bess if p.tipo == "inversor_hibrido"]
        modulos_fv = await list_solar(db, disponivel_only=True)
        modulos_fv = [m for m in modulos_fv if m.tipo == "modulo_fv"]
```

- [ ] **Step 3: Add solar sizing call in the backup branch**

Immediately after `kit_selecionado, alternativas = _kits_to_response(kits)` inside the `if req.tipo_calculo == "backup":` block, add:

```python
            # ── Solar dimensioning (optional) ────────────────────────────────
            if (
                req.consumo_medio_mensal_kwh
                and req.hsp_media
                and kit_selecionado
                and kits  # raw kits list still available
            ):
                best_kit = kits[0]  # already sorted by price ascending
                solar_dim_result = size_solar_strings(
                    inversor=best_kit.inversor,
                    modulos=modulos_fv,
                    solar_input=SolarStringsInput(
                        consumo_medio_mensal_kwh=req.consumo_medio_mensal_kwh,
                        hsp_media=req.hsp_media,
                    ),
                )
```

- [ ] **Step 4: Map `solar_dim_result` to `SolarDimensionamento` in the response**

In the `return CalculateResponse(...)` call, add the final field:

```python
            solar_dimensionamento=(
                SolarDimensionamento(
                    modulo_marca=solar_dim_result.modulo_marca,
                    modulo_modelo=solar_dim_result.modulo_modelo,
                    modulo_wp=solar_dim_result.modulo_wp,
                    qty_modulos=solar_dim_result.qty_modulos,
                    n_serie=solar_dim_result.n_serie,
                    n_paralelo=solar_dim_result.n_paralelo,
                    mppt_qty=solar_dim_result.mppt_qty,
                    kwp_instalado=solar_dim_result.kwp_instalado,
                    cobertura_pct=solar_dim_result.cobertura_pct,
                )
                if solar_dim_result else None
            ),
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/calculate/service.py
git commit -m "feat(calculate): integrate solar string sizing into backup flow"
```

---

## Task 8: Generate irradiacao.json

**Files:**
- Create: `frontend/scripts/generate_irradiacao.py`
- Create: `frontend/src/data/irradiacao.json`

- [ ] **Step 1: Create the generator script**

```python
# frontend/scripts/generate_irradiacao.py
"""
Generates frontend/src/data/irradiacao.json from the uploaded irradiacao.txt file.

Usage:
    python frontend/scripts/generate_irradiacao.py \
        --input /path/to/irradiacao.txt \
        --output frontend/src/data/irradiacao.json
"""
import argparse
import json
import re
import sys


def parse_irradiacao(input_path: str) -> list[dict]:
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract the JS array from the function body
    match = re.search(r'const Dados = (\[.*?\]);', content, re.DOTALL)
    if not match:
        # Try without semicolon at end
        match = re.search(r'const Dados = (\[.*\])', content, re.DOTALL)
    if not match:
        print("ERROR: Could not find 'const Dados = [...]' in input file", file=sys.stderr)
        sys.exit(1)

    raw_json = match.group(1)
    data = json.loads(raw_json)

    cities = []
    for item in data:
        mes_a_mes = item.get('Mês a mês', '')
        parts = mes_a_mes.split(';')
        if not parts:
            continue
        hsp_str = parts[-1].strip().replace(',', '.')
        try:
            hsp = float(hsp_str)
        except ValueError:
            continue

        sigla = item.get('Sigla', '').lstrip('-').strip()

        cities.append({
            'nome': item.get('Nome', '').strip(),
            'estado': item.get('Estado', '').strip(),
            'sigla': sigla,
            'hsp': hsp,
        })

    return cities


def main():
    parser = argparse.ArgumentParser(description='Generate irradiacao.json from irradiacao.txt')
    parser.add_argument('--input', required=True, help='Path to irradiacao.txt')
    parser.add_argument('--output', required=True, help='Path to output irradiacao.json')
    args = parser.parse_args()

    cities = parse_irradiacao(args.input)
    print(f"Parsed {len(cities)} cities")

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(cities, f, ensure_ascii=False, separators=(',', ':'))

    print(f"Written to {args.output}")


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Create the output directory and run the script**

```bash
mkdir -p frontend/src/data

python frontend/scripts/generate_irradiacao.py \
  --input /sessions/sleepy-inspiring-ride/mnt/uploads/irradiacao.txt \
  --output frontend/src/data/irradiacao.json
```

Expected output:
```
Parsed 5570 cities   (approximate)
Written to frontend/src/data/irradiacao.json
```

- [ ] **Step 3: Verify the output**

```bash
python3 -c "
import json
with open('frontend/src/data/irradiacao.json') as f:
    data = json.load(f)
print('Total cities:', len(data))
print('First entry:', data[0])
print('Last entry:', data[-1])
"
```

Expected: `Total cities: ~5500`, each entry has `nome`, `estado`, `sigla`, `hsp` (float).

- [ ] **Step 4: Commit**

```bash
git add frontend/scripts/generate_irradiacao.py frontend/src/data/irradiacao.json
git commit -m "feat(data): add Brazilian cities irradiation data + generator script"
```

---

## Task 9: Frontend Types

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Add 4 MPPT fields to `ProductBESS`**

In the `ProductBESS` interface, after `pot_ca_max_eps_kva`, add:

```typescript
  mppt_v_min?: number
  mppt_v_max?: number
  mppt_i_max_a?: number
  mppt_qty?: number
```

- [ ] **Step 2: Add 4 electrical fields to `ProductSolar`**

In the `ProductSolar` interface, after `eficiencia_pct`, add:

```typescript
  voc_v?: number
  vmp_v?: number
  isc_a?: number
  imp_a?: number
```

- [ ] **Step 3: Add `SolarDimensionamento` type and update `CalculateResponse`**

After the `StandardLoad` interface, add:

```typescript
export interface SolarDimensionamento {
  modulo_marca: string
  modulo_modelo: string
  modulo_wp: number
  qty_modulos: number
  n_serie: number
  n_paralelo: number
  mppt_qty: number
  kwp_instalado: number
  cobertura_pct: number
}
```

Then in `CalculateResponse` (wherever it is defined in types), add:

```typescript
  solar_dimensionamento?: SolarDimensionamento | null
```

If `CalculateResponse` is not in `types/index.ts`, search for it:

```bash
grep -r "CalculateResponse" frontend/src --include="*.ts" --include="*.tsx" -l
```

Add the field to whichever file defines it.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(types): add MPPT, FV electrical fields and SolarDimensionamento type"
```

---

## Task 10: Catalog Admin Pages — New Fields

**Files:**
- Modify: `frontend/src/pages/CatalogBESSPage.tsx`
- Modify: `frontend/src/pages/CatalogSolarPage.tsx`

- [ ] **Step 1: Add 4 MPPT fields to `CatalogBESSPage` `EMPTY_FORM`**

In `CatalogBESSPage.tsx`, update `EMPTY_FORM`:

```typescript
const EMPTY_FORM: BESSForm = {
  marca: '', modelo: '', sku: '', tipo: 'bateria', fase: undefined, disponivel: true, preco: 0,
  pot_ca_max_eps_kva: undefined,
  mppt_v_min: undefined,
  mppt_v_max: undefined,
  mppt_i_max_a: undefined,
  mppt_qty: undefined,
}
```

- [ ] **Step 2: Add MPPT fields to the BESS form — inside the `grid grid-cols-2` section**

After the `NField` for `pot_ca_max_eps_kva`, add 4 more `NField` entries. The grid section becomes:

```tsx
              <div className="grid grid-cols-2 gap-3">
                <NField label="Tensão Nominal (V)" value={form.tensao_nominal_v} onChange={v => set('tensao_nominal_v', v)} />
                <NField label="Capacidade (kWh)" value={form.capacidade_kwh} onChange={v => set('capacidade_kwh', v)} />
                <NField label="DoD (%)" value={form.dod_percent} onChange={v => set('dod_percent', v)} />
                <NField label="Corrente Máx Desc. (A)" value={form.corrente_max_descarga_a} onChange={v => set('corrente_max_descarga_a', v)} />
                <NField label="Tensão Mín DC (V)" value={form.tensao_min_dc_v} onChange={v => set('tensao_min_dc_v', v)} />
                <NField label="Tensão Máx DC (V)" value={form.tensao_max_dc_v} onChange={v => set('tensao_max_dc_v', v)} />
                <NField label="Corrente Máx DC (A)" value={form.corrente_max_dc_a} onChange={v => set('corrente_max_dc_a', v)} />
                <NField label="Potência Contínua (kW)" value={form.potencia_continua_kw} onChange={v => set('potencia_continua_kw', v)} />
                <NField label="P_máx EPS (kVA)" value={form.pot_ca_max_eps_kva} onChange={v => set('pot_ca_max_eps_kva', v)} />
                <NField label="MPPT V Mín (V)" value={form.mppt_v_min} onChange={v => set('mppt_v_min', v)} />
                <NField label="MPPT V Máx (V)" value={form.mppt_v_max} onChange={v => set('mppt_v_max', v)} />
                <NField label="MPPT I Máx (A)" value={form.mppt_i_max_a} onChange={v => set('mppt_i_max_a', v)} />
                <NField label="Qtd. Entradas MPPT" value={form.mppt_qty} onChange={v => set('mppt_qty', v)} />
              </div>
```

- [ ] **Step 3: Add 4 electrical fields to `CatalogSolarPage` `EMPTY_FORM`**

```typescript
const EMPTY_FORM: SolarForm = {
  marca: '', modelo: '', sku: '', tipo: 'modulo_fv', preco: 0, disponivel: true,
  voc_v: undefined,
  vmp_v: undefined,
  isc_a: undefined,
  imp_a: undefined,
}
```

- [ ] **Step 4: Add electrical fields to the solar form — inside `tipo === 'modulo_fv'` section**

Inside the `{form.tipo === 'modulo_fv' && (...)}` block, after the existing Potência Pico and Eficiência fields, add:

```tsx
                  <div><label className="mb-1 block text-xs font-medium text-gray-700">Voc (V)</label>
                    <input type="number" step="any" value={form.voc_v ?? ''}
                      onChange={e => set('voc_v', e.target.value ? parseFloat(e.target.value) : undefined)}
                      className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm" /></div>
                  <div><label className="mb-1 block text-xs font-medium text-gray-700">Vmp (V)</label>
                    <input type="number" step="any" value={form.vmp_v ?? ''}
                      onChange={e => set('vmp_v', e.target.value ? parseFloat(e.target.value) : undefined)}
                      className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm" /></div>
                  <div><label className="mb-1 block text-xs font-medium text-gray-700">Isc (A)</label>
                    <input type="number" step="any" value={form.isc_a ?? ''}
                      onChange={e => set('isc_a', e.target.value ? parseFloat(e.target.value) : undefined)}
                      className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm" /></div>
                  <div><label className="mb-1 block text-xs font-medium text-gray-700">Imp (A)</label>
                    <input type="number" step="any" value={form.imp_a ?? ''}
                      onChange={e => set('imp_a', e.target.value ? parseFloat(e.target.value) : undefined)}
                      className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm" /></div>
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/CatalogBESSPage.tsx frontend/src/pages/CatalogSolarPage.tsx
git commit -m "feat(catalog-ui): add MPPT and FV electrical fields to admin forms"
```

---

## Task 11: CityCombobox Component

**Files:**
- Create: `frontend/src/components/CityCombobox.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/src/components/CityCombobox.tsx
import { useState, useRef, useEffect } from 'react'
import irradiacaoData from '@/data/irradiacao.json'

interface City {
  nome: string
  estado: string
  sigla: string
  hsp: number
}

const CITIES = irradiacaoData as City[]

interface Props {
  value: string          // display label shown in input
  onSelect: (city: City) => void
  placeholder?: string
}

export function CityCombobox({ value, onSelect, placeholder = 'Buscar cidade...' }: Props) {
  const [query, setQuery] = useState(value)
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  // Close dropdown on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // Sync external value resets
  useEffect(() => { setQuery(value) }, [value])

  const filtered = query.length < 2
    ? []
    : CITIES.filter(c => {
        const q = query.toLowerCase()
        return (
          c.nome.toLowerCase().includes(q) ||
          c.sigla.toLowerCase().includes(q) ||
          c.estado.toLowerCase().includes(q)
        )
      }).slice(0, 30)

  function handleSelect(city: City) {
    setQuery(`${city.nome} - ${city.sigla}`)
    setOpen(false)
    onSelect(city)
  }

  return (
    <div ref={ref} className="relative">
      <input
        type="text"
        value={query}
        onChange={e => { setQuery(e.target.value); setOpen(true) }}
        onFocus={() => { if (query.length >= 2) setOpen(true) }}
        placeholder={placeholder}
        className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
        autoComplete="off"
      />
      {open && filtered.length > 0 && (
        <ul className="absolute z-50 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-lg">
          {filtered.map(city => (
            <li
              key={`${city.nome}-${city.sigla}`}
              onMouseDown={() => handleSelect(city)}
              className="cursor-pointer px-3 py-2 text-sm hover:bg-primary/5"
            >
              <span className="font-medium">{city.nome}</span>
              <span className="ml-1 text-gray-400 text-xs">— {city.sigla} · {city.hsp} HSP</span>
            </li>
          ))}
        </ul>
      )}
      {open && query.length >= 2 && filtered.length === 0 && (
        <div className="absolute z-50 mt-1 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-400 shadow-lg">
          Nenhuma cidade encontrada
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript can resolve the JSON import**

Check `frontend/tsconfig.json` (or `tsconfig.app.json`) for `"resolveJsonModule": true`. If missing, add it to the `compilerOptions`.

```bash
grep "resolveJsonModule" frontend/tsconfig*.json || echo "NOT FOUND — needs to be added"
```

If not found, open the tsconfig file and add `"resolveJsonModule": true` to `compilerOptions`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/CityCombobox.tsx
git commit -m "feat(ui): add CityCombobox autocomplete component with irradiation data"
```

---

## Task 12: NewProjectPage — Form Fields + Solar Result Section

**Files:**
- Modify: `frontend/src/pages/NewProjectPage.tsx`

- [ ] **Step 1: Add two new state variables for solar input**

After the existing backup state variables (`tipoInstalacao`, `autonomia`, `dod`, `backupRows`), add:

```typescript
  const [consumoMensal, setConsumoMensal] = useState('')
  const [hspMedia, setHspMedia] = useState<number | null>(null)
  const [cidadeLabel, setCidadeLabel] = useState('')
```

- [ ] **Step 2: Add import for `CityCombobox`**

At the top of the file, add:

```typescript
import { CityCombobox } from '@/components/CityCombobox'
```

Also update the `CalculateResponse` import if `SolarDimensionamento` is needed inline — but since it's part of `CalculateResponse`, no extra import is needed.

- [ ] **Step 3: Add solar payload fields to `handleSubmit`**

Inside the `if (tipo === 'backup')` block, after setting `eficiencia_roundtrip`, add:

```typescript
      const consumoNum = parseFloat(consumoMensal)
      if (consumoNum > 0 && hspMedia) {
        payload.consumo_medio_mensal_kwh = consumoNum
        payload.hsp_media = hspMedia
      }
```

- [ ] **Step 4: Add solar input fields to the Backup form**

After the closing `</>` of the autonomia/DoD grid (after `<Field label="DoD (%)" ...>`), and before the Cargas section, add:

```tsx
              {/* ── Solar (opcional) ───────────────────────────────────────── */}
              <div className="rounded-lg border border-amber-100 bg-amber-50 p-4 space-y-3">
                <p className="text-xs font-semibold text-amber-700 uppercase tracking-wide">
                  ☀️ Dimensionamento Solar (opcional)
                </p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="mb-1 block text-sm font-medium text-gray-700">
                      Consumo Médio Mensal (kWh)
                    </label>
                    <input
                      type="number" step="any" min={0}
                      value={consumoMensal}
                      onChange={e => setConsumoMensal(e.target.value)}
                      placeholder="ex: 1200"
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-gray-700">
                      Cidade (HSP)
                    </label>
                    <CityCombobox
                      value={cidadeLabel}
                      onSelect={city => {
                        setHspMedia(city.hsp)
                        setCidadeLabel(`${city.nome} - ${city.sigla}`)
                      }}
                      placeholder="Buscar cidade..."
                    />
                    {hspMedia && (
                      <p className="mt-1 text-xs text-gray-400">HSP média: {hspMedia} kWh/m²/dia</p>
                    )}
                  </div>
                </div>
              </div>
```

- [ ] **Step 5: Add solar result section in Step: Resultado**

After the kit BESS card (after the `{result?.kit_selecionado && (...)}` block, or at the end of the backup results), add:

```tsx
      {/* Solar dimensioning result */}
      {result?.solar_dimensionamento && (
        <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 p-4">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-amber-800 uppercase tracking-wide">
            ☀️ Dimensionamento Solar
          </h3>
          <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            <div>
              <span className="text-gray-500">Módulo selecionado</span>
              <p className="font-medium">
                {result.solar_dimensionamento.modulo_marca} {result.solar_dimensionamento.modulo_modelo}
                {' '}— {result.solar_dimensionamento.modulo_wp} Wp
              </p>
            </div>
            <div>
              <span className="text-gray-500">Configuração</span>
              <p className="font-medium font-mono">
                {result.solar_dimensionamento.n_serie}S ×{' '}
                {result.solar_dimensionamento.n_paralelo}P ×{' '}
                {result.solar_dimensionamento.mppt_qty} MPPT
              </p>
            </div>
            <div>
              <span className="text-gray-500">Total de módulos</span>
              <p className="font-medium">{result.solar_dimensionamento.qty_modulos} unidades</p>
            </div>
            <div>
              <span className="text-gray-500">Potência instalada</span>
              <p className="font-medium">{result.solar_dimensionamento.kwp_instalado} kWp</p>
            </div>
            <div className="col-span-2">
              <span className="text-gray-500">Cobertura estimada</span>
              <p className="font-medium text-amber-700">
                {result.solar_dimensionamento.cobertura_pct}% do consumo mensal
              </p>
            </div>
          </div>
        </div>
      )}
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/NewProjectPage.tsx
git commit -m "feat(ui): add solar dimensioning fields to backup form and result display"
```

---

## Task 13: Push and Verify Deploy

- [ ] **Step 1: Push all commits to main**

```bash
git push origin main
```

- [ ] **Step 2: Verify Railway backend deployed successfully**

Check Railway logs for the backend service. Look for:
```
Application startup complete.
```

If any import errors appear (e.g. `ImportError: cannot import name 'list_solar'`), verify that `catalog/service.py` exports `list_solar`.

- [ ] **Step 3: Verify Vercel frontend deployed**

Visit the Vercel deployment URL. Open the Backup form and confirm:
- The "☀️ Dimensionamento Solar" section appears with Consumo and Cidade fields
- Typing 3+ characters in Cidade shows autocomplete results
- The catalogs admin shows MPPT fields on inverter form and electrical fields on module form

- [ ] **Step 4: End-to-end smoke test**

1. Open Admin → Catálogo BESS → edit an inverter → fill in `MPPT V Mín`, `MPPT V Máx`, `MPPT I Máx (A)`, `Qtd. Entradas MPPT` → Save
2. Open Admin → Catálogo Solar → create a módulo FV with `Voc`, `Vmp`, `Isc`, `Imp` → Save
3. Open Novo Cálculo → Backup → add a load → fill Consumo Médio Mensal + select a city
4. Calculate → result should show **Dimensionamento Solar** section with module, configuration, and kWp

---

## Notes

- `list_solar` already exists in `backend/app/catalog/service.py` with `disponivel_only` parameter — no new function needed.
- The `irradiacao.txt` file is a JavaScript file with a `getIrradiationList` function containing a `const Dados = [...]` array. The generator script extracts this array via regex.
- The `SolarDimensionamento` field is only populated when `kit_selecionado` is not null AND the inverter has MPPT data AND at least one module in the catalog has the electrical specs filled in.
