# backup_direto Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar `tipo_calculo: "backup_direto"` ao endpoint `POST /calculate` para que o Ploomes envie apenas `total_pp_kva` e `total_e_eps_kwh` pré-calculados, recebendo o kit BESS recomendado sem precisar enviar dados brutos de equipamentos.

**Architecture:** Um novo bloco `elif` no `run_calculation` do service detecta `backup_direto`, valida os dois campos obrigatórios e chama `find_compatible_kits` diretamente — sem calcular a tabela de cargas. Schema recebe dois campos `Optional[float]` novos e um novo literal. Response shape é idêntico ao `backup` normal.

**Tech Stack:** FastAPI · Pydantic v2 · pytest · unittest.mock (AsyncMock)

---

## Mapa de arquivos

| Arquivo | Ação | O que muda |
|---------|------|-----------|
| `backend/app/calculate/schemas.py` | Modificar | Adiciona `"backup_direto"` ao Literal; adiciona `total_pp_kva` e `total_e_eps_kwh` |
| `backend/app/calculate/service.py` | Modificar | Adiciona bloco `elif req.tipo_calculo == "backup_direto":` |
| `backend/tests/test_calculate_unit.py` | Modificar | Adiciona testes de schema + validação do novo tipo |
| `docs/api-ploomes.md` | Modificar | Adiciona seção Tipo 1b — Backup Direto |

---

## Task 1: Testes de schema (TDD — escrever antes da implementação)

**Files:**
- Modify: `backend/tests/test_calculate_unit.py`

- [ ] **Step 1: Adicionar imports necessários no topo do arquivo de testes**

Abrir `backend/tests/test_calculate_unit.py` e garantir que os imports incluam:

```python
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.calculate.schemas import CalculateRequest, CalculateResponse, KitInfo, LoadItem, OrigemInfo
from app.calculate.service import _build_load_curve, _kits_to_response
from app.engines.compatibility import KitBESS
from app.catalog.schemas import ProductBESSRead
import uuid
from datetime import datetime, timezone
import pytest
```

- [ ] **Step 2: Adicionar helper `_make_origem_info` e os testes de schema ao final do arquivo**

```python
# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_origem_info(**kwargs):
    defaults = dict(
        origem="ploomes",
        negocio_id="123",
        negocio_nome="Empresa Teste",
        solicitante_id="user-1",
        solicitante_nome="João",
        solicitado_em=datetime.now(timezone.utc),
    )
    return OrigemInfo(**{**defaults, **kwargs})


# ── backup_direto schema ───────────────────────────────────────────────────────

def test_backup_direto_schema_accepts_new_tipo():
    """tipo_calculo='backup_direto' deve ser aceito pelo schema."""
    req = CalculateRequest(
        origem_info=_make_origem_info(),
        tipo_calculo="backup_direto",
        tipo_instalacao="monofasico",
        total_pp_kva=28.8,
        total_e_eps_kwh=4.8,
    )
    assert req.tipo_calculo == "backup_direto"
    assert req.total_pp_kva == 28.8
    assert req.total_e_eps_kwh == 4.8


def test_backup_direto_schema_fields_optional_by_default():
    """total_pp_kva e total_e_eps_kwh são None quando não fornecidos."""
    req = CalculateRequest(
        origem_info=_make_origem_info(),
        tipo_calculo="backup",
    )
    assert req.total_pp_kva is None
    assert req.total_e_eps_kwh is None


def test_backup_direto_schema_rejects_unknown_tipo():
    """tipo_calculo inválido deve lançar ValidationError."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        CalculateRequest(
            origem_info=_make_origem_info(),
            tipo_calculo="tipo_inexistente",
        )
```

- [ ] **Step 3: Rodar os testes — esperar FALHA**

```
cd backend
python -m pytest tests/test_calculate_unit.py::test_backup_direto_schema_accepts_new_tipo -v
```

Saída esperada: `FAILED` com `ValidationError` porque `"backup_direto"` ainda não está no Literal.

---

## Task 2: Atualizar schema — `backup_direto` + novos campos

**Files:**
- Modify: `backend/app/calculate/schemas.py`

- [ ] **Step 1: Adicionar `"backup_direto"` ao Literal de `tipo_calculo`**

Localizar a linha:
```python
tipo_calculo: Literal["backup", "peak_shaving", "arbitragem", "solar", "solar_storage"]
```

Substituir por:
```python
tipo_calculo: Literal["backup", "backup_direto", "peak_shaving", "arbitragem", "solar", "solar_storage"]
```

- [ ] **Step 2: Adicionar os dois novos campos opcionais a `CalculateRequest`**

Dentro de `CalculateRequest`, após o bloco `# ── Backup ───`:

```python
    # ── Backup Direto (totais pré-calculados pelo Ploomes) ────────────────────
    total_pp_kva:    Optional[float] = None  # Potência de pico total (kVA)
    total_e_eps_kwh: Optional[float] = None  # Energia necessária já escalada (kWh)
```

- [ ] **Step 3: Rodar os testes de schema — esperar PASS**

