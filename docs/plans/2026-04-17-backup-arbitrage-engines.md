# Engine Backup + Arbitragem Tarifária — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace incorrect calculation formulas for Backup and Arbitragem Tarifária engines with correct specs, add `max_baterias` to the BESS catalog, and update all layers (schemas → engine → service → tests).

**Architecture:** Pure-Python engine functions in `engines/bess.py` consume typed engine-schema inputs and return raw physics results. `service.py` converts API request fields to engine inputs, calls the engine, then calls a kit-finder in `compatibility.py`. Two kit-finders: `find_compatible_kits` (backup — ordered by min cost) and new `find_arbitrage_kits` (arbitragem — ordered by min payback). `catalog/models.py` gains a `max_baterias` column used by both finders.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async ORM, Pydantic v2, pytest / unittest

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `backend/migrations/002_add_max_baterias.sql` | CREATE | ALTER TABLE migration for new column |
| `backend/app/catalog/models.py` | MODIFY | Add `max_baterias` to `ProductBESS` ORM model |
| `backend/app/catalog/schemas.py` | MODIFY | Add `max_baterias` to Pydantic schemas |
| `backend/app/engines/schemas.py` | MODIFY | New `CargaItem`, updated `BackupInput/Result`, updated `ArbitrageInput`, new `ArbitrageKitEconomy` |
| `backend/app/engines/bess.py` | MODIFY | Rewrite `calculate_backup`; add `calculate_arbitrage_economy`; remove old `calculate_arbitrage` |
| `backend/app/engines/compatibility.py` | MODIFY | Add `qtd_inversores`/`economia_mensal` to `KitBESS`; apply `max_baterias` in backup finder; add `find_arbitrage_kits` |
| `backend/app/calculate/schemas.py` | MODIFY | Add `dod_percent`, arbitrage tariff fields to `CalculateRequest`; add `qtd_inversores`, `economia_mensal_rs`, `payback_anos` to `KitInfo` |
| `backend/app/calculate/service.py` | MODIFY | Rewrite backup and arbitragem branches |
| `backend/tests/test_engine_bess.py` | MODIFY | Rewrite backup tests; add arbitrage economy tests |

---

## Task 1 — DB migration: add `max_baterias` to products_bess

**Files:**
- Create: `backend/migrations/002_add_max_baterias.sql`
- Modify: `backend/app/catalog/models.py`
- Modify: `backend/app/catalog/schemas.py`

- [ ] **Step 1: Create migration file**

```sql
-- backend/migrations/002_add_max_baterias.sql
ALTER TABLE products_bess
  ADD COLUMN IF NOT EXISTS max_baterias INTEGER;

COMMENT ON COLUMN products_bess.max_baterias
  IS 'Para inversores: quantidade máxima de baterias suportada por unidade de inversor (conforme datasheet do fabricante)';
```

- [ ] **Step 2: Add column to ORM model**

In `backend/app/catalog/models.py`, add the import for `Integer` and the new column after `potencia_continua_kw`:

```python
# At top-level imports, add Integer:
from sqlalchemy import Boolean, DateTime, Integer, Numeric, Text

# Inside class ProductBESS, after potencia_continua_kw line:
    max_baterias: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

- [ ] **Step 3: Add field to Pydantic schemas**

In `backend/app/catalog/schemas.py`, add to `ProductBESSCreate` after `potencia_continua_kw`:

```python
    max_baterias: Optional[int] = None
```

- [ ] **Step 4: Apply migration in Supabase**

Copy the contents of `002_add_max_baterias.sql` and run it in Supabase → SQL Editor.
Expected: "ALTER TABLE" success message.

- [ ] **Step 5: Commit**

```bash
git add backend/migrations/002_add_max_baterias.sql \
        backend/app/catalog/models.py \
        backend/app/catalog/schemas.py
git commit -m "feat(catalog): add max_baterias column to products_bess for inverters"
```

---

## Task 2 — Update engine schemas

**Files:**
- Modify: `backend/app/engines/schemas.py`

- [ ] **Step 1: Replace `BackupInput` and `BackupResult`**

Replace the `BackupInput` and `BackupResult` classes in `backend/app/engines/schemas.py`:

```python
class CargaItem:
    """Uma carga crítica com potência (kW) e tempo de uso diário (h/dia)."""
    def __init__(self, potencia_kw: float, tdia_horas: float):
        self.potencia_kw = potencia_kw
        self.tdia_horas = tdia_horas


