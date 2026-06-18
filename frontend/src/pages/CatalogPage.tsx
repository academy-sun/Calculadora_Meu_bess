import { useState, useMemo } from 'react'
import {
  useBESSProducts, useCreateBESS, useUpdateBESS, useDeleteBESS,
  useSolarProducts, useCreateSolar, useUpdateSolar, useDeleteSolar,
  useSyncCatalog,
} from '@/hooks/useCatalog'
import type { SyncResult } from '@/hooks/useCatalog'
import type { ProductBESS, ProductSolar } from '@/types'
import { PlusCircle, RefreshCw, Trash2 } from 'lucide-react'

// ── combined row ──────────────────────────────────────────────────────────────

type BESSRow  = ProductBESS  & { _source: 'bess' }
type SolarRow = ProductSolar & { _source: 'solar' }
type CatalogRow = BESSRow | SolarRow

function isBESS(r: CatalogRow): r is BESSRow  { return r._source === 'bess' }

function specLabel(r: CatalogRow): string {
  if (isBESS(r)) {
    if (r.tipo === 'bateria')         return r.capacidade_kwh       ? `${r.capacidade_kwh} kWh` : '—'
    if (r.tipo === 'inversor_hibrido') return r.potencia_continua_kw ? `${r.potencia_continua_kw} kW` : '—'
    return '—'
  }
  if (r.tipo === 'modulo_fv')    return r.potencia_pico_wp    ? `${r.potencia_pico_wp} Wp`  : '—'
  if (r.tipo === 'inversor_solar') return r.potencia_nominal_kw ? `${r.potencia_nominal_kw} kW` : '—'
  return '—'
}

const TIPO_LABEL: Record<string, string> = {
  bateria:          'Bateria',
  inversor_hibrido: 'Inversor Híbrido',
  modulo_fv:        'Módulo FV',
  inversor_solar:   'Inversor Solar',
}

// ── form types ────────────────────────────────────────────────────────────────

type AllTipo = ProductBESS['tipo'] | ProductSolar['tipo']

interface CatalogForm {
  marca: string; modelo: string; sku: string
  tipo: AllTipo
  fase?: 'monofasico' | 'trifasico'
  preco: number; disponivel: boolean
  // BESS
  capacidade_kwh?: number; potencia_continua_kw?: number; dod_percent?: number
  corrente_max_descarga_a?: number; corrente_max_dc_a?: number
  mppt_qty?: number; mppt_v_max?: number; mppt_i_max_a?: number
  pot_ca_max_eps_kva?: number; tensao_nominal_v?: number
  // Solar
  potencia_pico_wp?: number; potencia_nominal_kw?: number
  eficiencia_pct?: number; voc_v?: number; vmp_v?: number
  isc_a?: number; imp_a?: number; mppt_min_v?: number; mppt_max_v?: number
}

const EMPTY_FORM: CatalogForm = {
  marca: '', modelo: '', sku: '', tipo: 'bateria', disponivel: true, preco: 0,
}

function isBESSTipo(t: AllTipo): t is ProductBESS['tipo'] {
  return t === 'bateria' || t === 'inversor_hibrido' || t === 'bess_comercial'
}

// ── small helpers ─────────────────────────────────────────────────────────────

function FField({ label, value, onChange, required }: {
  label: string; value: string; onChange: (v: string) => void; required?: boolean
}) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-gray-700">{label}</label>
      <input type="text" value={value} onChange={e => onChange(e.target.value)} required={required}
        className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-primary focus:outline-none" />
    </div>
  )
}
function NField({ label, value, onChange, required }: {
  label: string; value: number | undefined; onChange: (v: number | undefined) => void; required?: boolean
}) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-gray-700">{label}</label>
      <input type="number" step="any" value={value ?? ''} required={required}
        onChange={e => onChange(e.target.value === '' ? undefined : parseFloat(e.target.value))}
        className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-primary focus:outline-none" />
    </div>
  )
}

// ── filter input ──────────────────────────────────────────────────────────────

function FilterInput({ value, onChange, placeholder }: {
  value: string; onChange: (v: string) => void; placeholder?: string
}) {
  return (
    <input
      type="text"
      value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder ?? 'Filtrar…'}
      className="mt-1 w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-700 placeholder-gray-300 focus:border-primary focus:outline-none"
    />
  )
}

function FilterSelect({ value, onChange, options }: {
  value: string; onChange: (v: string) => void
  options: { value: string; label: string }[]
}) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      className="mt-1 w-full rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-700 focus:border-primary focus:outline-none"
    >
      <option value="">Todos</option>
      {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  )
}

