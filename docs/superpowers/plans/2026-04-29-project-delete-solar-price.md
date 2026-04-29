# Bulk Project Delete + Solar Price Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add bulk project deletion with role-based access control, and include solar module price in the total result display.

**Architecture:** Two independent features. Feature A (project delete) touches the backend projects router/service/schemas and the frontend ProjectsPage. Feature B (solar price) is a pure field addition propagated from the engine through schemas to the frontend result card.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy (backend), React 18 / TypeScript / Tailwind (frontend), Supabase PostgreSQL.

---

## File Map

| File | Action | Feature |
|---|---|---|
| `backend/app/projects/schemas.py` | Modify | A — add BulkDeleteRequest / BulkDeleteResponse |
| `backend/app/projects/service.py` | Modify | A — add delete fns, filter list by user |
| `backend/app/projects/router.py` | Modify | A — add DELETE endpoints, pass user to list |
| `backend/app/engines/schemas.py` | Modify | B — add preco_modulos_total to SolarStringsResult |
| `backend/app/engines/solar_strings.py` | Modify | B — calculate preco_modulos_total |
| `backend/app/calculate/schemas.py` | Modify | B — add preco_modulos_total to SolarDimensionamento |
| `backend/app/calculate/service.py` | Modify | B — pass preco_modulos_total in mapping |
| `frontend/src/types/index.ts` | Modify | A+B — add preco_modulos_total; Project type check |
| `frontend/src/lib/api.ts` | Modify | A — add apiBulkDelete helper |
| `frontend/src/hooks/useProjects.ts` | Modify | A — add useDeleteProjects hook |
| `frontend/src/pages/ProjectsPage.tsx` | Modify | A — checkboxes, action bar, confirm modal |
| `frontend/src/pages/NewProjectPage.tsx` | Modify | B — module cost + total com solar |

---

## Task 1: Solar Price — Engine Layer

**Files:**
- Modify: `backend/app/engines/schemas.py`
- Modify: `backend/app/engines/solar_strings.py`

- [ ] **Step 1: Add `preco_modulos_total` to `SolarStringsResult`**

In `backend/app/engines/schemas.py`, find the `SolarStringsResult.__init__` and add the field at the end of the parameter list and body:

```python
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
        preco_modulos_total: float,
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
        self.preco_modulos_total = preco_modulos_total
```

- [ ] **Step 2: Calculate and pass `preco_modulos_total` in `_size_module`**

In `backend/app/engines/solar_strings.py`, find the `return SolarStringsResult(...)` call inside `_size_module`. Before it, add the price calculation, and pass the new field:

```python
    preco_modulos_total = round(float(modulo.preco) * qty_modulos, 2) if modulo.preco else 0.0

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
        preco_modulos_total=preco_modulos_total,
    )
```

- [ ] **Step 3: Verify Python syntax**

```bash
cd /path/to/Calculadora_Meu_bess
python3 -c "import ast; ast.parse(open('backend/app/engines/schemas.py').read()); ast.parse(open('backend/app/engines/solar_strings.py').read()); print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/engines/schemas.py backend/app/engines/solar_strings.py
git commit -m "feat(engines): add preco_modulos_total to solar string sizing result"
```

---

## Task 2: Solar Price — Calculate Layer

**Files:**
- Modify: `backend/app/calculate/schemas.py`
- Modify: `backend/app/calculate/service.py`

- [ ] **Step 1: Add `preco_modulos_total` to `SolarDimensionamento`**

In `backend/app/calculate/schemas.py`, find `class SolarDimensionamento(BaseModel)` and add the field at the end:

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
    preco_modulos_total: float
```

- [ ] **Step 2: Pass `preco_modulos_total` in the service mapping**

In `backend/app/calculate/service.py`, find the `SolarDimensionamento(...)` constructor call (inside the `solar_dimensionamento=(... if solar_dim_result else None)` block) and add the field:

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
                    preco_modulos_total=solar_dim_result.preco_modulos_total,
                )
                if solar_dim_result else None
            ),
```

