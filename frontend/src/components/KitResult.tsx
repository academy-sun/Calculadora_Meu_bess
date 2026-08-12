import { useState } from 'react'
import type { ElementType } from 'react'
import { AlertTriangle, Plus, Trash2, Battery, Gauge, Zap, Percent, CheckCircle2 } from 'lucide-react'
import type { FreteInfo, KitInfo, KitItem, SolarDimensionamento } from '@/types'
import { ProductPicker } from '@/components/ProductPicker'
import { calcPotenciaPartidaKw, energiaTotalKwh, potenciaInversaoKw } from '@/lib/kitMetrics'

const brl = (v: number) => v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
const num = (v: number, d = 1) => v.toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d })

interface KitResultProps {
  kit: KitInfo
  itens: KitItem[]
  onItensChange: (itens: KitItem[]) => void
  titulo: string
  subtitulo?: string
  energiaNecessariaKwh?: number
  kwpInstalado?: number
  solar?: SolarDimensionamento | null
  frete?: FreteInfo | null
  editable?: boolean
  collapsible?: boolean
  defaultOpen?: boolean
  onEscolher?: () => void
  escolhendo?: boolean
  escolherLabel?: string
  /** Perfil restrito: o único valor em reais que aparece é o total com frete.
   *  Some preço unitário, subtotal por item, total do kit isolado, linha de
   *  frete (com o percentual da UF) e custo dos módulos. */
  ocultarValores?: boolean
  /** Total (kit + frete) vindo do servidor depois de uma edição. No perfil
   *  restrito o preço unitário não chega aqui, então somar no cliente é
   *  impossível — quem soma é /calculate/reprecificar. */
  totalComFreteServidor?: number | null
  /** Uma reprecificação está em voo: o total mostrado é o anterior. */
  recalculando?: boolean
  /** Embed: o picker busca por API key em vez de JWT. */
  pickerPorApiKey?: boolean
}

