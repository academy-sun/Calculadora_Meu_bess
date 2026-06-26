import { useMemo, useState } from 'react'
import { X } from 'lucide-react'
import { useCreateLoad } from '@/hooks/useCatalog'
import type { StandardLoad } from '@/types'

export type LoadRowInput = {
  nome: string
  categoria: string
  qtd: number
  pnom_w: number
  fp: number
  fd: number
  ip_in: number
  tdia_h: number
  tensao: string
  fase: string
}

type Props = {
  loads: StandardLoad[]
  defaultTensao: string
  onInsert: (row: LoadRowInput) => void
  onClose: () => void
}

const EMPTY = {
  nome: '', categoria: '', potencia_w: '', tdia_horas: '4',
  fator_potencia: '1', fator_demanda: '1', ip_in: '1', tensao: '220',
  fase: 'monofasico', qtd: '1',
}

export function AddLoadDialog({ loads, defaultTensao, onInsert, onClose }: Props) {
  const createLoad = useCreateLoad()
  const [search, setSearch] = useState('')
  const [open, setOpen] = useState(true)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [f, setF] = useState({ ...EMPTY, tensao: defaultTensao })
  const [error, setError] = useState<string | null>(null)

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    const base = loads.filter(l => l.ativo)
    if (!q) return base.slice(0, 50)
    return base.filter(l => l.nome.toLowerCase().includes(q)).slice(0, 50)
  }, [loads, search])

  // Carga "nova" = nenhuma do catálogo com o mesmo nome.
  const isNova = !loads.some(l => l.nome.trim().toLowerCase() === f.nome.trim().toLowerCase())

  function pick(l: StandardLoad) {
    setSelectedId(l.id)
    setSearch(l.nome)
    setOpen(false)
    setF({
      nome: l.nome,
      categoria: l.categoria ?? '',
      potencia_w: String(l.potencia_w ?? ''),
      tdia_horas: String(l.tdia_horas ?? 4),
      fator_potencia: String(l.fator_potencia ?? 1),
      fator_demanda: String(l.fator_demanda ?? 1),
      ip_in: String(l.ip_in ?? 1),
      tensao: l.tensao || defaultTensao,
      fase: l.fase ?? 'monofasico',
      qtd: '1',
    })
  }

  function set(k: keyof typeof f, v: string) {
    setF(prev => ({ ...prev, [k]: v }))
    if (k === 'nome') setSelectedId(null)
  }

  async function handleInsert() {
    setError(null)
    if (!f.nome.trim()) { setError('Informe o nome da carga.'); return }
    const num = (s: string) => parseFloat(s) || 0
    const row: LoadRowInput = {
      nome: f.nome.trim(),
      categoria: f.categoria.trim(),
      qtd: Math.max(1, Math.round(num(f.qtd))),
      pnom_w: num(f.potencia_w),
      fp: num(f.fator_potencia) || 1,
      fd: num(f.fator_demanda) || 1,
      ip_in: num(f.ip_in) || 1,
      tdia_h: num(f.tdia_horas),
      tensao: f.tensao,
      fase: f.fase,
    }
    try {
      if (isNova) {
        await createLoad.mutateAsync({
          nome: row.nome, categoria: row.categoria || 'Geral',
          potencia_w: row.pnom_w, fator_potencia: row.fp, fator_demanda: row.fd,
          tdia_horas: row.tdia_h, ip_in: row.ip_in, tensao: row.tensao,
          fase: row.fase as 'monofasico' | 'trifasico', ativo: true,
        })
      }
      onInsert(row)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao inserir carga')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-bold">Adicionar carga</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
        </div>

        {/* Combobox: busca no catálogo ou digita nova */}
        <div className="relative mb-4">
          <label className="mb-1 block text-xs font-medium text-gray-700">Equipamento</label>
          <input
            value={search}
            onChange={e => { setSearch(e.target.value); set('nome', e.target.value); setOpen(true) }}
            onFocus={() => setOpen(true)}
            placeholder="Buscar no catálogo ou digitar nova carga…"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
          />
          {open && filtered.length > 0 && (
            <div className="absolute z-10 mt-1 max-h-52 w-full overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-lg">
              {filtered.map(l => (
                <button key={l.id} type="button" onClick={() => pick(l)}
                  className="block w-full px-3 py-1.5 text-left text-sm hover:bg-gray-50">
                  {l.nome} <span className="text-xs text-gray-400">({l.potencia_w} W)</span>
                </button>
              ))}
            </div>
          )}
          {isNova && f.nome.trim() && (
            <p className="mt-1 text-xs text-amber-600">Nova carga — será adicionada ao catálogo.</p>
          )}
        </div>

        {/* Campos editáveis */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <DField label="Categoria" value={f.categoria} onChange={v => set('categoria', v)} />
          <DField label="Quantidade" value={f.qtd} onChange={v => set('qtd', v)} type="number" />
          <DField label="Potência (W)" value={f.potencia_w} onChange={v => set('potencia_w', v)} type="number" />
          <DField label="Uso (h/dia)" value={f.tdia_horas} onChange={v => set('tdia_horas', v)} type="number" />
          <DField label="Fator de potência" value={f.fator_potencia} onChange={v => set('fator_potencia', v)} type="number" />
          <DField label="Fator de demanda" value={f.fator_demanda} onChange={v => set('fator_demanda', v)} type="number" />
          <DField label="IP/IN (partida)" value={f.ip_in} onChange={v => set('ip_in', v)} type="number" />
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-700">Tensão</label>
            <select value={f.tensao} onChange={e => set('tensao', e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-2 py-1.5 text-sm">
              <option value="127">127 V</option>
              <option value="220">220 V</option>
              <option value="380">380 V</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-700">Fase</label>
            <select value={f.fase} onChange={e => set('fase', e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-2 py-1.5 text-sm">
              <option value="monofasico">Monofásico</option>
              <option value="trifasico">Trifásico</option>
            </select>
          </div>
        </div>

        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg border border-gray-300 px-4 py-2 text-sm hover:bg-gray-50">
            Cancelar
          </button>
          <button onClick={handleInsert} disabled={createLoad.isPending}
            className="rounded-lg bg-primary px-4 py-2 text-sm text-white hover:bg-primary-dark disabled:opacity-50">
            {createLoad.isPending ? 'Salvando…' : 'Inserir'}
          </button>
        </div>
      </div>
    </div>
  )
}

function DField({ label, value, onChange, type = 'text' }: {
  label: string; value: string; onChange: (v: string) => void; type?: string
}) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-gray-700">{label}</label>
      <input type={type} step="any" value={value} onChange={e => onChange(e.target.value)}
        className="w-full rounded-lg border border-gray-300 px-2 py-1.5 text-sm focus:border-primary focus:outline-none" />
    </div>
  )
}