// ── main page ─────────────────────────────────────────────────────────────────

export function CatalogPage() {
  const { data: bessData = [], isLoading: bessLoading } = useBESSProducts()
  const { data: solarData = [], isLoading: solarLoading } = useSolarProducts()

  const createBESS  = useCreateBESS();  const updateBESS  = useUpdateBESS();  const deleteBESS  = useDeleteBESS()
  const createSolar = useCreateSolar(); const updateSolar = useUpdateSolar(); const deleteSolar = useDeleteSolar()
  const syncMutation = useSyncCatalog()

  // ── sync state ──────────────────────────────────────────────────────────────
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null)
  const [syncError,  setSyncError]  = useState<string | null>(null)

  async function handleSync() {
    setSyncError(null); setSyncResult(null)
    try { setSyncResult(await syncMutation.mutateAsync()) }
    catch (err) { setSyncError(err instanceof Error ? err.message : 'Erro na sincronização') }
  }

  // ── combined rows ───────────────────────────────────────────────────────────
  const allRows = useMemo<CatalogRow[]>(() => [
    ...bessData.map(p => ({ ...p, _source: 'bess'  as const })),
    ...solarData.map(p => ({ ...p, _source: 'solar' as const })),
  ], [bessData, solarData])

  // ── filters ─────────────────────────────────────────────────────────────────
  const [fMarca, setFMarca]  = useState('')
  const [fTipo,  setFTipo]   = useState('')
  const [fFase,  setFFase]   = useState('')
  const [fSpec,  setFSpec]   = useState('')

  const filtered = useMemo(() => allRows.filter(r => {
    if (fMarca && !`${r.marca} ${r.modelo}`.toLowerCase().includes(fMarca.toLowerCase())) return false
    if (fTipo  && r.tipo !== fTipo)  return false
    if (fFase  && (r.fase ?? '') !== fFase) return false
    if (fSpec  && !specLabel(r).toLowerCase().includes(fSpec.toLowerCase())) return false
    return true
  }), [allRows, fMarca, fTipo, fFase, fSpec])

  const hasFilter = fMarca || fTipo || fFase || fSpec

  // ── form / modal ────────────────────────────────────────────────────────────
  const [showForm,    setShowForm]    = useState(false)
  const [editing,     setEditing]     = useState<CatalogRow | null>(null)
  const [form,        setForm]        = useState<CatalogForm>(EMPTY_FORM)
  const [formError,   setFormError]   = useState<string | null>(null)
  const [confirmDel,  setConfirmDel]  = useState<CatalogRow | null>(null)

  function set(field: keyof CatalogForm, value: unknown) {
    setForm(prev => ({ ...prev, [field]: value }))
  }

  function openCreate() { setForm(EMPTY_FORM); setEditing(null); setShowForm(true) }

  function openEdit(r: CatalogRow) {
    if (isBESS(r)) {
      const { _source: _, atualizado_em: __, id: _id, ...rest } = r
      setForm({ ...EMPTY_FORM, ...rest })
    } else {
      const { _source: _, id: _id, ...rest } = r
      setForm({ ...EMPTY_FORM, ...rest })
    }
    setEditing(r); setShowForm(true)
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault(); setFormError(null)
    try {
      if (isBESSTipo(form.tipo)) {
        const data = {
          marca: form.marca, modelo: form.modelo, sku: form.sku, tipo: form.tipo as ProductBESS['tipo'],
          fase: form.fase, preco: form.preco, disponivel: form.disponivel,
          capacidade_kwh: form.capacidade_kwh, potencia_continua_kw: form.potencia_continua_kw,
          dod_percent: form.dod_percent, corrente_max_descarga_a: form.corrente_max_descarga_a,
          corrente_max_dc_a: form.corrente_max_dc_a, mppt_qty: form.mppt_qty,
          mppt_v_max: form.mppt_v_max, mppt_i_max_a: form.mppt_i_max_a,
          pot_ca_max_eps_kva: form.pot_ca_max_eps_kva, tensao_nominal_v: form.tensao_nominal_v,
        }
        if (editing) await updateBESS.mutateAsync({ id: editing.id, ...data })
        else         await createBESS.mutateAsync(data as Omit<ProductBESS, 'id' | 'atualizado_em'>)
      } else {
        const data = {
          marca: form.marca, modelo: form.modelo, sku: form.sku, tipo: form.tipo as ProductSolar['tipo'],
          fase: form.fase, preco: form.preco, disponivel: form.disponivel,
          potencia_pico_wp: form.potencia_pico_wp, potencia_nominal_kw: form.potencia_nominal_kw,
          eficiencia_pct: form.eficiencia_pct, voc_v: form.voc_v, vmp_v: form.vmp_v,
          isc_a: form.isc_a, imp_a: form.imp_a, mppt_min_v: form.mppt_min_v, mppt_max_v: form.mppt_max_v,
        }
        if (editing) await updateSolar.mutateAsync({ id: editing.id, ...data })
        else         await createSolar.mutateAsync(data as Omit<ProductSolar, 'id'>)
      }
      setShowForm(false)
    } catch (err) { setFormError(err instanceof Error ? err.message : 'Erro ao salvar') }
  }

  async function handleDelete() {
    if (!confirmDel) return
    try {
      if (isBESS(confirmDel)) await deleteBESS.mutateAsync(confirmDel.id)
      else                     await deleteSolar.mutateAsync(confirmDel.id)
      setConfirmDel(null)
    } catch (err) { setFormError(err instanceof Error ? err.message : 'Erro ao excluir'); setConfirmDel(null) }
  }

  const isLoading = bessLoading || solarLoading
  const isSaving  = createBESS.isPending || updateBESS.isPending || createSolar.isPending || updateSolar.isPending

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Catálogo Solar e BESS</h1>
          <p className="text-sm text-gray-500">Módulos, Inversores, Baterias e Inversores Híbridos</p>
        </div>
        <div className="flex gap-2">
          <button onClick={handleSync} disabled={syncMutation.isPending}
            className="flex items-center gap-2 rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50">
            <RefreshCw size={16} className={syncMutation.isPending ? 'animate-spin' : ''} />
            {syncMutation.isPending ? 'Sincronizando...' : 'Sincronizar Plataforma'}
          </button>
          <button onClick={openCreate}
            className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm text-white hover:bg-primary-dark">
            <PlusCircle size={16} /> Novo Produto
          </button>
        </div>
      </div>

      {/* Sync banner */}
      {(syncResult || syncError) && (
        <div className={`mb-4 rounded-lg px-4 py-3 text-sm ${syncError ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-800'}`}>
          <div className="flex items-start justify-between gap-4">
            <div>
              {syncError  && <p className="font-medium">Erro na sincronização: {syncError}</p>}
              {syncResult && (
                <p className="font-medium">
                  ✅ {syncResult.total_synced} produto(s) sincronizado(s)
                  {syncResult.total_errors  > 0 && ` · ⚠ ${syncResult.total_errors} erro(s)`}
                  {(syncResult.needs_review_count ?? 0) > 0 && ` · 🔍 ${syncResult.needs_review_count} a revisar`}
                </p>
              )}
            </div>
            <button onClick={() => { setSyncResult(null); setSyncError(null) }} className="text-gray-400 hover:text-gray-600 flex-shrink-0">✕</button>
          </div>
        </div>
      )}

      {isLoading && <p className="text-gray-500">Carregando…</p>}

      {/* Table */}
      {!isLoading && (
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              {/* Column headers */}
              <tr className="text-xs font-semibold uppercase text-gray-500">
                <th className="px-4 pt-3 pb-1 text-left">Marca / Modelo</th>
                <th className="px-4 pt-3 pb-1 text-left">Tipo</th>
                <th className="px-4 pt-3 pb-1 text-left">Fase</th>
                <th className="px-4 pt-3 pb-1 text-right">Especificação</th>
                <th className="px-4 pt-3 pb-1 text-right">Preço (R$)</th>
                <th className="px-4 pt-3 pb-1 text-left">Status</th>
                <th className="px-4 pt-3 pb-1" />
              </tr>
              {/* Filter row */}
              <tr className="border-t border-gray-100">
                <th className="px-3 pb-2 pt-1">
                  <FilterInput value={fMarca} onChange={setFMarca} placeholder="Buscar marca ou modelo…" />
                </th>
                <th className="px-3 pb-2 pt-1">
                  <FilterSelect value={fTipo} onChange={setFTipo} options={[
                    { value: 'bateria',          label: 'Bateria' },
                    { value: 'inversor_hibrido', label: 'Inversor Híbrido' },
                    { value: 'modulo_fv',        label: 'Módulo FV' },
                    { value: 'inversor_solar',   label: 'Inversor Solar' },
                  ]} />
                </th>
                <th className="px-3 pb-2 pt-1">
                  <FilterSelect value={fFase} onChange={setFFase} options={[
                    { value: 'monofasico', label: 'Monofásico' },
                    { value: 'trifasico',  label: 'Trifásico' },
                  ]} />
                </th>
                <th className="px-3 pb-2 pt-1 text-right">
                  <FilterInput value={fSpec} onChange={setFSpec} placeholder="ex: 550 Wp" />
                </th>
                <th className="px-3 pb-2 pt-1" />
                <th className="px-3 pb-2 pt-1">
                  {hasFilter && (
                    <button onClick={() => { setFMarca(''); setFTipo(''); setFFase(''); setFSpec('') }}
                      className="mt-1 text-xs text-primary hover:underline whitespace-nowrap">
                      Limpar filtros
                    </button>
                  )}
                </th>
                <th className="px-3 pb-2 pt-1" />
              </tr>
            </thead>

            <tbody className="divide-y divide-gray-100">
              {filtered.map(r => (
                <tr key={`${r._source}-${r.id}`} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <p className="font-medium">{r.marca}</p>
                    <p className="text-xs text-gray-500">{r.modelo}</p>
                  </td>
                  <td className="px-4 py-3 text-gray-700">{TIPO_LABEL[r.tipo] ?? r.tipo}</td>
                  <td className="px-4 py-3 capitalize text-gray-700">
                    {r.fase ? r.fase.replace('fasico', 'fásico') : '—'}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">{specLabel(r)}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{r.preco.toLocaleString('pt-BR')}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs ${r.disponivel ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                      {r.disponivel ? 'Disponível' : 'Inativo'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-3">
                      <button onClick={() => openEdit(r)} className="text-xs text-primary hover:underline">Editar</button>
                      <button onClick={() => setConfirmDel(r)} className="text-gray-400 hover:text-red-600 transition-colors">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {filtered.length === 0 && !isLoading && (
            <p className="py-10 text-center text-sm text-gray-400">
              {hasFilter ? 'Nenhum produto corresponde aos filtros.' : 'Nenhum produto cadastrado.'}
            </p>
          )}
        </div>
      )}

      {/* ── Create / Edit Modal ── */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl bg-white p-6 shadow-xl">
            <h2 className="mb-4 text-lg font-bold">{editing ? 'Editar' : 'Novo'} Produto</h2>
            <form onSubmit={handleSave} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <FField label="Marca" value={form.marca} onChange={v => set('marca', v)} required />
                <FField label="Modelo" value={form.modelo} onChange={v => set('modelo', v)} required />
              </div>
              <FField label="SKU" value={form.sku} onChange={v => set('sku', v)} required />

              <div>
                <label className="mb-1 block text-xs font-medium text-gray-700">Tipo</label>
                <select value={form.tipo} onChange={e => set('tipo', e.target.value as AllTipo)}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm">
                  <optgroup label="BESS">
                    <option value="bateria">Bateria</option>
                    <option value="inversor_hibrido">Inversor Híbrido</option>
                  </optgroup>
                  <optgroup label="Solar">
                    <option value="modulo_fv">Módulo FV</option>
                    <option value="inversor_solar">Inversor Solar</option>
                  </optgroup>
                </select>
              </div>

              {/* Fase (BESS and inversor_solar) */}
              {(form.tipo !== 'modulo_fv') && (
                <div>
                  <label className="mb-1 block text-xs font-medium text-gray-700">Fase</label>
                  <select value={form.fase ?? ''} onChange={e => set('fase', e.target.value || undefined)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm">
                    <option value="">—</option>
                    <option value="monofasico">Monofásico</option>
                    <option value="trifasico">Trifásico</option>
                  </select>
                </div>
              )}

              {/* Bateria */}
              {form.tipo === 'bateria' && (
                <div className="rounded-lg bg-blue-50 border border-blue-100 p-3">
                  <p className="mb-2 text-xs font-semibold uppercase text-blue-600">Especificações da Bateria</p>
                  <div className="grid grid-cols-2 gap-3">
                    <NField label="Capacidade (kWh)" value={form.capacidade_kwh} onChange={v => set('capacidade_kwh', v)} />
                    <NField label="Tensão Nominal (V)" value={form.tensao_nominal_v} onChange={v => set('tensao_nominal_v', v)} />
                    <NField label="DoD (%)" value={form.dod_percent} onChange={v => set('dod_percent', v)} />
                    <NField label="Corrente Máx. Descarga (A)" value={form.corrente_max_descarga_a} onChange={v => set('corrente_max_descarga_a', v)} />
                  </div>
                </div>
              )}

              {/* Inversor Híbrido */}
              {form.tipo === 'inversor_hibrido' && (
                <div className="rounded-lg bg-amber-50 border border-amber-100 p-3">
                  <p className="mb-2 text-xs font-semibold uppercase text-amber-600">Especificações do Inversor Híbrido</p>
                  <div className="grid grid-cols-2 gap-3">
                    <NField label="Potência Contínua (kW)" value={form.potencia_continua_kw} onChange={v => set('potencia_continua_kw', v)} />
                    <NField label="Entradas MPPT" value={form.mppt_qty} onChange={v => set('mppt_qty', v)} />
                    <NField label="Tensão Máx. Entrada (V)" value={form.mppt_v_max} onChange={v => set('mppt_v_max', v)} />
                    <NField label="Corrente Máx. Entrada (A)" value={form.mppt_i_max_a} onChange={v => set('mppt_i_max_a', v)} />
                    <NField label="P_máx EPS (kVA)" value={form.pot_ca_max_eps_kva} onChange={v => set('pot_ca_max_eps_kva', v)} />
                  </div>
                </div>
              )}

              {/* Módulo FV */}
              {form.tipo === 'modulo_fv' && (
                <div className="rounded-lg bg-yellow-50 border border-yellow-100 p-3">
                  <p className="mb-2 text-xs font-semibold uppercase text-yellow-700">Especificações do Módulo</p>
                  <div className="grid grid-cols-2 gap-3">
                    <NField label="Potência Pico (Wp)" value={form.potencia_pico_wp} onChange={v => set('potencia_pico_wp', v)} />
                    <NField label="Eficiência (%)" value={form.eficiencia_pct} onChange={v => set('eficiencia_pct', v)} />
                    <NField label="Voc (V)" value={form.voc_v} onChange={v => set('voc_v', v)} />
                    <NField label="Vmp (V)" value={form.vmp_v} onChange={v => set('vmp_v', v)} />
                    <NField label="Isc (A)" value={form.isc_a} onChange={v => set('isc_a', v)} />
                    <NField label="Imp (A)" value={form.imp_a} onChange={v => set('imp_a', v)} />
                  </div>
                </div>
              )}

              {/* Inversor Solar */}
              {form.tipo === 'inversor_solar' && (
                <div className="rounded-lg bg-green-50 border border-green-100 p-3">
                  <p className="mb-2 text-xs font-semibold uppercase text-green-700">Especificações do Inversor Solar</p>
                  <div className="grid grid-cols-2 gap-3">
                    <NField label="Potência Nominal (kW)" value={form.potencia_nominal_kw} onChange={v => set('potencia_nominal_kw', v)} />
                    <NField label="MPPT Mín (V)" value={form.mppt_min_v} onChange={v => set('mppt_min_v', v)} />
                    <NField label="MPPT Máx (V)" value={form.mppt_max_v} onChange={v => set('mppt_max_v', v)} />
                  </div>
                </div>
              )}

              <NField label="Preço (R$)" value={form.preco} onChange={v => set('preco', v ?? 0)} required />
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.disponivel} onChange={e => set('disponivel', e.target.checked)} />
                Disponível
              </label>

              {formError && <p className="text-sm text-red-600">{formError}</p>}
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setShowForm(false)}
                  className="rounded-lg border border-gray-300 px-4 py-2 text-sm hover:bg-gray-50">Cancelar</button>
                <button type="submit" disabled={isSaving}
                  className="rounded-lg bg-primary px-4 py-2 text-sm text-white hover:bg-primary-dark disabled:opacity-50">
                  {isSaving ? 'Salvando…' : editing ? 'Salvar' : 'Criar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Delete Confirmation ── */}
      {confirmDel && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-sm rounded-xl bg-white p-6 shadow-xl">
            <h2 className="mb-2 text-lg font-bold text-gray-800">Excluir produto?</h2>
            <p className="mb-5 text-sm text-gray-600">
              Tem certeza que deseja excluir <strong>{confirmDel.marca} {confirmDel.modelo}</strong>?
              Esta ação não pode ser desfeita.
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setConfirmDel(null)}
                className="rounded-lg border border-gray-300 px-4 py-2 text-sm hover:bg-gray-50">Cancelar</button>
              <button onClick={handleDelete}
                disabled={deleteBESS.isPending || deleteSolar.isPending}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm text-white hover:bg-red-700 disabled:opacity-50">
                {(deleteBESS.isPending || deleteSolar.isPending) ? 'Excluindo…' : 'Excluir'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