```
cd backend
python -m pytest tests/test_calculate_unit.py -v
```

Saída esperada: todos os testes passando, incluindo os 3 novos.

- [ ] **Step 4: Commit**

```bash
git add backend/app/calculate/schemas.py backend/tests/test_calculate_unit.py
git commit -m "feat(schema): add backup_direto tipo_calculo and total_pp/e_eps fields"
```

---

## Task 3: Testes de validação do service (TDD — escrever antes da implementação)

**Files:**
- Modify: `backend/tests/test_calculate_unit.py`

- [ ] **Step 1: Adicionar imports de mock no topo do arquivo de testes**

```python
from unittest.mock import AsyncMock, MagicMock, patch
```

- [ ] **Step 2: Adicionar testes de validação do service ao final do arquivo**

```python
# ── backup_direto service validation ──────────────────────────────────────────

import asyncio

def _run(coro):
    """Helper para rodar coroutines em testes síncronos."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_backup_direto_req(**kwargs):
    defaults = dict(
        origem_info=_make_origem_info(),
        tipo_calculo="backup_direto",
        tipo_instalacao="monofasico",
        total_pp_kva=28.8,
        total_e_eps_kwh=4.8,
    )
    return CalculateRequest(**{**defaults, **kwargs})


def _mock_db_and_catalog(mock_project=None):
    """Retorna (db_mock, patches) para usar em testes de service."""
    if mock_project is None:
        mock_project = MagicMock()
        mock_project.parametros = {}
        mock_project.id = uuid.uuid4()

    db = AsyncMock()
    patches = [
        patch("app.calculate.service.create_project", new=AsyncMock(return_value=mock_project)),
        patch("app.calculate.service.mark_project_done", new=AsyncMock()),
        patch("app.calculate.service.mark_project_error", new=AsyncMock()),
        patch("app.calculate.service.list_bess", new=AsyncMock(return_value=[])),
        patch("app.calculate.service.list_solar", new=AsyncMock(return_value=[])),
    ]
    return db, patches


def test_backup_direto_missing_total_pp_kva_raises():
    """Sem total_pp_kva deve levantar ValueError."""
    from app.calculate.service import run_calculation

    req = _make_backup_direto_req(total_pp_kva=None)
    db, patches = _mock_db_and_catalog()

    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        with pytest.raises(ValueError, match="total_pp_kva"):
            _run(run_calculation(db, req))


def test_backup_direto_missing_total_e_eps_kwh_raises():
    """Sem total_e_eps_kwh deve levantar ValueError."""
    from app.calculate.service import run_calculation

    req = _make_backup_direto_req(total_e_eps_kwh=None)
    db, patches = _mock_db_and_catalog()

    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        with pytest.raises(ValueError, match="total_e_eps_kwh"):
            _run(run_calculation(db, req))


def test_backup_direto_zero_e_eps_raises():
    """total_e_eps_kwh=0 deve levantar ValueError."""
    from app.calculate.service import run_calculation

    req = _make_backup_direto_req(total_e_eps_kwh=0.0)
    db, patches = _mock_db_and_catalog()

    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        with pytest.raises(ValueError, match="maior que zero"):
            _run(run_calculation(db, req))


def test_backup_direto_valid_returns_response():
    """Com totais válidos e catálogo vazio deve retornar kit_selecionado=None sem erro."""
    from app.calculate.service import run_calculation
    from app.calculate.schemas import CalculateResponse

    req = _make_backup_direto_req()
    db, patches = _mock_db_and_catalog()

    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        result = _run(run_calculation(db, req))

    assert isinstance(result, CalculateResponse)
    assert result.tipo_calculo == "backup_direto"
    assert result.capacidade_kwh == 4.8
    assert result.potencia_kw == 28.8
    assert result.kit_selecionado is None   # catálogo vazio → sem kit
    assert result.backup_rows is None


def test_existing_backup_tipo_still_works():
    """tipo_calculo='backup' continua validando e roteando corretamente."""
    req = CalculateRequest(
        origem_info=_make_origem_info(),
        tipo_calculo="backup",
        tipo_instalacao="monofasico",
        cargas_backup=[],
    )
    assert req.tipo_calculo == "backup"
    assert req.total_pp_kva is None
```

- [ ] **Step 3: Rodar os testes de service — esperar FALHA**

```
cd backend
python -m pytest tests/test_calculate_unit.py::test_backup_direto_missing_total_pp_kva_raises -v
```

Saída esperada: `FAILED` com `KeyError` ou similar — o bloco `backup_direto` ainda não existe no service.

---

## Task 4: Implementar o bloco `backup_direto` no service

**Files:**
- Modify: `backend/app/calculate/service.py`

- [ ] **Step 1: Localizar o fim do bloco `backup` no service**

Abrir `backend/app/calculate/service.py`. Encontrar a linha:

```python
        elif req.tipo_calculo == "peak_shaving":
```

Inserir o novo bloco ANTES dessa linha:

```python
        elif req.tipo_calculo == "backup_direto":
            if req.total_pp_kva is None or req.total_e_eps_kwh is None:
                raise ValueError(
                    "total_pp_kva e total_e_eps_kwh são obrigatórios para backup_direto"
                )
            if req.total_e_eps_kwh <= 0:
                raise ValueError("total_e_eps_kwh deve ser maior que zero")

            capacidade_kwh = req.total_e_eps_kwh
            potencia_kw    = req.total_pp_kva

            kits = find_compatible_kits(
                baterias=baterias,
                inversores=inversores,
                total_pp_kva=req.total_pp_kva,
                total_e_eps_kwh=req.total_e_eps_kwh,
                tipo_instalacao=req.tipo_instalacao or "monofasico",
            )
            kit_selecionado, alternativas = _kits_to_response(kits)

```

- [ ] **Step 2: Rodar todos os testes — esperar PASS**

```
cd backend
python -m pytest tests/test_calculate_unit.py tests/test_engine_compatibility.py -v
```

Saída esperada: todos os testes passando.

- [ ] **Step 3: Commit**

```bash
git add backend/app/calculate/service.py backend/tests/test_calculate_unit.py
git commit -m "feat(service): add backup_direto — accepts pre-calculated totals from Ploomes"
```

---

## Task 5: Atualizar documentação da API

**Files:**
- Modify: `docs/api-ploomes.md`

- [ ] **Step 1: Adicionar seção "Tipo 1b" após a seção "Tipo 1 — Backup de Energia"**

Abrir `docs/api-ploomes.md` e inserir a seção abaixo após o bloco de resposta do Tipo 1:

```markdown
---

## Tipo 1b — Backup Direto (uso Ploomes)

Use este tipo quando o Ploomes já possui os totais das cargas calculados. Não é necessário enviar a lista de equipamentos.

### Campos específicos

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `total_pp_kva` | float | ✅ | Potência de pico total das cargas (kVA) — soma das colunas Pp |
| `total_e_eps_kwh` | float | ✅ | Energia necessária já escalada pela autonomia (kWh) |
| `tipo_instalacao` | string | ❌ | `"monofasico"` (padrão) ou `"trifasico"` |

### Exemplo de requisição

```json
{
  "origem_info": {
    "origem": "ploomes",
    "negocio_id": "123456",
    "negocio_nome": "Padaria Central",
    "solicitante_id": "rep-001",
    "solicitante_nome": "Carlos Vendas",
    "solicitado_em": "2026-05-19T14:00:00Z"
  },
  "tipo_calculo": "backup_direto",
  "tipo_instalacao": "monofasico",
  "total_pp_kva": 28.8,
  "total_e_eps_kwh": 4.8
}
```

### Diferença em relação ao Tipo 1

| | `backup` | `backup_direto` |
|-|----------|-----------------|
| Envia equipamentos | ✅ `cargas_backup[]` | ❌ |
| Envia totais | ❌ | ✅ `total_pp_kva` + `total_e_eps_kwh` |
| `backup_rows` na resposta | ✅ detalhamento por linha | `null` |
| Kit recomendado | ✅ | ✅ |

### Erros específicos

| Situação | HTTP | Detalhe |
|----------|------|---------|
| `total_pp_kva` ausente | `500` | `"total_pp_kva e total_e_eps_kwh são obrigatórios para backup_direto"` |
| `total_e_eps_kwh` ausente | `500` | `"total_pp_kva e total_e_eps_kwh são obrigatórios para backup_direto"` |
| `total_e_eps_kwh = 0` | `500` | `"total_e_eps_kwh deve ser maior que zero"` |
```

- [ ] **Step 2: Commit**

```bash
git add docs/api-ploomes.md
git commit -m "docs: add backup_direto section to Ploomes API docs"
```

---

## Task 6: Push e PR

- [ ] **Step 1: Verificar que todos os testes passam**

```
cd backend
python -m pytest tests/ -v
```

Saída esperada: todos os testes passando (sem falhas).

- [ ] **Step 2: Push da branch**

```bash
git push origin claude/beautiful-ardinghelli-f76720
```

- [ ] **Step 3: Abrir PR no GitHub**

Acessar: https://github.com/academy-sun/Calculadora_Meu_bess/pull/new/claude/beautiful-ardinghelli-f76720

Título sugerido: `feat: backup_direto — Ploomes envia totais pré-calculados`

---

## Verificação final

Após merge e deploy no Railway, testar com `curl`:

```bash
curl -X POST https://<railway-url>/calculate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <api-key>" \
  -d '{
    "origem_info": {
      "origem": "ploomes",
      "negocio_id": "teste-001",
      "negocio_nome": "Teste",
      "solicitante_id": "dev",
      "solicitante_nome": "Dev",
      "solicitado_em": "2026-05-19T14:00:00Z"
    },
    "tipo_calculo": "backup_direto",
    "tipo_instalacao": "monofasico",
    "total_pp_kva": 5.0,
    "total_e_eps_kwh": 4.8
  }'
```

Resposta esperada: `200 OK` com `kit_selecionado` preenchido (ou `null` se catálogo vazio).
