# Design: Bulk Project Delete + Solar Price in Total

**Date:** 2026-04-29

## Feature A — Bulk Project Delete

### Goal
Allow users to select one or more projects and delete them in a single action. Engineers can only delete their own projects; admins can delete any project.

### Auth rules
- `user.sub` (JWT `sub` claim) matches `project.solicitante_id` → engineer owns the project
- `user.role === 'admin'` → can delete any project
- Backend enforces this; frontend hides delete controls for unowned rows (for engineers)

### Backend changes
- `list_projects` gains optional `user_id_filter: str | None`; router passes `current_user.sub` when `role != 'admin'`, `None` for admin
- New `delete_project(db, project_id)` service function
- New `bulk_delete_projects(db, ids, user_sub, is_admin)` service function — returns `(deleted_ids, forbidden_ids)`
- New schema `BulkDeleteRequest { ids: list[uuid] }` and `BulkDeleteResponse { deleted: list[uuid], forbidden: list[uuid] }`
- New route `DELETE /projects/{id}` — single delete with permission check
- New route `DELETE /projects` with JSON body — bulk delete

### Frontend changes
- `ProjectsPage` gains a checkbox column; header checkbox = select all
- When ≥1 project selected: action bar appears above table with "Excluir X projeto(s)" button (red)
- Modal de confirmação: shows count and types of selected projects; cancel/confirm
- After confirm: calls bulk delete, invalidates `['projects']` cache, clears selection
- Engineers see only their own projects (server-side filtering)
- Engineers: checkbox visible but only on their own rows (server already filters, so all visible rows are theirs)

## Feature B — Solar Module Price in Total

### Goal
Include the estimated cost of solar modules in the result, and show "Total com Solar" = kit BESS price + modules price.

### Backend changes
- `SolarStringsResult` gains `preco_modulos_total: float` (calculated as `qty_modulos × float(modulo.preco)`)
- `SolarDimensionamento` Pydantic model gains `preco_modulos_total: float`
- Mapping in `calculate/service.py` passes the field through

### Frontend changes
- `SolarDimensionamento` TypeScript interface gains `preco_modulos_total: number`
- Solar result card gains "Custo estimado dos módulos: R$ X.XXX"
- Kit BESS card gains "Total com Solar: R$ Y.YYY" line (amber, bold) when `solar_dimensionamento` present
