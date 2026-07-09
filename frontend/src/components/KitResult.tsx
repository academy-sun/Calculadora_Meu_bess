import { useState } from 'react'
import type { ElementType } from 'react'
import { AlertTriangle, Plus, Trash2, Battery, Gauge, Zap, Percent, CheckCircle2 } from 'lucide-react'
import type { KitInfo, KitItem, SolarDimensionamento } from '@/types'
import { ProductPicker } from '@/components/ProductPicker'

const brl = (v: number) => v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
const num = (v: number, d = 1) => v.toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d })

/**
 * Réplica exata de `_distribuir` + `_pico_dc_kw` em kit_builder.py (backend): distribui as
 * baterias uniformemente entre as entradas (1 slot por entrada física, cada um com seu próprio
 * limite de corrente do inversor a que pertence), trunca a corrente por entrada e converte em kW.
 * Mantida idêntica ao motor — qualquer aproximação aqui pode causar erro de dimensionamento.
 */
export function calcPotenciaPartidaKw(itens: KitItem[]): number {
  const inversores = itens.filter(it => it.tipo === 'inversor' && it.potencia_pico_kw != null)
  const baterias = itens.filter(it => it.tipo === 'bateria' && it.corrente_pico_a != null && it.tensao_v != null)
  const picoInvTotal = inversores.reduce((s, inv) => s + (inv.potencia_pico_kw ?? 0) * inv.qtd, 0)
  if (inversores.length === 0 || baterias.length === 0) return picoInvTotal

  const slots: number[] = []
  for (const inv of inversores) {
    const nEntradas = (inv.entradas_bateria ?? 0) * inv.qtd
    for (let i = 0; i < nEntradas; i++) slots.push(inv.corrente_entrada_a ?? 0)
  }
  if (slots.length === 0) return picoInvTotal

  const nBaterias = baterias.reduce((s, b) => s + b.qtd, 0)
  const correntePico = baterias[0].corrente_pico_a ?? 0
  const tensao = baterias[0].tensao_v ?? 0

  const base = Math.floor(nBaterias / slots.length)
  const extra = nBaterias % slots.length
  const dist = slots.map((_, i) => base + (i < extra ? 1 : 0))

  const totalA = dist.reduce((s, n, i) => s + (n > 0 ? Math.min(n * correntePico, slots[i]) : 0), 0)
  const picoDc = (totalA * tensao) / 1000

  return Math.min(picoDc, picoInvTotal)
}

interface KitResultProps {
  kit: KitInfo
  itens: KitItem[]
  onItensChange: (itens: KitItem[]) => void
  titulo: string
  subtitulo?: string
  energiaNecessariaKwh?: number
  kwpInstalado?: number
  solar?: SolarDimensionamento | null
  editable?: boolean
  collapsible?: boolean
  defaultOpen?: boolean
  onEscolher?: () => void
  escolhendo?: boolean
}

