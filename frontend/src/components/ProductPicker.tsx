import { useEffect, useState } from 'react'
import { X, Search, SlidersHorizontal } from 'lucide-react'
import { useProducts } from '@/hooks/useCatalog'
import type { KitItem, MeuBESSProduct, ProductFilters, TipoProduto } from '@/types'

const TIPOS: { value: TipoProduto | ''; label: string }[] = [
  { value: '', label: 'Todos os tipos' },
  { value: 'bateria', label: 'Bateria' },
  { value: 'inversor_hibrido', label: 'Inversor híbrido' },
  { value: 'inversor_string', label: 'Inversor string' },
  { value: 'modulo_fv', label: 'Módulo FV' },
  { value: 'acessorio', label: 'Acessório' },
]

/** Dialog para adicionar um produto ao kit, com os mesmos filtros do catálogo (backend). */
export function ProductPicker({ onAdd, onClose }: { onAdd: (item: KitItem) => void; onClose: () => void }) {
  const [titulo, setTitulo] = useState('')
  const [tipo, setTipo] = useState<TipoProduto | ''>('')
  const [marca, setMarca] = useState('')
  const [potenciaMin, setPotenciaMin] = useState('')
  const [potenciaMax, setPotenciaMax] = useState('')
  const [somenteAtivos, setSomenteAtivos] = useState(true)
  const [showFiltros, setShowFiltros] = useState(false)

  // debounce simples da busca por texto/filtros antes de bater no backend
  const [filters, setFilters] = useState<ProductFilters>({ active: true })
  useEffect(() => {
    const t = setTimeout(() => {
      setFilters({
        titulo: titulo || undefined,
        tipo: tipo || undefined,
        marca: marca || undefined,
        potencia_min: potenciaMin ? parseFloat(potenciaMin) : undefined,
        potencia_max: potenciaMax ? parseFloat(potenciaMax) : undefined,
        active: somenteAtivos ? true : undefined,
      })
    }, 300)
    return () => clearTimeout(t)
  }, [titulo, tipo, marca, potenciaMin, potenciaMax, somenteAtivos])

  const { data: produtos = [], isLoading } = useProducts(filters)
  const listados = produtos.filter(p => (p.price ?? 0) > 0)

  function add(p: MeuBESSProduct) {
    const preco = p.price ?? 0
    const tipoEfetivo = (p.tipo_manual ?? p.tipo_auto ?? 'item') as string
    const isBateria = tipoEfetivo === 'bateria'
    onAdd({
      nome: p.title ?? p.meubess_id,
      tipo: tipoEfetivo,
      qtd: 1,
      preco_unitario: preco,
      preco_total: preco,
      // bateria
      energia_unit_kwh: isBateria ? p.usable_capacity_kwh : undefined,
      corrente_pico_a: isBateria ? (p.peak_discharge_current_a ?? p.max_continuous_current_a) : undefined,
      tensao_v: isBateria ? p.nominal_voltage_v : undefined,
      // inversor
      potencia_inversao_kw: !isBateria ? (p.max_eps_power ?? p.max_output_power ?? p.power) : undefined,
      potencia_pico_kw: !isBateria ? p.peak_power_kw : undefined,
      corrente_entrada_a: !isBateria ? p.battery_input_max_current_a : undefined,
      entradas_bateria: !isBateria ? p.battery_inputs : undefined,
    })
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4 backdrop-blur-sm">
      <div className="flex max-h-[85vh] w-full max-w-2xl flex-col rounded-2xl bg-white shadow-card ring-1 ring-ink/10">
        <div className="flex items-center justify-between border-b border-ink/10 px-5 py-4">
          <h3 className="font-display text-base font-semibold">Adicionar item ao kit</h3>
          <button onClick={onClose} className="text-ink/40 hover:text-ink"><X size={18} /></button>
        </div>

        <div className="space-y-3 border-b border-ink/10 px-5 py-3">
          <div className="flex items-center gap-2">
            <div className="flex flex-1 items-center gap-2 rounded-xl border border-ink/15 px-3 py-2 focus-within:border-primary">
              <Search size={16} className="text-ink/30" />
              <input autoFocus value={titulo} onChange={e => setTitulo(e.target.value)}
                placeholder="Buscar produto por nome…"
                className="w-full bg-transparent text-sm outline-none placeholder:text-ink/30" />
            </div>
            <button type="button" onClick={() => setShowFiltros(v => !v)}
              className={`flex items-center gap-1.5 rounded-xl border px-3 py-2 text-sm font-medium transition ${
                showFiltros ? 'border-primary bg-primary/5 text-primary' : 'border-ink/15 text-ink/60 hover:border-ink/30'
              }`}>
              <SlidersHorizontal size={15} /> Filtros
            </button>
          </div>

          {showFiltros && (
            <div className="grid grid-cols-2 gap-3 rounded-xl bg-paper/60 p-3 sm:grid-cols-4">
              <div className="col-span-2 sm:col-span-1">
                <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink/45">Tipo</label>
                <select value={tipo} onChange={e => setTipo(e.target.value as TipoProduto | '')}
                  className="w-full rounded-lg border border-ink/15 bg-white px-2 py-1.5 text-sm focus:border-primary focus:outline-none">
                  {TIPOS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              <div className="col-span-2 sm:col-span-1">
                <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink/45">Marca</label>
                <input value={marca} onChange={e => setMarca(e.target.value)} placeholder="ex: WEG"
                  className="w-full rounded-lg border border-ink/15 bg-white px-2 py-1.5 text-sm focus:border-primary focus:outline-none" />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink/45">Potência mín. (kW)</label>
                <input type="number" step="any" min={0} value={potenciaMin} onChange={e => setPotenciaMin(e.target.value)}
                  className="w-full rounded-lg border border-ink/15 bg-white px-2 py-1.5 text-sm focus:border-primary focus:outline-none" />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink/45">Potência máx. (kW)</label>
                <input type="number" step="any" min={0} value={potenciaMax} onChange={e => setPotenciaMax(e.target.value)}
                  className="w-full rounded-lg border border-ink/15 bg-white px-2 py-1.5 text-sm focus:border-primary focus:outline-none" />
              </div>
              <label className="col-span-2 flex items-center gap-2 text-sm text-ink/70 sm:col-span-4">
                <input type="checkbox" checked={somenteAtivos} onChange={e => setSomenteAtivos(e.target.checked)}
                  className="rounded border-ink/30 text-primary focus:ring-primary" />
                Somente produtos ativos
              </label>
            </div>
          )}
        </div>

        <div className="flex-1 overflow-y-auto px-2 py-2">
          {isLoading ? (
            <p className="px-3 py-6 text-center text-sm text-ink/40">Carregando catálogo…</p>
          ) : listados.length === 0 ? (
            <p className="px-3 py-6 text-center text-sm text-ink/40">Nenhum produto encontrado.</p>
          ) : listados.map(p => (
            <button key={p.meubess_id} onClick={() => add(p)}
              className="flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-left hover:bg-paper">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{p.title}</p>
                <p className="text-xs text-ink/40">{p.marca} · {p.tipo_manual ?? p.tipo_auto}</p>
              </div>
              <span className="shrink-0 font-mono text-sm tabular-nums text-ink/70">
                {(p.price ?? 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