class BackupInput:
    def __init__(
        self,
        cargas: list,             # list[CargaItem]
        autonomia_horas: float,   # duração do backup desejada (h)
        dod_percent: float,       # ex: 80 → usado como 0.80
        tensao_instalacao_v: float,
    ):
        self.cargas = cargas
        self.autonomia_horas = autonomia_horas
        self.dod_percent = dod_percent
        self.tensao_instalacao_v = tensao_instalacao_v


class BackupResult:
    def __init__(self, capacidade_kwh: float, energia_necessaria_kwh: float):
        # capacidade_kwh     = Σ(Pp_i × TDIA_i)
        # energia_necessaria = capacidade × (autonomia/24) / DoD / 0.9
        self.capacidade_kwh = capacidade_kwh
        self.energia_necessaria_kwh = energia_necessaria_kwh
```

- [ ] **Step 2: Replace `ArbitrageInput` and add `ArbitrageKitEconomy`**

Replace `ArbitrageInput` and `ArbitrageResult` in `backend/app/engines/schemas.py`:

```python
class ArbitrageInput:
    def __init__(
        self,
        modalidade: str,                          # "verde" ou "azul"
        tarifa_ponta_kwh: float,                  # R$/kWh
        tarifa_fora_ponta_kwh: float,             # R$/kWh
        demanda_medida_ponta_kw: float,           # kW medido hoje na ponta
        demanda_medida_fora_ponta_kw: float,
        demanda_contratada_ponta_kw: float,
        demanda_contratada_fora_ponta_kw: float,
        tarifa_demanda_ponta_kw,                  # R$/kW (Azul) ou None
        tarifa_demanda_fora_ponta_kw,             # R$/kW (Azul) ou None
        tarifa_demanda_unica_kw,                  # R$/kW (Verde) ou None
        dod_percent: float,
        tensao_instalacao_v: float,
    ):
        self.modalidade = modalidade.lower()
        self.tarifa_ponta_kwh = tarifa_ponta_kwh
        self.tarifa_fora_ponta_kwh = tarifa_fora_ponta_kwh
        self.demanda_medida_ponta_kw = demanda_medida_ponta_kw
        self.demanda_medida_fora_ponta_kw = demanda_medida_fora_ponta_kw
        self.demanda_contratada_ponta_kw = demanda_contratada_ponta_kw
        self.demanda_contratada_fora_ponta_kw = demanda_contratada_fora_ponta_kw
        self.tarifa_demanda_ponta_kw = tarifa_demanda_ponta_kw
        self.tarifa_demanda_fora_ponta_kw = tarifa_demanda_fora_ponta_kw
        self.tarifa_demanda_unica_kw = tarifa_demanda_unica_kw
        self.dod_percent = dod_percent
        self.tensao_instalacao_v = tensao_instalacao_v


class ArbitrageKitEconomy:
    """Resultado econômico para uma combinação específica (bateria, n_baterias)."""
    def __init__(
        self,
        energia_arbitrada_dia_kwh: float,
        potencia_descarga_kw: float,
        economia_energia_mensal: float,
        economia_demanda_mensal: float,
        economia_total_mensal: float,
    ):
        self.energia_arbitrada_dia_kwh = energia_arbitrada_dia_kwh
        self.potencia_descarga_kw = potencia_descarga_kw
        self.economia_energia_mensal = economia_energia_mensal
        self.economia_demanda_mensal = economia_demanda_mensal
        self.economia_total_mensal = economia_total_mensal
```

Also remove the old `ArbitrageResult` class (no longer used).

- [ ] **Step 3: Add `max_baterias` to `ProductBESSRead` in engines/schemas.py**

Inside the `ProductBESSRead.__init__` signature, add `max_baterias=None`:

```python
class ProductBESSRead:
    def __init__(self, id=None, marca=None, modelo=None, sku=None, tipo=None,
                 tensao_nominal_v=None, capacidade_kwh=None, dod_percent=None,
                 corrente_max_descarga_a=None, tensao_min_dc_v=None,
                 tensao_max_dc_v=None, corrente_max_dc_a=None,
                 potencia_continua_kw=None, max_baterias=None,
                 preco=0.0, disponivel=True, atualizado_em=None):
        # ... existing assignments ...
        self.max_baterias = max_baterias
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/engines/schemas.py
git commit -m "feat(engines): update BackupInput/Result and ArbitrageInput schemas per new spec"
```

---

## Task 3 — Rewrite backup engine function

**Files:**
- Modify: `backend/app/engines/bess.py`
- Test: `backend/tests/test_engine_bess.py`

- [ ] **Step 1: Write the failing tests for new backup formula**

Replace the `TestBackup` class in `backend/tests/test_engine_bess.py`:

```python
from app.engines.schemas import (
    BackupInput, CargaItem,
    ArbitrageInput, ArbitrageKitEconomy,
)
from app.engines.bess import calculate_backup, calculate_arbitrage_economy