export function KitResult({
  kit, itens, onItensChange, titulo, subtitulo, energiaNecessariaKwh, kwpInstalado, solar,
  editable = true, collapsible = false, defaultOpen = true, onEscolher, escolhendo,
}: KitResultProps) {
  const [showPicker, setShowPicker] = useState(false)
  const [open, setOpen] = useState(defaultOpen)

  const patch = (i: number, p: Partial<KitItem>) =>
    onItensChange(itens.map((it, idx) => (idx === i ? { ...it, ...p } : it)))
  const remove = (i: number) => onItensChange(itens.filter((_, idx) => idx !== i))
  const addItem = (it: KitItem) => onItensChange([...itens, it])

  // ── Métricas recalculadas ao vivo a partir do kit editado ───────────────────
  const energiaTotal = itens.reduce((s, it) => s + (it.energia_unit_kwh ?? 0) * it.qtd, 0)

  const coberturaPct = energiaNecessariaKwh && energiaNecessariaKwh > 0
    ? (energiaTotal / energiaNecessariaKwh) * 100 : null

  const potenciaInversao = itens.reduce((s, it) => s + (it.potencia_inversao_kw ?? 0) * it.qtd, 0)
  const potenciaPartida = calcPotenciaPartidaKw(itens)

  const totalKit = itens.reduce((s, it) => s + it.preco_unitario * it.qtd, 0)

  const body = (
    <>
      {/* Métricas-chave (recalculadas ao vivo conforme o kit é editado) */}
      <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric icon={Battery} label="Energia total" value={num(energiaTotal, 2)} unit="kWh" />
        <Metric icon={Percent} label="Cobertura de energia"
          value={coberturaPct != null ? num(coberturaPct, 1) : '—'} unit="%" accent
          warn={coberturaPct != null && coberturaPct < 100} />
        <Metric icon={Zap} label="Potência máx. de partida" value={num(potenciaPartida, 1)} unit="kW" />
        <Metric icon={Gauge} label="Potência total de inversão" value={num(potenciaInversao, 1)} unit="kW" />
      </div>

      {/* Tabela de itens (editável quando editable=true) */}
      <div className="overflow-hidden rounded-2xl border border-ink/10 bg-white shadow-card">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-ink/10 bg-ink/[0.03] text-left text-[11px] font-semibold uppercase tracking-wider text-ink/45">
              <th className="px-4 py-3">Item</th>
              <th className="px-4 py-3 w-20 text-center">Qtd</th>
              <th className="px-4 py-3 w-36 text-right">Preço unit.</th>
              <th className="px-4 py-3 w-36 text-right">Total</th>
              {editable && <th className="px-2 py-3 w-10" />}
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
                  {editable ? (
                    <input type="number" min={1} value={it.qtd}
                      onChange={e => patch(i, { qtd: Math.max(1, parseInt(e.target.value) || 1) })}
                      className="w-16 rounded-lg border border-ink/15 bg-paper/50 px-2 py-1 text-center font-mono text-sm tabular-nums focus:border-primary focus:outline-none" />
                  ) : (
                    <span className="font-mono text-sm tabular-nums text-ink/80">{it.qtd}</span>
                  )}
                </td>
                <td className="px-4 py-3 text-right">
                  {editable ? (
                    <input type="number" step="any" min={0} value={it.preco_unitario}
                      onChange={e => patch(i, { preco_unitario: parseFloat(e.target.value) || 0 })}
                      className="w-28 rounded-lg border border-ink/15 bg-paper/50 px-2 py-1 text-right font-mono text-sm tabular-nums focus:border-primary focus:outline-none" />
                  ) : (
                    <span className="font-mono text-sm tabular-nums text-ink/80">{brl(it.preco_unitario)}</span>
                  )}
                </td>
                <td className="px-4 py-3 text-right font-mono tabular-nums text-ink/80">{brl(it.preco_unitario * it.qtd)}</td>
                {editable && (
                  <td className="px-2 py-3 text-center">
                    <button onClick={() => remove(i)} className="text-ink/25 opacity-0 transition hover:text-red-500 group-hover:opacity-100">
                      <Trash2 size={15} />
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
          <tfoot>
            {editable && (
              <tr className="border-t border-ink/10">
                <td colSpan={5} className="px-4 py-2.5">
                  <button onClick={() => setShowPicker(true)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-dashed border-primary/40 px-3 py-1.5 text-sm font-medium text-primary transition hover:bg-primary/5">
                    <Plus size={15} /> Adicionar item
                  </button>
                </td>
              </tr>
            )}
            <tr className="border-t-2 border-ink/15 bg-ink/[0.03]">
              <td colSpan={3} className="px-4 py-3 text-right font-semibold uppercase tracking-wide text-ink/60 text-xs">Total do kit</td>
              <td className="px-4 py-3 text-right font-mono text-base font-bold tabular-nums text-primary">{brl(totalKit)}</td>
              {editable && <td />}
            </tr>
          </tfoot>
        </table>
      </div>

      {onEscolher && (
        <button onClick={onEscolher} disabled={escolhendo}
          className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-white transition hover:bg-primary-dark disabled:opacity-50">
          <CheckCircle2 size={17} /> {escolhendo ? 'Salvando…' : 'Escolher este kit'}
        </button>
      )}

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
    </>
  )

  const coberturaBadge = coberturaPct != null && (
    <span className={`rounded-full px-2 py-0.5 font-mono text-xs font-semibold ${
      coberturaPct < 100 ? 'bg-accent/15 text-accent-dark' : 'bg-primary/10 text-primary'
    }`}>{num(coberturaPct, 0)}%</span>
  )

  // Modo colapsável (lista de opções de kit) — header clicável com resumo
  if (collapsible) {
    return (
      <div className="rounded-2xl border border-ink/10 bg-white shadow-card">
        <button type="button" onClick={() => setOpen(o => !o)}
          className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left">
          <div className="min-w-0">
            <p className="truncate font-display text-base font-bold text-ink">{titulo}</p>
            {subtitulo && <p className="truncate text-xs text-ink/50">{subtitulo}</p>}
          </div>
          <div className="flex shrink-0 items-center gap-3">
            {kwpInstalado ? <span className="hidden font-mono text-xs text-ink/50 sm:inline">{num(kwpInstalado, 2)} kWp</span> : null}
            {coberturaBadge}
            <span className="font-mono text-sm font-semibold tabular-nums text-primary">{brl(totalKit)}</span>
            <span className="text-sm text-ink/40">{open ? '▲' : '▼'}</span>
          </div>
        </button>
        {open && <div className="border-t border-ink/10 px-5 pb-5 pt-1">{body}</div>}
      </div>
    )
  }

  // Modo aberto (tela de cotação salva)
  return (
    <div className="mt-10">
      <div className="mb-5">
        <h2 className="font-display text-2xl font-bold tracking-tight">{titulo}</h2>
        {subtitulo && <p className="mt-0.5 text-sm text-ink/50">{subtitulo}</p>}
      </div>
      {body}
    </div>
  )
}

function Metric({ icon: Icon, label, value, unit, accent, warn }: {
  icon: ElementType; label: string; value: string; unit: string; accent?: boolean; warn?: boolean
}) {
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
