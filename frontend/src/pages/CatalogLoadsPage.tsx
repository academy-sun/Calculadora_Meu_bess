import { useState } from 'react'
import { useStandardLoads, useCreateLoad } from '@/hooks/useCatalog'
import type { StandardLoad } from '@/types'
import { PlusCircle } from 'lucide-react'

type LoadForm = Omit<StandardLoad, 'id'>

const EMPTY_FORM: LoadForm = {
  nome: '', categoria: '', potencia_w: 0, fator_potencia: 1.0, tensao: '220V', fase: 'monofasico', ativo: true,
}

export function CatalogLoadsPage() {
  const { data: loads, isLoading } = useStandardLoads()
  const createMutation = useCreateLoad()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<LoadForm>(EMPTY_FORM)
  const [error, setError] = useState<string | null>(null)

  function set(field: keyof LoadForm, value: unknown) { setForm(prev => ({ ...prev, [field]: value })) }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault(); setError(null)
    try { await createMutation.mutateAsync(form); setShowForm(false); setForm(EMPTY_FORM) }
    catch (err: unknown) { setError(err instanceof Error ? err.message : 'Erro ao salvar') }
  }

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Cargas Padrão</h1>
          <p className="text-sm text-gray-500">Biblioteca de cargas para dimensionamento</p>
        </div>
        <button onClick={() => setShowForm(true)}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm text-white hover:bg-primary-dark">
          <PlusCircle size={16} /> Nova Carga
        </button>
      </div>

      {isLoading && <p className="text-gray-500">Carregando...</p>}

      {loads && (
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs font-semibold uppercase text-gray-500">
              <tr>
                <th className="px-4 py-3 text-left">Nome</th>
                <th className="px-4 py-3 text-left">Categoria</th>
                <th className="px-4 py-3 text-right">Potência (W)</th>
                <th className="px-4 py-3 text-left">Tensão</th>
                <th className="px-4 py-3 text-left">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loads.map(l => (
                <tr key={l.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium">{l.nome}</td>
                  <td className="px-4 py-3 text-gray-500">{l.categoria}</td>
                  <td className="px-4 py-3 text-right">{l.potencia_w}</td>
                  <td className="px-4 py-3">{l.tensao} · {l.fase}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs ${l.ativo ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                      {l.ativo ? 'Ativa' : 'Inativa'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h2 className="mb-4 text-lg font-bold">Nova Carga Padrão</h2>
            <form onSubmit={handleSave} className="space-y-3">
              <div><label className="mb-1 block text-xs font-medium text-gray-700">Nome</label>
                <input type="text" value={form.nome} onChange={e => set('nome', e.target.value)} required
                  className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm" /></div>
              <div><label className="mb-1 block text-xs font-medium text-gray-700">Categoria</label>
                <input type="text" value={form.categoria} onChange={e => set('categoria', e.target.value)} required
                  placeholder="ex: Climatização"
                  className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm" /></div>
              <div><label className="mb-1 block text-xs font-medium text-gray-700">Potência (W)</label>
                <input type="number" step="any" value={form.potencia_w}
                  onChange={e => set('potencia_w', parseFloat(e.target.value))} required
                  className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm" /></div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="mb-1 block text-xs font-medium text-gray-700">Tensão</label>
                  <select value={form.tensao} onChange={e => set('tensao', e.target.value)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm">
                    <option>127V</option><option>220V</option><option>380V</option>
                  </select></div>
                <div><label className="mb-1 block text-xs font-medium text-gray-700">Fase</label>
                  <select value={form.fase} onChange={e => set('fase', e.target.value as StandardLoad['fase'])}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm">
                    <option value="monofasico">Monofásico</option>
                    <option value="trifasico">Trifásico</option>
                  </select></div>
              </div>
              <div><label className="mb-1 block text-xs font-medium text-gray-700">Fator de Potência</label>
                <input type="number" step="0.01" min="0.1" max="1" value={form.fator_potencia}
                  onChange={e => set('fator_potencia', parseFloat(e.target.value))}
                  className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm" /></div>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.ativo} onChange={e => set('ativo', e.target.checked)} />
                Ativa
              </label>
              {error && <p className="text-sm text-red-600">{error}</p>}
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setShowForm(false)}
                  className="rounded-lg border border-gray-300 px-4 py-2 text-sm hover:bg-gray-50">Cancelar</button>
                <button type="submit"
                  className="rounded-lg bg-primary px-4 py-2 text-sm text-white hover:bg-primary-dark">Criar</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
