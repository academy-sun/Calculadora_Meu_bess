import { useState } from 'react'
import { useProducts, useUpdateProduct, useSyncCatalog } from '@/hooks/useCatalog'
import type { SyncResult } from '@/hooks/useCatalog'
import type { MeuBESSProduct, ProductFilters, TipoProduto } from '@/types'
import { RefreshCw, CheckCircle2, AlertTriangle, X } from 'lucide-react'

// ── rótulos e cores ─────────────────────────────────────────────────────────

const TIPO_LABEL: Record<string, string> = {
  bateria:          'Bateria',
  inversor_hibrido: 'Inversor Híbrido',
  inversor_string:  'Inversor String',
  modulo_fv:        'Módulo FV',
  acessorio:        'Acessório',
  indefinido:       'Indefinido',
}

const TIPO_BADGE: Record<string, string> = {
  bateria:          'bg-blue-100 text-blue-700',
  inversor_hibrido: 'bg-amber-100 text-amber-700',
  inversor_string:  'bg-green-100 text-green-700',
  modulo_fv:        'bg-yellow-100 text-yellow-700',
  acessorio:        'bg-gray-100 text-gray-500',
  indefinido:       'bg-red-100 text-red-700',
}

const CONFIANCA_LABEL: Record<string, string> = {
  alta: 'alta', media: 'média', baixa: 'baixa',
}

const TIPOS_EDITAVEIS: TipoProduto[] = [
  'bateria', 'inversor_hibrido', 'inversor_string', 'modulo_fv', 'acessorio', 'indefinido',
]

function tipoEfetivo(p: MeuBESSProduct): string {
  return p.tipo_manual ?? p.tipo_auto ?? 'indefinido'
}

function fmtNum(v: number | undefined, suffix = ''): string {
  if (v === undefined || v === null) return '—'
  return `${v.toLocaleString('pt-BR')}${suffix}`
}

function fmtDate(v: string | undefined): string {
  if (!v) return '—'
  const d = new Date(v)
  return isNaN(d.getTime()) ? '—' : d.toLocaleString('pt-BR')
}

// ── página ───────────────────────────────────────────────────────────────────

// ── dimensionamento (campos editáveis por tipo) ──────────────────────────────

type DimField = { key: keyof MeuBESSProduct; label: string; kind: 'num' | 'text' | 'bool' }

const DIM_INVERSOR: DimField[] = [
  { key: 'peak_power_kw',               label: 'Potência de pico (kW)',       kind: 'num' },
  { key: 'peak_power_duration_s',       label: 'Duração do pico (s)',         kind: 'num' },
  { key: 'battery_input_max_current_a', label: 'Corrente máx/entrada (A)',    kind: 'num' },
  { key: 'battery_voltage_min_v',       label: 'Tensão bateria mín (V)',      kind: 'num' },
  { key: 'battery_voltage_max_v',       label: 'Tensão bateria máx (V)',      kind: 'num' },
  { key: 'eps_output_voltage',          label: 'Tensão saída EPS',            kind: 'text' },
  { key: 'split_phase',                 label: 'Split-phase',                 kind: 'bool' },
  { key: 'max_parallel_units',          label: 'Máx inversores paralelo',     kind: 'num' },
]

const DIM_BATERIA: DimField[] = [
  { key: 'usable_capacity_kwh',     label: 'Capacidade útil (kWh)',     kind: 'num' },
  { key: 'nominal_capacity_kwh',    label: 'Capacidade nominal (kWh)',  kind: 'num' },
  { key: 'dod_percent',             label: 'DoD (%)',                   kind: 'num' },
  { key: 'max_parallel_batteries',  label: 'Máx em paralelo',           kind: 'num' },
  { key: 'max_continuous_current_a', label: 'Corrente máx contínua (A)', kind: 'num' },
  { key: 'peak_discharge_current_a', label: 'Corrente pico descarga (A)', kind: 'num' },
  { key: 'nominal_voltage_v',       label: 'Tensão nominal (V)',        kind: 'num' },
  { key: 'operating_voltage_min_v', label: 'Tensão operação mín (V)',   kind: 'num' },
  { key: 'operating_voltage_max_v', label: 'Tensão operação máx (V)',   kind: 'num' },
  { key: 'chemistry',               label: 'Química',                   kind: 'text' },
  { key: 'compatible_inverters',    label: 'Inversores compatíveis',    kind: 'text' },
]

