import { useMemo, useState } from 'react'
import { X, Search } from 'lucide-react'
import { useProducts } from '@/hooks/useCatalog'
import type { KitItem, MeuBESSProduct } from '@/types'

/** Dialog para adicionar um produto ao kit, buscando no catálogo da réplica. */
export function ProductPicker({ onAdd, onClose }: { onAdd: (item: KitItem) => void; onClose: () => void }) {
  const { data: produtos = [], isLoading } = useProducts({ active: true })
  const [q, setQ] = useState('')

  const filtrados = useMemo(() => {
    const s = q.trim().toLowerCase()
    const base = produtos.filter(p => (p.price ?? 0) > 0)
    if (!s) return base.slice(0, 40)
    return base.filter(p =>
      (p.title ?? '').toLowerCase().includes(s) || (p.marca ?? '').toLowerCase().includes(s),
    ).slice(0, 40)
  }, [produtos, q])

  function add(p: MeuBESSProduct) {
    const preco = p.price ?? 0
    onAdd({
      nome: p.title ?? p.meubess_id,
      tipo: (p.tipo_manual ?? p.tipo_auto ?? 'item') as string,
      qtd: 1,
      preco_unitario: preco,
      preco_total: preco,
      energia_unit_kwh: p.usable_capacity_kwh,
      potencia_unit_kw: p.peak_power_kw,
    })
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4 backdrop-blur-sm">
      <div className="flex max-h-[80vh] w-full max-w-xl flex-col rounded-2xl bg-white shadow-card ring-1 ring-ink/10">
        <div className="flex items-center justify-between border-b border-ink/10 px-5 py-4">
          <h3 className="font-display text-base font-semibold">Adicionar item ao kit</h3>
          <button onClick={onClose} className="text-ink/40 hover:text-ink"><X size={18} /></button>
        </div>
        <div className="border-b border-ink/10 px-5 py-3">
          <div className="flex items-center gap-2 rounded-xl border border-ink/15 px-3 py-2 focus-within:border-primary">
            <Search size={16} className="text-ink/30" />
            <input autoFocus value={q} onChange={e => setQ(e.target.value)}
              placeholder="Buscar produto por nome ou marca…"
              className="w-full bg-transparent text-sm outline-none placeholder:text-ink/30" />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto px-2 py-2">
          {isLoading ? (
            <p className="px-3 py-6 text-center text-sm text-ink/40">Carregando catálogo…</p>
          ) : filtrados.length === 0 ? (
            <p className="px-3 py-6 text-center text-sm text-ink/40">Nenhum produto encontrado.</p>
          ) : filtrados.map(p => (
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