- [ ] **Step 3: Verify syntax**

```bash
python3 -c "import ast; ast.parse(open('backend/app/calculate/schemas.py').read()); ast.parse(open('backend/app/calculate/service.py').read()); print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/calculate/schemas.py backend/app/calculate/service.py
git commit -m "feat(calculate): propagate preco_modulos_total through SolarDimensionamento"
```

---

## Task 3: Project Delete — Backend

**Files:**
- Modify: `backend/app/projects/schemas.py`
- Modify: `backend/app/projects/service.py`
- Modify: `backend/app/projects/router.py`

- [ ] **Step 1: Add bulk delete schemas**

In `backend/app/projects/schemas.py`, add after the existing imports and before or after `ProjectRead`:

```python
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ProjectRead(BaseModel):
    id: uuid.UUID
    tipo_calculo: str
    estado: str
    versao: int
    origem: str
    negocio_id: Optional[str]
    negocio_nome: Optional[str]
    solicitante_id: str
    solicitante_nome: str
    solicitado_em: datetime
    calculado_em: Optional[datetime]
    parametros: Optional[dict]

    model_config = {"from_attributes": True}


class BulkDeleteRequest(BaseModel):
    ids: list[uuid.UUID]


class BulkDeleteResponse(BaseModel):
    deleted: list[uuid.UUID]
    forbidden: list[uuid.UUID]
```

- [ ] **Step 2: Add service functions for delete and filtered list**

Read `backend/app/projects/service.py`. Replace the `list_projects` function signature and add two new functions at the end of the file:

```python
async def list_projects(
    db: AsyncSession,
    origem: str | None = None,
    negocio_id: str | None = None,
    limit: int = 50,
    user_id_filter: str | None = None,
) -> list[Project]:
    stmt = select(Project).order_by(Project.solicitado_em.desc()).limit(limit)
    if origem:
        stmt = stmt.where(Project.origem == origem)
    if negocio_id:
        stmt = stmt.where(Project.negocio_id == negocio_id)
    if user_id_filter:
        stmt = stmt.where(Project.solicitante_id == user_id_filter)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def delete_project(db: AsyncSession, project_id: uuid.UUID) -> bool:
    project = await get_project(db, project_id)
    if not project:
        return False
    await db.delete(project)
    await db.commit()
    return True


async def bulk_delete_projects(
    db: AsyncSession,
    project_ids: list[uuid.UUID],
    user_sub: str,
    is_admin: bool,
) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    """Returns (deleted_ids, forbidden_ids)."""
    deleted: list[uuid.UUID] = []
    forbidden: list[uuid.UUID] = []
    for pid in project_ids:
        project = await get_project(db, pid)
        if not project:
            continue
        if not is_admin and project.solicitante_id != user_sub:
            forbidden.append(pid)
            continue
        await db.delete(project)
        deleted.append(pid)
    await db.commit()
    return deleted, forbidden
```

Also make sure `import uuid` is at the top of service.py (add if missing).

- [ ] **Step 3: Add DELETE endpoints to router**