const REQ_INVERSOR: (keyof MeuBESSProduct)[] = ['peak_power_kw', 'battery_input_max_current_a', 'eps_output_voltage']
const REQ_BATERIA: (keyof MeuBESSProduct)[] = ['usable_capacity_kwh', 'max_parallel_batteries', 'max_continuous_current_a', 'nominal_voltage_v']

/** Valor efetivo: override manual vence o nativo (espelha o backend). */
function effVal(p: MeuBESSProduct, key: string): unknown {
  const ov = p.overrides_tecnicos as Record<string, unknown> | undefined
  return ov?.[key] ?? (p as unknown as Record<string, unknown>)[key]
}

/** Faltam dados técnicos obrigatórios para o tipo? (só inversor híbrido / bateria) */
function dadosTecnicosIncompletos(p: MeuBESSProduct): boolean {
  const t = tipoEfetivo(p)
  if (t === 'inversor_hibrido')
    return REQ_INVERSOR.some(k => effVal(p, k) == null) || effVal(p, 'battery_inputs') == null
  if (t === 'bateria')
    return REQ_BATERIA.some(k => effVal(p, k) == null)
  return false
}

export function ProductsPage() {
  const [filters, setFilters] = useState<ProductFilters>({})
  const { data: products = [], isLoading } = useProducts(filters)
  const syncMutation = useSyncCatalog()
  const [detail, setDetail] = useState<MeuBESSProduct | null>(null)

  const [syncResult, setSyncResult] = useState<SyncResult | null>(null)
  const [syncError,  setSyncError]  = useState<string | null>(null)

  async function handleSync() {
    setSyncError(null); setSyncResult(null)
    try { setSyncResult(await syncMutation.mutateAsync()) }
    catch (err) { setSyncError(err instanceof Error ? err.message : 'Erro na sincronização') }
  }

  function setF<K extends keyof ProductFilters>(k: K, v: ProductFilters[K]) {
    setFilters(prev => {
      const next = { ...prev }
      if (v === undefined || v === '' || v === null) delete next[k]
      else next[k] = v
      return next
    })
  }

  const hasFilter = Object.keys(filters).length > 0

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Catálogo MeuBESS</h1>
          <p className="text-sm text-gray-500">
            Réplica completa da plataforma · {products.length} produto(s) na visão atual
          </p>
        </div>
        <button onClick={handleSync} disabled={syncMutation.isPending}
          className="flex items-center gap-2 rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50">
          <RefreshCw size={16} className={syncMutation.isPending ? 'animate-spin' : ''} />
          {syncMutation.isPending ? 'Sincronizando…' : 'Sincronizar Plataforma'}
        </button>
      </div>

      {/* Sync banner */}
      {(syncResult || syncError) && (
        <div className={`mb-4 rounded-lg px-4 py-3 text-sm ${syncError ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-800'}`}>
          <div className="flex items-start justify-between gap-4">
            <div>
              {syncError && <p className="font-medium">Erro na sincronização: {syncError}</p>}
              {syncResult && (
                <div>
                  <p className="font-medium">✅ {syncResult.total_synced} produto(s) replicado(s)
                    {syncResult.total_errors > 0 && ` · ⚠ ${syncResult.total_errors} erro(s)`}
                    {(syncResult.needs_review_count ?? 0) > 0 && ` · 🔍 ${syncResult.needs_review_count} a revisar`}
                  </p>
                  {syncResult.por_tipo && (
                    <p className="mt-1 text-xs text-green-700">
                      {Object.entries(syncResult.por_tipo)
                        .map(([t, n]) => `${TIPO_LABEL[t] ?? t}: ${n}`)
                        .join(' · ')}
                    </p>
                  )}
                </div>
              )}
            </div>
            <button onClick={() => { setSyncResult(null); setSyncError(null) }}
              className="flex-shrink-0 text-gray-400 hover:text-gray-600">✕</button>
          </div>
        </div>
      )}

      {/* Filtros */}
      <div className="mb-4 grid grid-cols-2 gap-3 rounded-xl border border-gray-200 bg-white p-4 md:grid-cols-4 lg:grid-cols-6">
        <FilterText label="Título" value={filters.titulo ?? ''} onChange={v => setF('titulo', v)} placeholder="Buscar…" />
        <FilterText label="Marca" value={filters.marca ?? ''} onChange={v => setF('marca', v)} placeholder="Ex: WEG" />
        <FilterSelect label="Tipo" value={filters.tipo ?? ''} onChange={v => setF('tipo', v || undefined)}
          options={TIPOS_EDITAVEIS.map(t => ({ value: t, label: TIPO_LABEL[t] }))} />
        <FilterText label="App" value={filters.app ?? ''} onChange={v => setF('app', v)} placeholder="bess / sunhub" />
        <FilterNum label="Potência mín (kW)" value={filters.potencia_min} onChange={v => setF('potencia_min', v)} />
        <FilterNum label="Potência máx (kW)" value={filters.potencia_max} onChange={v => setF('potencia_max', v)} />
        <FilterSelect label="Situação" value={filters.active === undefined ? '' : String(filters.active)}
          onChange={v => setF('active', v === '' ? undefined : v === 'true')}
          options={[{ value: 'true', label: 'Ativo' }, { value: 'false', label: 'Inativo' }]} />
        <FilterDate label="Sinc. de" value={filters.synced_from ?? ''} onChange={v => setF('synced_from', v)} />
        <FilterDate label="Sinc. até" value={filters.synced_to ?? ''} onChange={v => setF('synced_to', v)} />
        <FilterDate label="Criado de" value={filters.seen_from ?? ''} onChange={v => setF('seen_from', v)} />
        <FilterDate label="Criado até" value={filters.seen_to ?? ''} onChange={v => setF('seen_to', v)} />
        <label className="flex items-end gap-2 pb-1 text-xs font-medium text-gray-700">
          <input type="checkbox" checked={filters.needs_review === true}
            onChange={e => setF('needs_review', e.target.checked ? true : undefined)} />
          Só a revisar
        </label>
      </div>
      {hasFilter && (
        <button onClick={() => setFilters({})} className="mb-3 text-xs text-primary hover:underline">
          Limpar filtros
        </button>
      )}

      {isLoading && <p className="text-gray-500">Carregando…</p>}

      {/* Tabela */}
      {!isLoading && (
        <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr className="text-xs font-semibold uppercase text-gray-500">
                <th className="px-4 py-3 text-left">Produto</th>
                <th className="px-4 py-3 text-left">Tipo</th>
                <th className="px-4 py-3 text-left">Categoria</th>
                <th className="px-4 py-3 text-right">Potência</th>
                <th className="px-4 py-3 text-right">Preço (R$)</th>
                <th className="px-4 py-3 text-left">App</th>
                <th className="px-4 py-3 text-left">Situação</th>
                <th className="px-4 py-3 text-left">Validação</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {products.map(p => {
                const t = tipoEfetivo(p)
                return (
                  <tr key={p.meubess_id} onClick={() => setDetail(p)}
                    className="cursor-pointer hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <p className="font-medium">{p.marca ?? '—'}</p>
                      <p className="max-w-md truncate text-xs text-gray-500">{p.title ?? p.meubess_id}</p>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2 py-0.5 text-xs ${TIPO_BADGE[t] ?? 'bg-gray-100 text-gray-500'}`}>
                        {TIPO_LABEL[t] ?? t}
                      </span>
                      {p.tipo_manual && <span className="ml-1 text-[10px] text-gray-400">(manual)</span>}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-600">{p.category_title ?? '—'}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{fmtNum(p.power, ' kW')}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{fmtNum(p.price)}</td>
                    <td className="px-4 py-3 text-xs text-gray-600">{p.app ?? '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2 py-0.5 text-xs ${p.active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                        {p.active ? 'Ativo' : 'Inativo'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {p.needs_review ? (
                        <span className="flex items-center gap-1 text-xs text-amber-600">
                          <AlertTriangle size={13} /> A revisar
                        </span>
                      ) : dadosTecnicosIncompletos(p) ? (
                        <span className="flex items-center gap-1 text-xs text-orange-600">
                          <AlertTriangle size={13} /> Dados incompletos
                        </span>
                      ) : p.validado_em ? (
                        <span className="flex items-center gap-1 text-xs text-green-600">
                          <CheckCircle2 size={13} /> Validado
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-xs text-gray-400">
                          <CheckCircle2 size={13} /> OK
                        </span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {products.length === 0 && (
            <p className="py-10 text-center text-sm text-gray-400">
              {hasFilter ? 'Nenhum produto corresponde aos filtros.' : 'Nenhum produto. Rode a sincronização.'}
            </p>
          )}
        </div>
      )}

      {detail && <DetailModal product={detail} onClose={() => setDetail(null)} />}
    </div>
  )
}

// ── modal de detalhes + edição manual ────────────────────────────────────────

function DetailModal({ product, onClose }: { product: MeuBESSProduct; onClose: () => void }) {
  const updateProduct = useUpdateProduct()
  const [tipoManual, setTipoManual] = useState<TipoProduto | ''>(product.tipo_manual ?? '')
  const [batteryInputs, setBatteryInputs] = useState<string>(
    product.battery_inputs != null ? String(product.battery_inputs) : '')
  const [maxEps, setMaxEps] = useState<string>(
    product.max_eps_power != null ? String(product.max_eps_power) : '')
  const [error, setError] = useState<string | null>(null)

  const t = tipoEfetivo(product)
  const dimFields: DimField[] = t === 'bateria' ? DIM_BATERIA
    : t === 'inversor_hibrido' || t === 'inversor_string' ? DIM_INVERSOR : []

  const [dim, setDim] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {}
    for (const f of dimFields) {
      const v = effVal(product, f.key as string)
      init[f.key as string] = v == null ? '' : f.kind === 'bool' ? (v ? 'true' : 'false') : String(v)
    }
    return init
  })

  async function handleSave(marcarValidado: boolean) {
    setError(null)
    // battery_inputs / max_eps_power são nativos da MeuBESS → vão para overrides
    const overrides: Record<string, unknown> = {}
    if (batteryInputs !== '' && Number(batteryInputs) !== product.battery_inputs)
      overrides.battery_inputs = Number(batteryInputs)
    if (maxEps !== '' && Number(maxEps) !== product.max_eps_power)
      overrides.max_eps_power = Number(maxEps)

    // campos de dimensionamento (colunas dedicadas) → enviados diretamente
    const dimChanges: Record<string, unknown> = {}
    for (const f of dimFields) {
      const raw = dim[f.key as string]
      const val: unknown = raw === '' ? null
        : f.kind === 'num' ? Number(raw)
        : f.kind === 'bool' ? raw === 'true' : raw
      if (val !== (product as unknown as Record<string, unknown>)[f.key as string])
        dimChanges[f.key as string] = val
    }

    try {
      await updateProduct.mutateAsync({
        meubess_id: product.meubess_id,
        tipo_manual: tipoManual || undefined,
        overrides_tecnicos: Object.keys(overrides).length ? overrides : undefined,
        marcar_validado: marcarValidado,
        ...dimChanges,
      })
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao salvar')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h2 className="text-lg font-bold">{product.marca ?? '—'}</h2>
            <p className="text-sm text-gray-500">{product.title ?? product.meubess_id}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
        </div>

        {/* Classificação + validação manual */}
        <div className="mb-5 rounded-lg border border-amber-100 bg-amber-50 p-4">
          <div className="mb-3 flex flex-wrap items-center gap-2 text-sm">
            <span className={`rounded-full px-2 py-0.5 text-xs ${TIPO_BADGE[t] ?? 'bg-gray-100'}`}>
              {TIPO_LABEL[t] ?? t}
            </span>
            <span className="text-xs text-gray-500">
              automático: <strong>{TIPO_LABEL[product.tipo_auto ?? 'indefinido']}</strong>
              {product.classificacao_confianca && ` · confiança ${CONFIANCA_LABEL[product.classificacao_confianca]}`}
            </span>
            {product.needs_review && (
              <span className="flex items-center gap-1 text-xs text-amber-700">
                <AlertTriangle size={13} /> requer revisão
              </span>
            )}
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-700">Tipo (manual)</label>
              <select value={tipoManual} onChange={e => setTipoManual(e.target.value as TipoProduto | '')}
                className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm">
                <option value="">— usar automático —</option>
                {TIPOS_EDITAVEIS.map(t => <option key={t} value={t}>{TIPO_LABEL[t]}</option>)}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-700">Entradas de bateria</label>
              <input type="number" step="1" value={batteryInputs} onChange={e => setBatteryInputs(e.target.value)}
                placeholder={product.battery_inputs == null ? 'não informado' : ''}
                className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-700">Pot. máx EPS (kW)</label>
              <input type="number" step="any" value={maxEps} onChange={e => setMaxEps(e.target.value)}
                placeholder={product.max_eps_power == null ? 'não informado' : ''}
                className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm" />
            </div>
          </div>
          {dimFields.length > 0 && (
            <div className="mt-4 border-t border-amber-200 pt-3">
              <p className="mb-2 text-xs font-semibold uppercase text-amber-700">
                Dados de dimensionamento (datasheet)
                {dadosTecnicosIncompletos(product) && (
                  <span className="ml-1 normal-case text-orange-600"> — incompletos</span>
                )}
              </p>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {dimFields.map(f => (
                  <div key={f.key as string}>
                    <label className="mb-1 block text-[11px] font-medium text-gray-600">{f.label}</label>
                    {f.kind === 'bool' ? (
                      <select value={dim[f.key as string] ?? ''}
                        onChange={e => setDim(d => ({ ...d, [f.key as string]: e.target.value }))}
                        className="w-full rounded-lg border border-gray-300 px-2 py-1 text-sm">
                        <option value="">—</option>
                        <option value="true">Sim</option>
                        <option value="false">Não</option>
                      </select>
                    ) : (
                      <input type={f.kind === 'num' ? 'number' : 'text'} step="any"
                        value={dim[f.key as string] ?? ''}
                        onChange={e => setDim(d => ({ ...d, [f.key as string]: e.target.value }))}
                        className="w-full rounded-lg border border-gray-300 px-2 py-1 text-sm" />
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
          <div className="mt-3 flex justify-end gap-2">
            <button onClick={() => handleSave(false)} disabled={updateProduct.isPending}
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-50 disabled:opacity-50">
              Salvar
            </button>
            <button onClick={() => handleSave(true)} disabled={updateProduct.isPending}
              className="rounded-lg bg-primary px-3 py-1.5 text-sm text-white hover:bg-primary-dark disabled:opacity-50">
              {updateProduct.isPending ? 'Salvando…' : 'Salvar e validar'}
            </button>
          </div>
        </div>

        {/* Todos os campos */}
        <Section title="Identidade">
          <Field label="ID MeuBESS" value={product.meubess_id} />
          <Field label="SKU" value={product.sku} />
          <Field label="Cód. fornecedor" value={product.suplier_cod} />
          <Field label="Marca" value={product.marca} />
          <Field label="Fornecedor" value={product.supplier_title} />
          <Field label="App" value={product.app} />
          <Field label="Grupo" value={product.groups} />
          <Field label="Seção" value={product.section} />
          <Field label="Disponibilidade" value={product.availability} />
          <Field label="Título original" value={product.original_title} full />
          <Field label="Descrição" value={product.description} full />
        </Section>

        <Section title="Categoria">
          <Field label="Categoria" value={product.category_title} />
          <Field label="Seção da categoria" value={product.category_section} />
        </Section>

        <Section title="Elétrico / Técnico">
          <Field label="Potência" value={fmtNum(product.power, ' kW')} />
          <Field label="Tensão" value={product.voltage} />
          <Field label="Fase" value={product.phase} />
          <Field label="Entradas de bateria" value={product.battery_inputs} highlight />
          <Field label="Pot. máx EPS" value={fmtNum(product.max_eps_power, ' kW')} highlight />
          <Field label="Pot. máx saída" value={fmtNum(product.max_output_power, ' kW')} />
          <Field label="Qtd MPPT" value={product.qty_mppt} />
          <Field label="Entradas por MPPT" value={product.qty_inputs_per_mppt} />
          <Field label="Voc máx" value={fmtNum(product.voc_max_voltage, ' V')} />
          <Field label="MPPT mín" value={fmtNum(product.mppt_min_voltage, ' V')} />
          <Field label="Tensão saída" value={fmtNum(product.output_voltage, ' V')} />
          <Field label="Corrente string" value={fmtNum(product.string_current, ' A')} />
        </Section>

        <Section title="Preço / Fiscal / Dimensão">
          <Field label="Preço" value={fmtNum(product.price)} />
          <Field label="Preço promo" value={fmtNum(product.price_sale)} />
          <Field label="Promo até" value={product.price_sale_until} />
          <Field label="NCM" value={product.ncm} />
          <Field label="Peso" value={fmtNum(product.weight, ' kg')} />
          <Field label="Dimensões (LxAxC)" value={`${fmtNum(product.width)} × ${fmtNum(product.height)} × ${fmtNum(product.length)}`} />
        </Section>

        <Section title="Compliance">
          <Field label="Origem" value={product.origem} />
          <Field label="1ª vez no banco" value={fmtDate(product.first_seen_at)} />
          <Field label="Última sincronização" value={fmtDate(product.last_synced_at)} />
          <Field label="Validado por" value={product.validado_por} />
          <Field label="Validado em" value={fmtDate(product.validado_em)} />
        </Section>
      </div>
    </div>
  )
}

// ── componentes auxiliares ────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-400">{title}</p>
      <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 sm:grid-cols-3">{children}</div>
    </div>
  )
}

function Field({ label, value, full, highlight }: {
  label: string; value: string | number | undefined | null; full?: boolean; highlight?: boolean
}) {
  const v = value === undefined || value === null || value === '' ? '—' : String(value)
  return (
    <div className={full ? 'col-span-2 sm:col-span-3' : ''}>
      <p className="text-[11px] text-gray-400">{label}</p>
      <p className={`text-sm ${highlight ? 'font-semibold text-amber-700' : 'text-gray-700'} ${full ? '' : 'truncate'}`}>{v}</p>
    </div>
  )
}

function FilterText({ label, value, onChange, placeholder }: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string
}) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-gray-700">{label}</label>
      <input type="text" value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder}
        className="w-full rounded border border-gray-200 px-2 py-1 text-xs focus:border-primary focus:outline-none" />
    </div>
  )
}

function FilterNum({ label, value, onChange }: {
  label: string; value: number | undefined; onChange: (v: number | undefined) => void
}) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-gray-700">{label}</label>
      <input type="number" step="any" value={value ?? ''}
        onChange={e => onChange(e.target.value === '' ? undefined : parseFloat(e.target.value))}
        className="w-full rounded border border-gray-200 px-2 py-1 text-xs focus:border-primary focus:outline-none" />
    </div>
  )
}

function FilterDate({ label, value, onChange }: {
  label: string; value: string; onChange: (v: string) => void
}) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-gray-700">{label}</label>
      <input type="date" value={value} onChange={e => onChange(e.target.value)}
        className="w-full rounded border border-gray-200 px-2 py-1 text-xs focus:border-primary focus:outline-none" />
    </div>
  )
}

function FilterSelect({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void
  options: { value: string; label: string }[]
}) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-gray-700">{label}</label>
      <select value={value} onChange={e => onChange(e.target.value)}
        className="w-full rounded border border-gray-200 px-2 py-1 text-xs focus:border-primary focus:outline-none">
        <option value="">Todos</option>
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  )
}
