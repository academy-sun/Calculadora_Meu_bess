import { useState } from 'react'
import { useStandardLoads, useCreateLoad, useUpdateLoad, useDeleteLoad } from '@/hooks/useCatalog'
import type { StandardLoad } from '@/types'
import { Trash2 } from 'lucide-react'

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
  const deleteMutation = useDeleteLoad()

  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<StandardLoad | null>(null)
  const [form, setForm] = useState<LoadForm>(EMPTY_FORM)
  const [search, setSearch] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<StandardLoad | null>(null)

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

      {error && !showForm && (
        <div className="mb-4 rounded-lg bg-red-50 px-4 py-2 text-sm text-red-600">{error}</div>
      )}

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
                    <div className="flex items-center gap-3">
                      <button onClick={() => openEdit(l)} className="text-xs text-primary hover:underline">Editar</button>
                      <button onClick={() => setConfirmDelete(l)}
                        className="text-gray-400 hover:text-red-600 transition-colors">
                        <Trash2 size={14} />
                      </button>
                    </div>
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

      {/* Edit / Create Modal */}
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

      {/* Delete Confirmation Modal */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-sm rounded-xl bg-white p-6 shadow-xl">
            <h2 className="mb-2 text-lg font-bold text-gray-800">Excluir carga?</h2>
            <p className="mb-5 text-sm text-gray-600">
              Tem certeza que deseja excluir <strong>{confirmDelete.nome}</strong>?
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