Read `backend/app/projects/router.py`. Replace the file content with:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.schemas import UserInToken
from app.database import get_db
from app.projects import service
from app.projects.schemas import BulkDeleteRequest, BulkDeleteResponse, ProjectRead

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectRead])
async def list_projects(
    origem: str | None = None,
    negocio_id: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    user_filter = None if current_user.role == "admin" else current_user.sub
    return await service.list_projects(
        db, origem=origem, negocio_id=negocio_id, limit=limit, user_id_filter=user_filter
    )


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    project = await service.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return project


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    project = await service.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    if current_user.role != "admin" and project.solicitante_id != current_user.sub:
        raise HTTPException(status_code=403, detail="Sem permissão para excluir este projeto")
    await service.delete_project(db, project_id)


@router.delete("", response_model=BulkDeleteResponse)
async def bulk_delete_projects(
    request: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    deleted, forbidden = await service.bulk_delete_projects(
        db,
        request.ids,
        current_user.sub,
        current_user.role == "admin",
    )
    return BulkDeleteResponse(deleted=deleted, forbidden=forbidden)
```

- [ ] **Step 4: Verify syntax**

```bash
python3 -c "
import ast
for f in ['backend/app/projects/schemas.py','backend/app/projects/service.py','backend/app/projects/router.py']:
    ast.parse(open(f).read())
    print(f'OK: {f}')
"
```

Expected: three `OK` lines.

- [ ] **Step 5: Check UserInToken has `.sub` field**

```bash
grep -n "sub\|class UserInToken" backend/app/auth/schemas.py
```

If `sub` is missing from `UserInToken`, add it:
```python
class UserInToken(BaseModel):
    sub: str
    email: str
    role: str
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/projects/schemas.py backend/app/projects/service.py backend/app/projects/router.py
git commit -m "feat(projects): add bulk delete endpoints with role-based access + engineer filtering"
```

---

## Task 4: Frontend — Types, API helper, Hook

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/hooks/useProjects.ts`

- [ ] **Step 1: Add `preco_modulos_total` to `SolarDimensionamento` in types**

In `frontend/src/types/index.ts`, find `export interface SolarDimensionamento` and add the field at the end:

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
  preco_modulos_total: number
}
```

- [ ] **Step 2: Add `apiBulkDelete` to api.ts**

In `frontend/src/lib/api.ts`, find the `apiDelete` function and add a new function after it:

```typescript
export async function apiBulkDelete<T>(path: string, body: unknown): Promise<T> {
  const headers = await getAuthHeaders()
  const res = await fetch(`${API_URL}${path}`, {
    method: 'DELETE',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: string }).detail ?? `Erro ${res.status}`)
  }
  return res.json() as Promise<T>
}
```

- [ ] **Step 3: Add `useDeleteProjects` hook**

In `frontend/src/hooks/useProjects.ts`, add at the end of the file:

```typescript
interface BulkDeleteResponse {
  deleted: string[]
  forbidden: string[]
}

export function useDeleteProjects() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (ids: string[]) =>
      apiBulkDelete<BulkDeleteResponse>('/projects', { ids }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}
```

Also add `apiBulkDelete` to the import from `@/lib/api` at the top of `useProjects.ts`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/lib/api.ts frontend/src/hooks/useProjects.ts
git commit -m "feat(frontend): add preco_modulos_total type, apiBulkDelete helper, useDeleteProjects hook"
```

---

## Task 5: Frontend — Solar Price UI (NewProjectPage)

**Files:**
- Modify: `frontend/src/pages/NewProjectPage.tsx`

- [ ] **Step 1: Add module cost line to solar result card**

Read `frontend/src/pages/NewProjectPage.tsx`. Find the solar dimensionamento result block — look for `result?.solar_dimensionamento &&`. Inside the grid, find the `col-span-2` div for `cobertura_pct` and add a new `col-span-2` row after it:

```tsx
            <div className="col-span-2 border-t border-amber-200 pt-2">
              <span className="text-gray-500">Custo estimado dos módulos</span>
              <p className="font-semibold text-amber-800">
                {result.solar_dimensionamento.preco_modulos_total.toLocaleString('pt-BR', {
                  style: 'currency', currency: 'BRL',
                })}
              </p>
            </div>
```

- [ ] **Step 2: Add "Total com Solar" to the kit result card**

In the same file, find where the kit BESS result is rendered — look for `result?.kit_selecionado &&` and inside it find `preco_total`. After the price display, add:

```tsx
                {result.solar_dimensionamento && (
                  <div className="mt-2 border-t border-amber-200 pt-2">
                    <span className="text-xs text-gray-500">Total com Solar</span>
                    <p className="text-lg font-bold text-amber-700">
                      {(result.kit_selecionado.preco_total + result.solar_dimensionamento.preco_modulos_total)
                        .toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                    </p>
                  </div>
                )}
```

