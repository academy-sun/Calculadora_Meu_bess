import { useEffect, useState } from 'react'
import type { ElementType } from 'react'
import { AlertTriangle, Plus, Trash2, Battery, Gauge, Zap, Percent } from 'lucide-react'
import type { CalculateResponse, KitItem } from '@/types'
import { ProductPicker } from '@/components/ProductPicker'

const brl = (v: number) => v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
const num = (v: number, d = 1) => v.toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d })

export function KitResult({ result }: { result: CalculateResponse }) {
  const kit = result.kit_selecionado
  const solar = result.solar_dimensionamento

  // Kit editável (quantidades, itens, preço unitário) — recalcula tudo ao vivo
  const [itens, setItens] = useState<KitItem[]>(kit?.itens ?? [])
  const [showPicker, setShowPicker] = useState(false)
  useEffect(() => { setItens(kit?.itens ?? []) }, [kit])

  if (!kit) {
    return (
      <div className="mt-10 rounded-2xl border border-dashed border-ink/15 bg-white/60 px-6 py-12 text-center">
        <p className="font-display text-lg text-ink/70">Nenhum kit compatível</p>
        <p className="mt-1 text-sm text-ink/50">Ajuste os parâmetros e busque novamente.</p>
      </div>
    )
  }

  const patch = (i: number, p: Partial<KitItem>) =>
    setItens(prev => prev.map((it, idx) => (idx === i ? { ...it, ...p } : it)))
  const remove = (i: number) => setItens(prev => prev.filter((_, idx) => idx !== i))
  const addItem = (it: KitItem) => setItens(prev => [...prev, it])

  // ── Métricas recalculadas ao vivo a partir do kit editado ───────────────────
  const energiaTotal = itens.reduce((s, it) => s + (it.energia_unit_kwh ?? 0) * it.qtd, 0)

  // Cobertura de energia: quanto o kit entrega da energia necessária (E_BAT)
  const energiaNecessaria = result.energia_necessaria_kwh ?? result.capacidade_kwh ?? 0
  const coberturaPct = energiaNecessaria > 0 ? (energiaTotal / energiaNecessaria) * 100 : null

  // Potência total de inversão = soma da potência nominal de saída dos inversores
  const potenciaInversao = itens.reduce((s, it) => s + (it.potencia_inversao_kw ?? 0) * it.qtd, 0)

  // Potência máxima de partida = pico dos inversores, LIMITADO pela bateria / corrente de entrada.
  // (a potência também pode ser limitada pela corrente da bateria ou da entrada do inversor)
  const picoInversores = itens.reduce((s, it) => s + (it.potencia_pico_kw ?? 0) * it.qtd, 0)
  const correnteBaterias = itens.reduce((s, it) => s + (it.corrente_pico_a ?? 0) * it.qtd, 0)
  const correnteEntradas = itens.reduce((s, it) => s + (it.corrente_entrada_a ?? 0) * (it.entradas_bateria ?? 0) * it.qtd, 0)
  const tensaoBat = itens.find(it => it.tensao_v)?.tensao_v ?? 0
  const limiteDcKw = tensaoBat > 0 && correnteBaterias > 0 && correnteEntradas > 0
    ? (Math.min(correnteBaterias, correnteEntradas) * tensaoBat) / 1000
    : Infinity
  const potenciaPartida = picoInversores > 0 ? Math.min(picoInversores, limiteDcKw) : 0

  const totalKit = itens.reduce((s, it) => s + it.preco_unitario * it.qtd, 0)

  return (
    <div className="mt-10">
      <div className="mb-5">
        <h2 className="font-display text-2xl font-bold tracking-tight">Kit dimensionado</h2>
      </div>

      {/* Métricas-chave (recalculadas ao vivo conforme o kit é editado) */}
      <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric icon={Battery} label="Energia total" value={num(energiaTotal, 2)} unit="kWh" />
        <Metric icon={Percent} label="Cobertura de energia"
          value={coberturaPct != null ? num(coberturaPct, 1) : '—'} unit="%" accent
          warn={coberturaPct != null && coberturaPct < 100} />
        <Metric icon={Zap} label="Potência máx. de partida" value={num(potenciaPartida, 1)} unit="kW" />
        <Metric icon={Gauge} label="Potência total de inversão" value={num(potenciaInversao, 1)} unit="kW" />
      </div>

      {/* Tabela de itens editável */}
      <div className="overflow-hidden rounded-2xl border border-ink/10 bg-white shadow-card">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-ink/10 bg-ink/[0.03] text-left text-[11px] font-semibold uppercase tracking-wider text-ink/45">
              <th className="px-4 py-3">Item</th>
              <th className="px-4 py-3 w-20 text-center">Qtd</th>
              <th className="px-4 py-3 w-36 text-right">Preço unit.</th>
              <th className="px-4 py-3 w-36 text-right">Total</th>
              <th className="px-2 py-3 w-10" />
            </tr>
          </thead>
          <tbody className="divide-y divide-ink/[0.06]">
            {itens.map((it, i) => (
              <tr key={i} className="group">
                <td className="px-4 py-3">
                  <p className="font-medium text-ink">{it.nome}</p>
                  <p className="text-xs capitalize text-ink/40">{it.tipo}</p>
                </td>
                <td className="px-4 py-3 text-center">
                  <input type="number" min={1} value={it.qtd}
                    onChange={e => patch(i, { qtd: Math.max(1, parseInt(e.target.value) || 1) })}
                    className="w-16 rounded-lg border border-ink/15 bg-paper/50 px-2 py-1 text-center font-mono text-sm tabular-nums focus:border-primary focus:outline-none" />
                </td>
                <td className="px-4 py-3 text-right">
                  <input type="number" step="any" min={0} value={it.preco_unitario}
                    onChange={e => patch(i, { preco_unitario: parseFloat(e.target.value) || 0 })}
                    className="w-28 rounded-lg border border-ink/15 bg-paper/50 px-2 py-1 text-right font-mono text-sm tabular-nums focus:border-primary focus:outline-none" />
                </td>
                <td className="px-4 py-3 text-right font-mono tabular-nums text-ink/80">{brl(it.preco_unitario * it.qtd)}</td>
                <td className="px-2 py-3 text-center">
                  <button onClick={() => remove(i)} className="text-ink/25 opacity-0 transition hover:text-red-500 group-hover:opacity-100">
                    <Trash2 size={15} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-ink/10">
              <td colSpan={5} className="px-4 py-2.5">
                <button onClick={() => setShowPicker(true)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-dashed border-primary/40 px-3 py-1.5 text-sm font-medium text-primary transition hover:bg-primary/5">
                  <Plus size={15} /> Adicionar item
                </button>
              </td>
            </tr>
            <tr className="border-t-2 border-ink/15 bg-ink/[0.03]">
              <td colSpan={3} className="px-4 py-3 text-right font-semibold uppercase tracking-wide text-ink/60 text-xs">Total do kit</td>
              <td className="px-4 py-3 text-right font-mono text-base font-bold tabular-nums text-primary">{brl(totalKit)}</td>
              <td />
            </tr>
          </tfoot>
        </table>
      </div>

      {/* Geração solar */}
      {solar && (
        <div className="mt-4 rounded-2xl border border-accent/30 bg-accent/[0.06] p-4">
          <p className="mb-2 font-display text-sm font-semibold text-accent-dark">Sistema fotovoltaico</p>
          <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-sm sm:grid-cols-3">
            <Detail label="Módulo" value={`${solar.modulo_marca} ${solar.modulo_modelo} · ${solar.modulo_wp} Wp`} />
            <Detail label="Configuração" value={`${solar.n_serie}S × ${solar.n_paralelo}P × ${solar.mppt_qty} MPPT`} />
            <Detail label="Potência instalada" value={`${solar.kwp_instalado} kWp`} />
            <Detail label="Geração / cobertura" value={`${solar.cobertura_pct}% do consumo`} />
            <Detail label="Custo dos módulos" value={brl(solar.preco_modulos_total)} />
          </div>
        </div>
      )}

      {/* Alertas */}
      {kit.alertas && kit.alertas.length > 0 && (
        <div className="mt-4 space-y-2">
          {kit.alertas.map((a, i) => (
            <div key={i} className="flex items-start gap-2 rounded-xl border border-accent/40 bg-accent/[0.08] px-3.5 py-2.5 text-sm text-accent-dark">
              <AlertTriangle size={16} className="mt-0.5 shrink-0" /> <span>{a}</span>
            </div>
          ))}
        </div>
      )}

      {showPicker && <ProductPicker onAdd={addItem} onClose={() => setShowPicker(false)} />}
    </div>
  )
}

function Metric({ icon: Icon, label, value, unit, accent, warn }: {
  icon: ElementType; label: string; value: string; unit: string; accent?: boolean; warn?: boolean
}) {
  // cobertura abaixo de 100% destaca em âmbar (subdimensionado)
  const tone = warn ? 'amber' : accent ? 'primary' : 'ink'
  const ring = tone === 'amber' ? 'border-accent/40 bg-accent/[0.06]'
    : tone === 'primary' ? 'border-primary/30 bg-primary/[0.04]' : 'border-ink/10 bg-white'
  const valColor = tone === 'amber' ? 'text-accent-dark' : tone === 'primary' ? 'text-primary' : 'text-ink'
  const iconColor = tone === 'amber' ? 'text-accent-dark' : tone === 'primary' ? 'text-primary' : ''
  return (
    <div className={`relative overflow-hidden rounded-2xl border p-5 ${ring} shadow-card`}>
      <div className="mb-3 flex items-center gap-2 text-ink/45">
        <Icon size={15} className={iconColor} />
        <span className="text-[11px] font-semibold uppercase tracking-wider">{label}</span>
      </div>
      <div className="flex items-baseline gap-1.5">
        <span className={`font-mono text-3xl font-semibold tabular-nums ${valColor}`}>{value}</span>
        <span className="font-mono text-sm text-ink/40">{unit}</span>
      </div>
    </div>
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-ink/45">{label}</p>
      <p className="font-medium text-ink/80">{value}</p>
    </div>
  )
}