export function KitResult({
  kit, itens, onItensChange, titulo, subtitulo, energiaNecessariaKwh, kwpInstalado, solar,
  frete, editable = true, collapsible = false, defaultOpen = true, onEscolher, escolhendo,
  escolherLabel = 'Escolher este kit',
  ocultarValores = false, totalComFreteServidor = null, recalculando = false,
  pickerPorApiKey = false,
}: KitResultProps) {
  // Quantidade, remover e adicionar seguem `editable`. Editar PREÇO exige
  // também ver preço: no perfil restrito o valor nem chega ao navegador, e
  // um campo editável ali mostraria 0,00 e gravaria 0,00 no kit.
  const editarPreco = editable && !ocultarValores
  const [showPicker, setShowPicker] = useState(false)
  const [open, setOpen] = useState(defaultOpen)

  const patch = (i: number, p: Partial<KitItem>) =>
    onItensChange(itens.map((it, idx) => (idx === i ? { ...it, ...p } : it)))
  const remove = (i: number) => onItensChange(itens.filter((_, idx) => idx !== i))
  const addItem = (it: KitItem) => onItensChange([...itens, it])

  // ── Métricas recalculadas ao vivo a partir do kit editado ───────────────────
  const energiaTotal = energiaTotalKwh(itens)

  const coberturaPct = energiaNecessariaKwh && energiaNecessariaKwh > 0
    ? (energiaTotal / energiaNecessariaKwh) * 100 : null

  const potenciaInversao = potenciaInversaoKw(itens)
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
              {!ocultarValores && <th className="px-4 py-3 w-36 text-right">Preço unit.</th>}
              {!ocultarValores && <th className="px-4 py-3 w-36 text-right">Total</th>}
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
                {!ocultarValores && (
                <td className="px-4 py-3 text-right">
                  {editarPreco ? (
                    <input type="number" step="any" min={0} value={it.preco_unitario}
                      onChange={e => patch(i, { preco_unitario: parseFloat(e.target.value) || 0 })}
                      className="w-28 rounded-lg border border-ink/15 bg-paper/50 px-2 py-1 text-right font-mono text-sm tabular-nums focus:border-primary focus:outline-none" />
                  ) : (
                    <span className="font-mono text-sm tabular-nums text-ink/80">{brl(it.preco_unitario)}</span>
                  )}
                </td>
                )}
                {!ocultarValores && (
                <td className="px-4 py-3 text-right font-mono tabular-nums text-ink/80">{brl(it.preco_unitario * it.qtd)}</td>
                )}
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
            {!ocultarValores && (
            <tr className="border-t-2 border-ink/15 bg-ink/[0.03]">
              <td colSpan={3} className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-ink/60">Total do kit</td>
              <td className="px-4 py-3 text-right font-mono text-base font-bold tabular-nums text-primary">{brl(totalKit)}</td>
              {editable && <td />}
            </tr>
            )}
            {ocultarValores && (
              <tr className="border-t-2 border-ink/15 bg-primary/[0.04]">
                <td colSpan={2} className="px-4 py-3 text-right text-xs font-bold uppercase tracking-wide text-ink/70">Total geral (kit + frete)</td>
                <td className="px-4 py-3 text-right font-mono text-lg font-bold tabular-nums text-primary">
                  {recalculando
                    ? <span className="text-sm font-medium text-ink/40">recalculando…</span>
                    : (totalComFreteServidor ?? kit.total_com_frete) != null
                      ? brl((totalComFreteServidor ?? kit.total_com_frete)!)
                      : '—'}
                </td>
              </tr>
            )}
            {!ocultarValores && frete && (
              <>
                <tr className="bg-ink/[0.02]">
                  <td colSpan={3} className="px-4 py-2.5 text-right text-xs font-semibold uppercase tracking-wide text-ink/50">
                    {frete.tipo === 'fob'
                      ? `Frete FOB — WEG→CD (${(frete.percentual * 100).toFixed(0)}%)`
                      : `Frete CIF — ${frete.uf} (${(frete.percentual * 100).toFixed(1)}%)`}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-sm tabular-nums text-ink/70">{brl(frete.valor)}</td>
                  {editable && <td />}
                </tr>
                <tr className="border-t border-ink/15 bg-primary/[0.04]">
                  <td colSpan={3} className="px-4 py-3 text-right text-xs font-bold uppercase tracking-wide text-ink/70">Total geral (kit + frete)</td>
                  <td className="px-4 py-3 text-right font-mono text-lg font-bold tabular-nums text-primary">{brl(totalKit + frete.valor)}</td>
                  {editable && <td />}
                </tr>
              </>
            )}
          </tfoot>
        </table>
      </div>

      {onEscolher && (
        // Travado durante a reprecificação: clicar no meio dela aplicaria o
        // total anterior à edição, que é justamente o número que vai para a
        // proposta.
        <button onClick={onEscolher} disabled={escolhendo || recalculando}
          className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-white transition hover:bg-primary-dark disabled:opacity-50">
          <CheckCircle2 size={17} />{' '}
          {recalculando ? 'Recalculando…' : escolhendo ? 'Salvando…' : escolherLabel}
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
            {/* "do consumo" só valia no caminho legado (consumo + HSP). Com kWp
                vindo pronto do CRM a base é o alvo, não o consumo. */}
            <Detail label="Cobertura" value={`${solar.cobertura_pct}% do kWp alvo`} />
            {!ocultarValores && (
              <Detail label="Custo dos módulos" value={brl(solar.preco_modulos_total)} />
            )}
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

      {showPicker && (
        <ProductPicker onAdd={addItem} onClose={() => setShowPicker(false)}
          porApiKey={pickerPorApiKey} ocultarPreco={ocultarValores} />
      )}
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
            <div className="text-right">
              <span className="block font-mono text-sm font-semibold tabular-nums text-primary">
                {ocultarValores
                  ? (kit.total_com_frete != null ? brl(kit.total_com_frete) : '—')
                  : frete ? brl(totalKit + frete.valor) : brl(totalKit)}
              </span>
              {frete && !ocultarValores && (
                <span className="block font-mono text-[10px] tabular-nums text-ink/40">kit {brl(totalKit)}</span>
              )}
            </div>
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