Note: the exact location depends on how the kit card is structured. Read the file carefully to find the right insertion point near the `preco_total` display. The `Total com Solar` line should appear directly below the kit price.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/NewProjectPage.tsx
git commit -m "feat(ui): show solar module cost and total-with-solar in backup result"
```

---

## Task 6: Frontend — Bulk Delete UI (ProjectsPage)

**Files:**
- Modify: `frontend/src/pages/ProjectsPage.tsx`

- [ ] **Step 1: Read the current file**

Read `frontend/src/pages/ProjectsPage.tsx` fully before making any edits.

- [ ] **Step 2: Rewrite ProjectsPage with bulk delete support**

Replace the entire file content with:

```tsx
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { PlusCircle, Trash2 } from 'lucide-react'
import { useProjects, useDeleteProjects } from '@/hooks/useProjects'

const TIPO_LABEL: Record<string, string> = {
  backup: 'Backup',
  peak_shaving: 'Peak Shaving',
  arbitragem: 'Arbitragem',
  solar: 'Solar',
  solar_storage: 'Solar + Storage',
}

const ESTADO_COLOR: Record<string, string> = {
  concluido: 'bg-green-100 text-green-700',
  calculando: 'bg-yellow-100 text-yellow-700',
  erro: 'bg-red-100 text-red-700',
}

