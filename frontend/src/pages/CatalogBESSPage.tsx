import { useState } from 'react'
import { useBESSProducts, useCreateBESS, useUpdateBESS } from '@/hooks/useCatalog'
import type { ProductBESS } from '@/types'
import { PlusCircle } from 'lucide-react'

type BESSForm = Omit<ProductBESS, 'id' | 'atualizado_em'>

const EMPTY_FORM: BESSForm = {
  marca: '', modelo: '', sku: '', tipo: 'bateria', disponivel: true, preco: 0,
  pot_ca_max_eps_kva: undefined,
}

export function CatalogBESSPage() {
  const { data: products, isLoading } = useBESSProducts()
  const createMutation = useCreateBESS()
  const updateMutation = useUpdateBESS()

  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<ProductBESS | null>(null)
  const [form, setForm] = useState<BESSForm>(EMPTY_FORM)
  const [error, setError] = useState<string | null>(null)

  function openCreate() { setForm(EMPTY_FORM); setEditing(null); setShowForm(true) }
  function openEdit(p: ProductBESS) {
    const { id: _id, atualizado_em: _at, ...rest } = p
    setForm(rest); setEditing(p); setShowForm(true)
  }

  function set(field: keyof BESSForm, value: unknown) {
    setForm(prev => ({ ...prev, [field]: value }))
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

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Catálogo BESS</h1>
          <p className="text-sm text-gray-500">Baterias e Inversores Híbridos</p>
        </div>
        <button onClick={openCreate}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm text-white hover:bg-primary-dark">
          <PlusCircle size={16} /> Novo Produto
        </button>
      </div>

      {isLoading && <p className="text-gray-500">Carregando...</p>}

      {products && (
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs font-semibold uppercase text-gray-500">
              <tr>
                <th className="px-4 py-3 text-left">Marca / Modelo</th>
                <th className="px-4 py-3 text-left">SKU</th>
                <th className="px-4 py-3 text-left">Tipo</th>
                <th className="px-4 py-3 text-right">P_EPS (kVA)</th>
                <th className="px-4 py-3 text-right">Preço (R$)</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {products.map(p => (
                <tr key={p.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3"><p className="font-medium">{p.marca}</p><p className="text-xs text-gray-500">{p.modelo}</p></td>
                  <td className="px-4 py-3 font-mono text-xs">{p.sku}</td>
                  <td className="px-4 py-3 capitalize">{p.tipo.replace(/_/g, ' ')}</td>
                  <td className="px-4 py-3 text-right">{p.pot_ca_max_eps_kva ? `${p.pot_ca_max_eps_kva} kVA` : '—'}</td>
                  <td className="px-4 py-3 text-right">{p.preco.toLocaleString('pt-BR')}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs ${p.disponivel ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                      {p.disponivel ? 'Disponível' : 'Inativo'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button onClick={() => openEdit(p)} className="text-xs text-primary hover:underline">Editar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl bg-white p-6 shadow-xl">
            <h2 className="mb-4 text-lg font-bold">{editing ? 'Editar' : 'Novo'} Produto BESS</h2>
            <form onSubmit={handleSave} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <FField label="Marca" value={form.marca} onChange={v => set('marca', v)} required />
                <FField label="Modelo" value={form.modelo} onChange={v => set('modelo', v)} required />
              </div>
              <FField label="SKU" value={form.sku} onChange={v => set('sku', v)} required />
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-700">Tipo</label>
                <select value={form.tipo} onChange={e => set('tipo', e.target.value as ProductBESS['tipo'])}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm">
                  <option value="bateria">Bateria</option>
                  <option value="inversor_hibrido">Inversor Híbrido</option>
                  <option value="bess_comercial">BESS Comercial</option>
                </select>
              </div>
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
              </div>
              <NField label="Preço (R$)" value={form.preco} onChange={v => set('preco', v ?? 0)} required />
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
    </div>
  )
}

function FField({ label, value, onChange, required }: { label: string; value: string; onChange: (v: string) => void; required?: boolean }) {
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