class TestBackup(unittest.TestCase):

    def test_single_load_capacidade(self):
        """1 carga 5 kW × 4 h/dia → Capacidade = 20 kWh"""
        inp = BackupInput(
            cargas=[CargaItem(potencia_kw=5.0, tdia_horas=4.0)],
            autonomia_horas=12.0,
            dod_percent=80.0,
            tensao_instalacao_v=220.0,
        )
        result = calculate_backup(inp)
        self.assertAlmostEqual(result.capacidade_kwh, 20.0, places=2)

    def test_single_load_energia_necessaria(self):
        """Energia = 20 × (12/24) / 0.8 / 0.9 ≈ 13.89 kWh"""
        inp = BackupInput(
            cargas=[CargaItem(potencia_kw=5.0, tdia_horas=4.0)],
            autonomia_horas=12.0,
            dod_percent=80.0,
            tensao_instalacao_v=220.0,
        )
        result = calculate_backup(inp)
        expected = 20.0 * (12.0 / 24.0) / 0.80 / 0.9
        self.assertAlmostEqual(result.energia_necessaria_kwh, expected, places=2)

    def test_multi_load_sum(self):
        """2 cargas: 3 kW×2 h + 2 kW×6 h = 6 + 12 = 18 kWh capacidade"""
        inp = BackupInput(
            cargas=[
                CargaItem(potencia_kw=3.0, tdia_horas=2.0),
                CargaItem(potencia_kw=2.0, tdia_horas=6.0),
            ],
            autonomia_horas=24.0,
            dod_percent=100.0,
            tensao_instalacao_v=220.0,
        )
        result = calculate_backup(inp)
        self.assertAlmostEqual(result.capacidade_kwh, 18.0, places=2)

    def test_dod_100_energia_equals_capacidade_over_efficiency(self):
        """DoD 100%, autonomia 24h → Energia = Capacidade / 0.9"""
        inp = BackupInput(
            cargas=[CargaItem(potencia_kw=10.0, tdia_horas=3.0)],
            autonomia_horas=24.0,
            dod_percent=100.0,
            tensao_instalacao_v=220.0,
        )
        result = calculate_backup(inp)
        self.assertAlmostEqual(result.energia_necessaria_kwh, 30.0 / 0.9, places=2)

    def test_zero_dod_raises(self):
        with self.assertRaises(ValueError):
            calculate_backup(BackupInput(
                cargas=[CargaItem(potencia_kw=5.0, tdia_horas=4.0)],
                autonomia_horas=4.0,
                dod_percent=0.0,
                tensao_instalacao_v=220.0,
            ))

    def test_empty_cargas_raises(self):
        with self.assertRaises(ValueError):
            calculate_backup(BackupInput(
                cargas=[],
                autonomia_horas=4.0,
                dod_percent=80.0,
                tensao_instalacao_v=220.0,
            ))
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_engine_bess.py::TestBackup -v 2>&1 | head -30
```

Expected: `FAILED` or `ImportError` (functions don't exist yet with new signature).

- [ ] **Step 3: Rewrite `calculate_backup` in `bess.py`**

Replace the `calculate_backup` function in `backend/app/engines/bess.py`:

```python
from app.engines.schemas import (
    ArbitrageInput, ArbitrageKitEconomy,
    BackupInput, BackupResult,
    PeakShavingInput, PeakShavingResult,
)

_EFICIENCIA_SISTEMA = 0.9   # round-trip + inversor
_HORAS_PONTA = 3.0          # 18h–21h
_DIAS_UTEIS_MES = 22