export function ProjectsPage() {
  const { data: projects, isLoading, error } = useProjects()
  const deleteMutation = useDeleteProjects()

  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [showConfirm, setShowConfirm] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const allIds = projects?.map(p => p.id) ?? []
  const allSelected = allIds.length > 0 && allIds.every(id => selected.has(id))

  function toggleAll() {
    if (allSelected) {
      setSelected(new Set())
    } else {
      setSelected(new Set(allIds))
    }
  }

  function toggleOne(id: string) {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  async function handleDelete() {
    setDeleteError(null)
    try {
      await deleteMutation.mutateAsync(Array.from(selected))
      setSelected(new Set())
      setShowConfirm(false)
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'Erro ao excluir')
    }
  }

  const selectedCount = selected.size

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Projetos</h1>
        <Link
          to="/projects/new"
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-dark"
        >
          <PlusCircle size={16} /> Novo Cálculo
        </Link>
      </div>

      {deleteError && (
        <div className="mb-4 rounded-lg bg-red-50 px-4 py-2 text-sm text-red-600">{deleteError}</div>
      )}

      {/* Action bar — appears when items selected */}
      {selectedCount > 0 && (
        <div className="mb-4 flex items-center justify-between rounded-lg border border-red-200 bg-red-50 px-4 py-3">
          <span className="text-sm font-medium text-red-700">
            {selectedCount} projeto{selectedCount > 1 ? 's' : ''} selecionado{selectedCount > 1 ? 's' : ''}
          </span>
          <button
            onClick={() => setShowConfirm(true)}
            className="flex items-center gap-2 rounded-lg bg-red-600 px-3 py-1.5 text-sm text-white hover:bg-red-700"
          >
            <Trash2 size={14} />
            Excluir selecionados
          </button>
        </div>
      )}

      {isLoading && <p className="text-gray-500">Carregando...</p>}
      {error && <p className="text-red-600">Erro ao carregar projetos.</p>}

      {projects && (
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs font-semibold uppercase text-gray-500">
              <tr>
                <th className="px-4 py-3 text-left w-10">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={toggleAll}
                    className="rounded border-gray-300"
                  />
                </th>
                <th className="px-4 py-3 text-left">Tipo</th>
                <th className="px-4 py-3 text-left">Solicitante</th>
                <th className="px-4 py-3 text-left">Origem</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">Data</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {projects.map(p => (
                <tr key={p.id} className={`hover:bg-gray-50 ${selected.has(p.id) ? 'bg-red-50/40' : ''}`}>
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={selected.has(p.id)}
                      onChange={() => toggleOne(p.id)}
                      className="rounded border-gray-300"
                    />
                  </td>
                  <td className="px-4 py-3 font-medium">
                    {TIPO_LABEL[p.tipo_calculo] ?? p.tipo_calculo}
                  </td>
                  <td className="px-4 py-3 text-gray-600">{p.solicitante_nome}</td>
                  <td className="px-4 py-3">
                    <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs capitalize">
                      {p.origem}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${ESTADO_COLOR[p.estado] ?? ''}`}>
                      {p.estado}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {new Date(p.solicitado_em).toLocaleDateString('pt-BR')}
                  </td>
                  <td className="px-4 py-3">
                    <Link to={`/projects/${p.id}`} className="text-primary hover:underline">
                      Ver
                    </Link>
                  </td>
                </tr>
              ))}
              {projects.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                    Nenhum projeto ainda.{' '}
                    <Link to="/projects/new" className="text-primary">Criar o primeiro</Link>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Confirm delete modal */}
      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-sm rounded-xl bg-white p-6 shadow-xl">
            <h2 className="mb-2 text-lg font-bold text-gray-800">Excluir projetos?</h2>
            <p className="mb-5 text-sm text-gray-600">
              Tem certeza que deseja excluir{' '}
              <strong>{selectedCount} projeto{selectedCount > 1 ? 's' : ''}</strong>?
              Esta ação não pode ser desfeita.
            </p>
            {deleteError && (
              <p className="mb-3 text-sm text-red-600">{deleteError}</p>
            )}
            <div className="flex justify-end gap-2">
              <button
                onClick={() => { setShowConfirm(false); setDeleteError(null) }}
                className="rounded-lg border border-gray-300 px-4 py-2 text-sm hover:bg-gray-50"
              >
                Cancelar
              </button>
              <button
                onClick={handleDelete}
                disabled={deleteMutation.isPending}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm text-white hover:bg-red-700 disabled:opacity-50"
              >
                {deleteMutation.isPending ? 'Excluindo...' : 'Excluir'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ProjectsPage.tsx
git commit -m "feat(ui): add bulk project deletion with checkboxes and confirmation modal"
```

---

## Task 7: Push and Verify

- [ ] **Step 1: Check all Python files parse cleanly**

```bash
python3 -c "
import ast
files = [
    'backend/app/engines/schemas.py',
    'backend/app/engines/solar_strings.py',
    'backend/app/calculate/schemas.py',
    'backend/app/calculate/service.py',
    'backend/app/projects/schemas.py',
    'backend/app/projects/service.py',
    'backend/app/projects/router.py',
]
for f in files:
    ast.parse(open(f).read())
    print(f'OK: {f}')
"
```

Expected: 7 `OK` lines.

- [ ] **Step 2: Check all modified frontend files exist and have content**

```bash
python3 -c "
import os
files = [
    'frontend/src/types/index.ts',
    'frontend/src/lib/api.ts',
    'frontend/src/hooks/useProjects.ts',
    'frontend/src/pages/ProjectsPage.tsx',
    'frontend/src/pages/NewProjectPage.tsx',
]
for f in files:
    size = os.path.getsize(f)
    print(f'OK: {f} ({size} bytes)')
"
```

- [ ] **Step 3: Push to origin**

```bash
git push origin main
```

- [ ] **Step 4: Smoke test after deploy**

1. Abrir `/projects` — deve aparecer só os próprios projetos (engenheiro) ou todos (admin)
2. Selecionar 1 ou mais projetos → barra vermelha aparece no topo
3. Clicar "Excluir selecionados" → modal de confirmação aparece
4. Confirmar → projetos somem da lista
5. Fazer um cálculo Backup com consumo mensal + cidade preenchidos → card solar mostra "Custo estimado dos módulos" e o kit mostra "Total com Solar"
