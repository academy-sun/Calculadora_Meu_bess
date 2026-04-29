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
                <th className="w-10 px-4 py-3 text-left">
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
