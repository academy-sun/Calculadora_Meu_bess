import { useState } from 'react'
import { useSolarProducts, useCreateSolar, useUpdateSolar, useDeleteSolar } from '@/hooks/useCatalog'
import type { ProductSolar } from '@/types'
import { PlusCircle, Trash2 } from 'lucide-react'

type SolarForm = Omit<ProductSolar, 'id'>

const EMPTY_FORM: SolarForm = {
  marca: '', modelo: '', sku: '', tipo: 'modulo_fv', preco: 0, disponivel: true,
  voc_v: undefined,
  vmp_v: undefined,
  isc_a: undefined,
  imp_a: undefined,
}

export function CatalogSolarPage() {
  const { data: products, isLoading } = useSolarProducts()
  const createMutation = useCreateSolar()
  const updateMutation = useUpdateSolar()
  const deleteMutation = useDeleteSolar()

  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<ProductSolar | null>(null)
  const [form, setForm] = useState<SolarForm>(EMPTY_FORM)
  const [error, setError] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<ProductSolar | null>(null)

  function set(field: keyof SolarForm, value: unknown) { setForm(prev => ({ ...prev, [field]: value })) }

  function openCreate() { setForm(EMPTY_FORM); setEditing(null); setShowForm(true) }
  function openEdit(p: ProductSolar) {
    const { id: _id, ...rest } = p
    setForm(rest as SolarForm); setEditing(p); setShowForm(true)
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault(); setError(null)
    try {
      if (editing) await updateMutation.mutateAsync({ id: editing.id, ...form })
      else await createMutation.mutateAsync(form)
      setShowForm(false)
      setForm(EMPTY_FORM)
    } catch (err: unknown) { setError(err instanceof Error ? err.message : 'Erro ao salvar') }
  }

  async function handleDelete() {
    if (!confirmDelete) return
    try {
      await deleteMutation.mutateAsync(confirmDelete.id)
      setConfirmDelete(null)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erro ao excluir')
      setConfirmDelete(null)
    }
  }

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Catálogo Solar</h1>
          <p className="text-sm text-gray-500">Módulos FV e Inversores Solares</p>
        </div>
        <button onClick={openCreate}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm text-white hover:bg-primary-dark">
          <PlusCircle size={16} /> Novo Produto
        </button>
      </div>

      {error && !showForm && (
        <div className="mb-4 rounded-lg bg-red-50 px-4 py-2 text-sm text-red-600">{error}</div>
      )}

      {isLoading && <p className="text-gray-500">Carregando...</p>}

      {products && (
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs font-semibold uppercase text-gray-500">
              <tr>
                <th className="px-4 py-3 text-left">Marca / Modelo</th>
                <th className="px-4 py-3 text-left">Tipo</th>
                <th className="px-4 py-3 text-right">Potência</th>
                <th className="px-4 py-3 text-right">Preço (R$)</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {products.map(p => (
                <tr key={p.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3"><p className="font-medium">{p.marca}</p><p className="text-xs text-gray-500">{p.modelo}</p></td>
                  <td className="px-4 py-3 capitalize">{p.tipo.replace(/_/g, ' ')}</td>
                  <td className="px-4 py-3 text-right">
                    {p.potencia_pico_wp ? `${p.potencia_pico_wp} Wp` : p.potencia_nominal_kw ? `${p.potencia_nominal_kw} kW` : '—'}
                  </td>
                  <td className="px-4 py-3 text-right">{p.preco.toLocaleString('pt-BR')}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs ${p.disponivel ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                      {p.disponivel ? 'Disponível' : 'Inativo'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-3">
                      <button onClick={() => openEdit(p)} className="text-xs text-primary hover:underline">Editar</button>
                      <button onClick={() => setConfirmDelete(p)}
                        className="text-gray-400 hover:text-red-600 transition-colors">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {products.length === 0 && (
            <p className="py-8 text-center text-sm text-gray-400">Nenhum produto solar cadastrado.</p>
          )}
        </div>
      )}

      {/* Edit / Create Modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl bg-white p-6 shadow-xl">
            <h2 className="mb-4 text-lg font-bold">{editing ? 'Editar' : 'Novo'} Produto Solar</h2>
            <form onSubmit={handleSave} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div><label className="mb-1 block text-xs font-medium text-gray-700">Marca</label>
                  <input type="text" value={form.marca} onChange={e => set('marca', e.target.value)} required
                    className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm" /></div>
                <div><label className="mb-1 block text-xs font-medium text-gray-700">Modelo</label>
                  <input type="text" value={form.modelo} onChange={e => set('modelo', e.target.value)} required
                    className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm" /></div>
              </div>
              <div><label className="mb-1 block text-xs font-medium text-gray-700">SKU</label>
                <input type="text" value={form.sku} onChange={e => set('sku', e.target.value)} required
                  className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm" /></div>
              <div><label className="mb-1 block text-xs font-medium text-gray-700">Tipo</label>
                <select value={form.tipo} onChange={e => set('tipo', e.target.value as ProductSolar['tipo'])}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm">
                  <option value="modulo_fv">Módulo FV</option>
                  <option value="inversor_solar">Inversor Solar</option>
                </select>
              </div>
              {form.tipo === 'modulo_fv' && (
                <div className="grid grid-cols-2 gap-3">
                  <div><label className="mb-1 block text-xs font-medium text-gray-700">Potência Pico (Wp)</label>
                    <input type="number" step="any" value={form.potencia_pico_wp ?? ''}
                      onChange={e => set('potencia_pico_wp', e.target.value ? parseFloat(e.target.value) : undefined)}
                      className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm" /></div>
                  <div><label className="mb-1 block text-xs font-medium text-gray-700">Eficiência (%)</label>
                    <input type="number" step="any" value={form.eficiencia_pct ?? ''}
                      onChange={e => set('eficiencia_pct', e.target.value ? parseFloat(e.target.value) : undefined)}
                      className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm" /></div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-gray-700">Voc (V)</label>
                    <input type="number" step="any" value={form.voc_v ?? ''}
                      onChange={e => set('voc_v', e.target.value ? parseFloat(e.target.value) : undefined)}
                      className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm" />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-gray-700">Vmp (V)</label>
                    <input type="number" step="any" value={form.vmp_v ?? ''}
                      onChange={e => set('vmp_v', e.target.value ? parseFloat(e.target.value) : undefined)}
                      className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm" />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-gray-700">Isc (A)</label>
                    <input type="number" step="any" value={form.isc_a ?? ''}
                      onChange={e => set('isc_a', e.target.value ? parseFloat(e.target.value) : undefined)}
                      className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm" />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-gray-700">Imp (A)</label>
                    <input type="number" step="any" value={form.imp_a ?? ''}
                      onChange={e => set('imp_a', e.target.value ? parseFloat(e.target.value) : undefined)}
                      className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm" />
                  </div>
                </div>
              )}
              {form.tipo === 'inversor_solar' && (
                <div className="grid grid-cols-2 gap-3">
                  <div><label className="mb-1 block text-xs font-medium text-gray-700">Potência Nominal (kW)</label>
                    <input type="number" step="any" value={form.potencia_nominal_kw ?? ''}
                      onChange={e => set('potencia_nominal_kw', e.target.value ? parseFloat(e.target.value) : undefined)}
                      className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm" /></div>
                  <div><label className="mb-1 block text-xs font-medium text-gray-700">MPPT Mín (V)</label>
                    <input type="number" step="any" value={form.mppt_min_v ?? ''}
                      onChange={e => set('mppt_min_v', e.target.value ? parseFloat(e.target.value) : undefined)}
                      className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm" /></div>
                  <div><label className="mb-1 block text-xs font-medium text-gray-700">MPPT Máx (V)</label>
                    <input type="number" step="any" value={form.mppt_max_v ?? ''}
                      onChange={e => set('mppt_max_v', e.target.value ? parseFloat(e.target.value) : undefined)}
                      className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm" /></div>
                  <div><label className="mb-1 block text-xs font-medium text-gray-700">Fase</label>
                    <select value={form.fase ?? ''} onChange={e => set('fase', e.target.value || undefined)}
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm">
                      <option value="">—</option>
                      <option value="monofasico">Monofásico</option>
                      <option value="trifasico">Trifásico</option>
                    </select></div>
                </div>
              )}
              <div><label className="mb-1 block text-xs font-medium text-gray-700">Preço (R$)</label>
                <input type="number" step="any" value={form.preco}
                  onChange={e => set('preco', parseFloat(e.target.value))} required
                  className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm" /></div>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.disponivel} onChange={e => set('disponivel', e.target.checked)} />
                Disponível
              </label>
              {error && <p className="text-sm text-red-600">{error}</p>}
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setShowForm(false)}
                  className="rounded-lg border border-gray-300 px-4 py-2 text-sm hover:bg-gray-50">Cancelar</button>
                <button type="submit"
                  className="rounded-lg bg-primary px-4 py-2 text-sm text-white hover:bg-primary-dark">
                  {editing ? 'Salvar' : 'Criar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-sm rounded-xl bg-white p-6 shadow-xl">
            <h2 className="mb-2 text-lg font-bold text-gray-800">Excluir produto?</h2>
            <p className="mb-5 text-sm text-gray-600">
              Tem certeza que deseja excluir <strong>{confirmDelete.marca} {confirmDelete.modelo}</strong>?
              Esta ação não pode ser desfeita.
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setConfirmDelete(null)}
                className="rounded-lg border border-gray-300 px-4 py-2 text-sm hover:bg-gray-50">
                Cancelar
              </button>
              <button onClick={handleDelete}
                disabled={deleteMutation.isPending}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm text-white hover:bg-red-700 disabled:opacity-50">
                {deleteMutation.isPending ? 'Excluindo...' : 'Excluir'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