def calculate_backup(data: BackupInput) -> BackupResult:
    """
    Capacidade (kWh)      = Σ(Pp_i × TDIA_i)
    Energia Necessária    = Capacidade × (Autonomia / 24) / DoD / 0.9
    """
    if data.dod_percent <= 0:
        raise ValueError("dod_percent deve ser maior que zero")
    if not data.cargas:
        raise ValueError("cargas não pode ser vazia")

    dod = data.dod_percent / 100.0
    capacidade_kwh = sum(c.potencia_kw * c.tdia_horas for c in data.cargas)
    energia_necessaria_kwh = (
        capacidade_kwh * (data.autonomia_horas / 24.0) / dod / _EFICIENCIA_SISTEMA
    )

    return BackupResult(
        capacidade_kwh=round(capacidade_kwh, 2),
        energia_necessaria_kwh=round(energia_necessaria_kwh, 2),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_engine_bess.py::TestBackup -v
```

Expected: all 6 tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/engines/bess.py backend/tests/test_engine_bess.py
git commit -m "feat(engines): rewrite calculate_backup with correct multi-load formula"
```

---

## Task 4 — Add `calculate_arbitrage_economy` to bess.py

**Files:**
- Modify: `backend/app/engines/bess.py`
- Test: `backend/tests/test_engine_bess.py`

- [ ] **Step 1: Write the failing tests**

Add `TestArbitrageEconomy` class to `backend/tests/test_engine_bess.py`:

```python
class TestArbitrageEconomy(unittest.TestCase):

    def _azul_input(self):
        return ArbitrageInput(
            modalidade="azul",
            tarifa_ponta_kwh=0.90,
            tarifa_fora_ponta_kwh=0.30,
            demanda_medida_ponta_kw=50.0,
            demanda_medida_fora_ponta_kw=30.0,
            demanda_contratada_ponta_kw=60.0,
            demanda_contratada_fora_ponta_kw=40.0,
            tarifa_demanda_ponta_kw=45.0,
            tarifa_demanda_fora_ponta_kw=15.0,
            tarifa_demanda_unica_kw=None,
            dod_percent=80.0,
            tensao_instalacao_v=220.0,
        )

    def test_energia_arbitrada(self):
        """2 baterias × 10 kWh × 0.80 DoD = 16 kWh/dia"""
        eco = calculate_arbitrage_economy(self._azul_input(), n_baterias=2, cap_bateria_kwh=10.0)
        self.assertAlmostEqual(eco.energia_arbitrada_dia_kwh, 16.0, places=2)

    def test_potencia_descarga(self):
        """16 kWh / 3h = 5.33 kW"""
        eco = calculate_arbitrage_economy(self._azul_input(), n_baterias=2, cap_bateria_kwh=10.0)
        self.assertAlmostEqual(eco.potencia_descarga_kw, 16.0 / 3.0, places=2)

    def test_economia_energia_mensal(self):
        """16 kWh × (0.90 - 0.30) × 22 dias = 211.20 R$/mês"""
        eco = calculate_arbitrage_economy(self._azul_input(), n_baterias=2, cap_bateria_kwh=10.0)
        self.assertAlmostEqual(eco.economia_energia_mensal, 16.0 * 0.60 * 22, places=1)

    def test_economia_demanda_azul(self):
        """Redução = min(16/3, 50) = 5.33 kW; economia = 5.33 × 45 ≈ 240 R$"""
        eco = calculate_arbitrage_economy(self._azul_input(), n_baterias=2, cap_bateria_kwh=10.0)
        expected = min(16.0 / 3.0, 50.0) * 45.0
        self.assertAlmostEqual(eco.economia_demanda_mensal, expected, places=1)

    def test_economia_demanda_verde_zero(self):
        """Tarifa Verde: economia de demanda = 0"""
        verde = ArbitrageInput(
            modalidade="verde",
            tarifa_ponta_kwh=0.90,
            tarifa_fora_ponta_kwh=0.30,
            demanda_medida_ponta_kw=50.0,
            demanda_medida_fora_ponta_kw=30.0,
            demanda_contratada_ponta_kw=60.0,
            demanda_contratada_fora_ponta_kw=40.0,
            tarifa_demanda_ponta_kw=None,
            tarifa_demanda_fora_ponta_kw=None,
            tarifa_demanda_unica_kw=35.0,
            dod_percent=80.0,
            tensao_instalacao_v=220.0,
        )
        eco = calculate_arbitrage_economy(verde, n_baterias=2, cap_bateria_kwh=10.0)
        self.assertEqual(eco.economia_demanda_mensal, 0.0)

    def test_economia_total_is_sum(self):
        eco = calculate_arbitrage_economy(self._azul_input(), n_baterias=2, cap_bateria_kwh=10.0)
        self.assertAlmostEqual(
            eco.economia_total_mensal,
            eco.economia_energia_mensal + eco.economia_demanda_mensal,
            places=2,
        )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_engine_bess.py::TestArbitrageEconomy -v 2>&1 | head -20
```

Expected: `ImportError` or `AttributeError` (function doesn't exist yet).

- [ ] **Step 3: Add `calculate_arbitrage_economy` to `bess.py`**

Add this function after `calculate_backup` in `backend/app/engines/bess.py` (remove the old `calculate_arbitrage`):

```python
def calculate_arbitrage_economy(
    data: ArbitrageInput,
    n_baterias: int,
    cap_bateria_kwh: float,
) -> ArbitrageKitEconomy:
    """
    Calcula economia mensal para uma combinação específica de baterias.
    Parâmetros fixos: ponta = 18h–21h (3h), 22 dias úteis/mês.

    Args:
        data:           Dados tarifários e de demanda do cliente.
        n_baterias:     Quantidade de baterias nesta combinação.
        cap_bateria_kwh: Capacidade nominal de cada bateria (kWh, sem DoD).
    """
    dod = data.dod_percent / 100.0
    energia_arbitrada_dia = n_baterias * cap_bateria_kwh * dod
    potencia_descarga_kw = energia_arbitrada_dia / _HORAS_PONTA

    economia_energia = (
        energia_arbitrada_dia
        * (data.tarifa_ponta_kwh - data.tarifa_fora_ponta_kwh)
        * _DIAS_UTEIS_MES
    )

    economia_demanda = 0.0
    if data.modalidade == "azul" and data.tarifa_demanda_ponta_kw:
        reducao_demanda = min(potencia_descarga_kw, data.demanda_medida_ponta_kw)
        economia_demanda = reducao_demanda * data.tarifa_demanda_ponta_kw

    return ArbitrageKitEconomy(
        energia_arbitrada_dia_kwh=round(energia_arbitrada_dia, 2),
        potencia_descarga_kw=round(potencia_descarga_kw, 2),
        economia_energia_mensal=round(economia_energia, 2),
        economia_demanda_mensal=round(economia_demanda, 2),
        economia_total_mensal=round(economia_energia + economia_demanda, 2),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_engine_bess.py::TestArbitrageEconomy -v
```

Expected: all 6 tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/engines/bess.py backend/tests/test_engine_bess.py
git commit -m "feat(engines): add calculate_arbitrage_economy with tariff-based formula"
```

---

## Task 5 — Update compatibility.py: max_baterias + find_arbitrage_kits

**Files:**
- Modify: `backend/app/engines/compatibility.py`
- Test: `backend/tests/test_engine_compatibility.py`

- [ ] **Step 1: Add `qtd_inversores` and `economia_mensal` to `KitBESS` dataclass**

In `backend/app/engines/compatibility.py`, update the `KitBESS` dataclass:

```python
from typing import Optional

@dataclass
class KitBESS:
    bateria: ProductBESSRead
    inversor: ProductBESSRead
    qtd_baterias_serie: int
    qtd_strings_paralelo: int
    qtd_baterias_total: int
    qtd_inversores: int                    # NEW
    capacidade_total_kwh: float
    potencia_total_kw: float
    preco_total: float
    economia_mensal: Optional[float] = None   # NEW — usado na arbitragem
    payback_anos: Optional[float] = None      # NEW — usado na arbitragem
```

- [ ] **Step 2: Apply `max_baterias` constraint in `find_compatible_kits` + set `qtd_inversores`**

After `qtd_baterias_total = qtd_serie * strings_necessarias` in `find_compatible_kits`, add:

```python
            # Verificar limite do catálogo: max_baterias por inversor
            max_bat = getattr(inv, 'max_baterias', None)
            if max_bat is not None and max_bat > 0:
                n_inv = math.ceil(qtd_baterias_total / max_bat)
            else:
                n_inv = 1   # sem restrição de catálogo: 1 inversor

            if n_inv > 4:
                continue    # precisaria de mais de 4 inversores — inviável
```

And update the `preco_total` line and the `kits.append(...)` call:

```python
            preco_total = bat.preco * qtd_baterias_total + inv.preco * n_inv

            kits.append(KitBESS(
                bateria=bat,
                inversor=inv,
                qtd_baterias_serie=qtd_serie,
                qtd_strings_paralelo=strings_necessarias,
                qtd_baterias_total=qtd_baterias_total,
                qtd_inversores=n_inv,          # NEW
                capacidade_total_kwh=round(capacidade_total_kwh, 2),
                potencia_total_kw=round(potencia_total_kw, 2),
                preco_total=round(preco_total, 2),
            ))
```

- [ ] **Step 3: Add `find_arbitrage_kits` function**

Append the following function to `backend/app/engines/compatibility.py`:

```python
def find_arbitrage_kits(
    baterias: list,
    inversores: list,
    data,           # ArbitrageInput
) -> list[KitBESS]:
    """
    Para cada par (bateria, inversor) de mesma marca, itera de 1 até
    max_baterias × 4 unidades (até 4 inversores em paralelo) e calcula
    economia + payback para cada quantidade.
    Retorna todos os kits válidos (economia > 0) ordenados por payback crescente.
    """
    from app.engines.bess import calculate_arbitrage_economy

    kits: list[KitBESS] = []

    for bat in baterias:
        if not bat.capacidade_kwh or not bat.preco:
            continue

        for inv in inversores:
            if bat.marca != inv.marca:
                continue
            if not inv.preco:
                continue

            max_bat_inv = getattr(inv, 'max_baterias', None) or 8  # default conservador
            max_total = max_bat_inv * 4  # até 4 inversores

            for n_baterias in range(1, max_total + 1):
                n_inv = math.ceil(n_baterias / max_bat_inv)
                if n_inv > 4:
                    break

                eco = calculate_arbitrage_economy(data, n_baterias, float(bat.capacidade_kwh))

                if eco.economia_total_mensal <= 0:
                    continue

                custo_kit = float(bat.preco) * n_baterias + float(inv.preco) * n_inv
                payback_anos = custo_kit / (eco.economia_total_mensal * 12)
                cap_total = n_baterias * float(bat.capacidade_kwh) * (data.dod_percent / 100.0)
                pot_total = (float(inv.potencia_continua_kw) * n_inv
                             if inv.potencia_continua_kw else 0.0)

                kits.append(KitBESS(
                    bateria=bat,
                    inversor=inv,
                    qtd_baterias_serie=1,
                    qtd_strings_paralelo=n_baterias,
                    qtd_baterias_total=n_baterias,
                    qtd_inversores=n_inv,
                    capacidade_total_kwh=round(cap_total, 2),
                    potencia_total_kw=round(pot_total, 2),
                    preco_total=round(custo_kit, 2),
                    economia_mensal=eco.economia_total_mensal,
                    payback_anos=round(payback_anos, 2),
                ))

    kits.sort(key=lambda k: k.payback_anos if k.payback_anos is not None else float('inf'))
    return kits
```

- [ ] **Step 4: Run the full test suite to check no regression**

```bash
cd backend && python -m pytest tests/ -v 2>&1 | tail -20
```

Expected: `test_engine_compatibility.py` tests still pass. Backup tests pass. Ignore failures in `test_engine_bess.py::TestArbitrage` (old class being removed next step).

- [ ] **Step 5: Remove old `TestArbitrage` from test file**

In `backend/tests/test_engine_bess.py`, delete the old `TestArbitrage` class entirely (it tested the old `calculate_arbitrage` which has been removed).

- [ ] **Step 6: Commit**

```bash
git add backend/app/engines/compatibility.py backend/tests/test_engine_bess.py
git commit -m "feat(engines): add max_baterias constraint to backup finder; add find_arbitrage_kits"
```

---

## Task 6 — Update calculate/schemas.py

**Files:**
- Modify: `backend/app/calculate/schemas.py`

- [ ] **Step 1: Add new fields to `CalculateRequest`**

In `backend/app/calculate/schemas.py`, add to `CalculateRequest` after the existing `tarifa_fora_ponta_rs_kwh` field:

```python
    # Backup — DoD informado pelo engenheiro (antes era lido do catálogo)
    dod_percent: Optional[float] = None

    # Arbitragem Tarifária — tarifas e demandas
    modalidade_tarifaria: Optional[Literal["verde", "azul"]] = None
    demanda_medida_ponta_kw: Optional[float] = None
    demanda_medida_fora_ponta_kw: Optional[float] = None
    demanda_contratada_ponta_kw: Optional[float] = None
    demanda_contratada_fora_ponta_kw: Optional[float] = None
    tarifa_demanda_ponta_rs_kw: Optional[float] = None
    tarifa_demanda_fora_ponta_rs_kw: Optional[float] = None
    tarifa_demanda_unica_rs_kw: Optional[float] = None
```

- [ ] **Step 2: Update `KitInfo`**

Replace the existing `KitInfo` class:

```python
class KitInfo(BaseModel):
    marca: str
    bateria_modelo: str
    inversor_modelo: str
    qtd_baterias: int
    qtd_inversores: int = 1
    capacidade_total_kwh: float
    potencia_total_kw: float
    preco_total: float
    economia_mensal_rs: Optional[float] = None    # valor econômico (arbitragem)
    payback_anos: Optional[float] = None          # payback em anos (arbitragem)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/calculate/schemas.py
git commit -m "feat(calculate): add dod_percent, arbitragem fields to CalculateRequest; update KitInfo"
```

---

## Task 7 — Rewrite calculate/service.py branches

**Files:**
- Modify: `backend/app/calculate/service.py`

- [ ] **Step 1: Update imports at the top of service.py**

```python
from app.engines.bess import calculate_backup, calculate_peak_shaving, calculate_arbitrage_economy
from app.engines.compatibility import find_compatible_kits, find_arbitrage_kits
from app.engines.schemas import (
    BackupInput, CargaItem,
    ArbitrageInput,
    PeakShavingInput, SolarInput,
    BackupResult, PeakShavingResult, SolarResult,
)
```

- [ ] **Step 2: Update `_kits_to_response` helper to pass new KitInfo fields**

Replace `_kits_to_response` in `service.py`:

```python
def _kits_to_response(kits) -> tuple[KitInfo | None, list[KitInfo]]:
    if not kits:
        return None, []
    kit_info_list = [
        KitInfo(
            marca=k.bateria.marca,
            bateria_modelo=k.bateria.modelo,
            inversor_modelo=k.inversor.modelo,
            qtd_baterias=k.qtd_baterias_total,
            qtd_inversores=k.qtd_inversores,
            capacidade_total_kwh=k.capacidade_total_kwh,
            potencia_total_kw=k.potencia_total_kw,
            preco_total=k.preco_total,
            economia_mensal_rs=k.economia_mensal,
            payback_anos=k.payback_anos,
        )
        for k in kits
    ]
    return kit_info_list[0], kit_info_list[1:]
```

- [ ] **Step 3: Rewrite the `backup` branch inside `run_calculation`**

Replace the `if req.tipo_calculo == "backup":` block:

```python
        if req.tipo_calculo == "backup":
            # Converter cargas do request → CargaItem para o engine
            cargas_engine = []
            if req.cargas:
                for c in req.cargas:
                    kw = (c.potencia_w * c.quantidade) / 1000.0
                    cargas_engine.append(CargaItem(potencia_kw=kw, tdia_horas=c.horas_uso_dia))
            elif req.potencia_critica_kw:
                # Modo legado / compatibilidade: campo único. TDIA assume-se = autonomia (h).
                cargas_engine.append(CargaItem(
                    potencia_kw=req.potencia_critica_kw,
                    tdia_horas=req.autonomia_horas or 4.0,
                ))

            dod = req.dod_percent or 80.0
            result: BackupResult = calculate_backup(BackupInput(
                cargas=cargas_engine,
                autonomia_horas=req.autonomia_horas or 4.0,
                dod_percent=dod,
                tensao_instalacao_v=req.tensao_instalacao_v or 220.0,
            ))
            capacidade_kwh = result.energia_necessaria_kwh    # energia que o kit deve armazenar
            potencia_kw = sum(c.potencia_kw for c in cargas_engine)
```

- [ ] **Step 4: Rewrite the `arbitragem` branch inside `run_calculation`**

Replace the `elif req.tipo_calculo == "arbitragem":` block:

```python
        elif req.tipo_calculo == "arbitragem":
            arb_input = ArbitrageInput(
                modalidade=req.modalidade_tarifaria or "verde",
                tarifa_ponta_kwh=req.tarifa_ponta_rs_kwh or 0.0,
                tarifa_fora_ponta_kwh=req.tarifa_fora_ponta_rs_kwh or 0.0,
                demanda_medida_ponta_kw=req.demanda_medida_ponta_kw or 0.0,
                demanda_medida_fora_ponta_kw=req.demanda_medida_fora_ponta_kw or 0.0,
                demanda_contratada_ponta_kw=req.demanda_contratada_ponta_kw or 0.0,
                demanda_contratada_fora_ponta_kw=req.demanda_contratada_fora_ponta_kw or 0.0,
                tarifa_demanda_ponta_kw=req.tarifa_demanda_ponta_rs_kw,
                tarifa_demanda_fora_ponta_kw=req.tarifa_demanda_fora_ponta_rs_kw,
                tarifa_demanda_unica_kw=req.tarifa_demanda_unica_rs_kw,
                dod_percent=req.dod_percent or 80.0,
                tensao_instalacao_v=req.tensao_instalacao_v or 220.0,
            )

            # Kit finder específico para arbitragem (ordena por menor payback)
            kits = find_arbitrage_kits(
                baterias=baterias,
                inversores=inversores,
                data=arb_input,
            )

            kit_selecionado, alternativas = _kits_to_response(kits)

            if kits:
                capacidade_kwh = kits[0].capacidade_total_kwh
                potencia_kw = kits[0].potencia_total_kw
                economia_mensal = kits[0].economia_mensal
            else:
                capacidade_kwh = 0.0
                potencia_kw = 0.0
                economia_mensal = None

            # Pular o find_compatible_kits genérico abaixo para arbitragem
            payback_meses = round(kits[0].payback_anos * 12, 1) if kits and kits[0].payback_anos else None
```

- [ ] **Step 5: Gate the `find_compatible_kits` call to skip arbitragem**

Wrap the existing `kits = find_compatible_kits(...)` block so it only runs for non-arbitragem types. Before that line, add:

```python
        # Para arbitragem, kits já foram calculados acima; para demais tipos, usar finder genérico
        if req.tipo_calculo != "arbitragem":
            kits = find_compatible_kits(
                baterias=baterias,
                inversores=inversores,
                capacidade_necessaria_kwh=capacidade_kwh,
                potencia_necessaria_kw=potencia_kw,
            )
            kit_selecionado, alternativas = _kits_to_response(kits)
```

And update the payback calculation block to only run when `req.tipo_calculo != "arbitragem"`:

```python
        if req.tipo_calculo != "arbitragem":
            if kit_selecionado:
                if economia_mensal:
                    payback = kit_selecionado.preco_total / economia_mensal
                elif economia_anual:
                    payback = (kit_selecionado.preco_total / economia_anual) * 12
                else:
                    payback = None
            else:
                payback = None
            payback_meses = round(payback, 1) if payback else None
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/calculate/service.py
git commit -m "feat(service): rewrite backup and arbitragem branches with correct formulas"
```

---

## Task 8 — Verification: run full test suite

**Files:** none (read-only verification step)

- [ ] **Step 1: Run all backend tests**

```bash
cd backend && python -m pytest tests/ -v
```

Expected output (key lines):
```
tests/test_engine_bess.py::TestBackup::test_single_load_capacidade PASSED
tests/test_engine_bess.py::TestBackup::test_single_load_energia_necessaria PASSED
tests/test_engine_bess.py::TestBackup::test_multi_load_sum PASSED
tests/test_engine_bess.py::TestBackup::test_dod_100_energia_equals_capacidade_over_efficiency PASSED
tests/test_engine_bess.py::TestBackup::test_zero_dod_raises PASSED
tests/test_engine_bess.py::TestBackup::test_empty_cargas_raises PASSED
tests/test_engine_bess.py::TestArbitrageEconomy::test_energia_arbitrada PASSED
tests/test_engine_bess.py::TestArbitrageEconomy::test_potencia_descarga PASSED
tests/test_engine_bess.py::TestArbitrageEconomy::test_economia_energia_mensal PASSED
tests/test_engine_bess.py::TestArbitrageEconomy::test_economia_demanda_azul PASSED
tests/test_engine_bess.py::TestArbitrageEconomy::test_economia_demanda_verde_zero PASSED
tests/test_engine_bess.py::TestArbitrageEconomy::test_economia_total_is_sum PASSED
tests/test_engine_compatibility.py:: ... PASSED (existing tests unchanged)
```

- [ ] **Step 2: Fix any failures before continuing**

If any test fails, debug before proceeding. Do not skip.

- [ ] **Step 3: Final commit**

```bash
git add -u
git commit -m "test: all backup and arbitrage engine tests passing"
git push origin main
```

---

## Notes for developer

**`list_bess` returns ORM model instances** (`catalog.models.ProductBESS`), not Pydantic objects. `compatibility.py` uses attribute access (`.marca`, `.max_baterias`, etc.) which works correctly with ORM models via duck typing.

**Old `calculate_arbitrage` function** (load-curve based) is removed from `bess.py`. If `test_calculate_unit.py` calls it, update those tests too.

**Migration must be run in Supabase** before deploying to Railway. Railway reads from Supabase PostgreSQL — the column must exist before the app starts.

**DoD source change for Backup:** previously read from the first battery in the catalog (`baterias[0].dod_percent`). Now it comes from the API request (`req.dod_percent`). Default: 80% if not provided.
