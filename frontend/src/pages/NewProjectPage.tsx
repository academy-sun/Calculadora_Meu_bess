import { useState } from 'react'
import type { ElementType } from 'react'
import { BatteryCharging, TrendingUp, Plus } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { CityCombobox } from '@/components/CityCombobox'
import { AddLoadDialog } from '@/components/AddLoadDialog'
import type { LoadRowInput } from '@/components/AddLoadDialog'
import { KitResult } from '@/components/KitResult'
import { useCalculate } from '@/hooks/useProjects'
import { useStandardLoads } from '@/hooks/useCatalog'
import type { CalculateResponse } from '@/types'

type TipoCalculo = 'backup' | 'arbitragem'

const TIPOS: { value: TipoCalculo; label: string; desc: string; icon: ElementType }[] = [
  { value: 'backup',    label: 'Backup de Energia',   desc: 'Autonomia na falta de energia', icon: BatteryCharging },
  { value: 'arbitragem', label: 'Arbitragem Tarifária', desc: 'Carrega no fora-ponta, descarrega na ponta', icon: TrendingUp },
]

const MONTHS = [
  'Janeiro','Fevereiro','Março','Abril','Maio','Junho',
  'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro',
]

type Step = 'tipo' | 'dados'

type BackupRow = {
  id: string
  nome: string
  categoria: string
  qtd: number
  pnom_w: number
  fp: number
  fd: number
  ip_in: number
  tdia_h: number
  tensao: string   // "127" | "220" | "380" — usada no R8 (saída EPS do inversor)
  fase: string
}

export function NewProjectPage() {
  const { user } = useAuth()
  const { mutateAsync: calcular, isPending } = useCalculate()
  const { data: loads, isLoading: loadsLoading, isError: loadsError } = useStandardLoads()

  const [step, setStep] = useState<Step>('tipo')
  const [tipo, setTipo] = useState<TipoCalculo>('backup')
  const [result, setResult] = useState<CalculateResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  // ── Backup ──────────────────────────────────────────────────────────────────
  const [padraoEntrada, setPadraoEntrada] = useState('mono_220')
  const tipoInstalacao: 'monofasico' | 'trifasico' =
    padraoEntrada.startsWith('tri') ? 'trifasico' : 'monofasico'
  const [autonomia, setAutonomia] = useState('4')
  const [backupRows, setBackupRows] = useState<BackupRow[]>([])
  const [consumoMensal, setConsumoMensal] = useState('')
  const [hspMedia, setHspMedia] = useState<number | null>(null)
  const [cidadeLabel, setCidadeLabel] = useState('')
  const [showAddLoad, setShowAddLoad] = useState(false)

  function insertRow(r: LoadRowInput) {
    setBackupRows(prev => [...prev, { id: crypto.randomUUID(), ...r }])
  }

  function patchRow(id: string, patch: Partial<BackupRow>) {
    setBackupRows(prev => prev.map(r => r.id === id ? { ...r, ...patch } : r))
  }

  function removeBackupRow(id: string) {
    setBackupRows(prev => prev.filter(r => r.id !== id))
  }

  // ── Arbitragem ──────────────────────────────────────────────────────────────
  const [arbConsumoPonta, setArbConsumoPonta] = useState<string[]>(Array(12).fill(''))
  const [arbDemandaPonta, setArbDemandaPonta] = useState<string[]>(Array(12).fill(''))
  const [arbTarifaPonta, setArbTarifaPonta] = useState('2.50')
  const [arbTarifaForaPonta, setArbTarifaForaPonta] = useState('0.30')

  // Pn (kVA) = qtd × pnom / fp / 1000 ; Pp (kVA) = Pn × IP/IN ; E (kWh) = qtd × pnom × h / 1000
  const rowPn = (r: BackupRow) => (r.qtd * r.pnom_w) / (r.fp || 1) / 1000
  const rowPp = (r: BackupRow) => rowPn(r) * (r.ip_in || 1)
  const rowE = (r: BackupRow) => (r.qtd * r.pnom_w * r.tdia_h) / 1000
  const subtotais = backupRows.reduce(
    (a, r) => ({ pn: a.pn + rowPn(r), pp: a.pp + rowPp(r), energia: a.energia + rowE(r) }),
    { pn: 0, pp: 0, energia: 0 },
  )

  // ── Submit ──────────────────────────────────────────────────────────────────
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    const displayName =
      (user?.user_metadata?.nome as string | undefined) ?? user?.email ?? 'Engenheiro'

    const payload: Record<string, unknown> = {
      origem_info: {
        origem: 'interno',
        solicitante_id: user?.id ?? 'unknown',
        solicitante_nome: displayName,
        solicitado_em: new Date().toISOString(),
      },
      tipo_calculo: tipo,
    }

    if (tipo === 'backup') {
      payload.cargas_backup = backupRows.map(r => ({
        nome: r.nome, qtd: r.qtd, pnom_w: r.pnom_w, fp: r.fp, fd: r.fd,
        ip_in: r.ip_in, tdia_h: r.tdia_h, tensao: r.tensao,
      }))
      payload.tipo_instalacao = tipoInstalacao
      payload.padrao_entrada = padraoEntrada
      payload.autonomia_horas = parseFloat(autonomia)
      payload.eficiencia_roundtrip = 90
      const consumoNum = parseFloat(consumoMensal)
      if (consumoNum > 0 && hspMedia) {
        payload.consumo_medio_mensal_kwh = consumoNum
        payload.hsp_media = hspMedia
      }
    } else {
      payload.consumo_ponta_kwh = arbConsumoPonta.map(v => parseFloat(v) || 0)
      payload.demanda_ponta_kw  = arbDemandaPonta.map(v => parseFloat(v) || 0)
      payload.tarifa_ponta_rs_kwh = parseFloat(arbTarifaPonta)
      payload.tarifa_fora_ponta_rs_kwh = parseFloat(arbTarifaForaPonta)
    }

    try {
      const res = await calcular(payload)
      setResult(res)  // mostra o kit na mesma página (abaixo do formulário)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erro ao calcular')
    }
  }

  // ── Step: Tipo ──────────────────────────────────────────────────────────────
  if (step === 'tipo') {
    return (
      <div className="flex min-h-[80vh] flex-col items-center justify-center p-6">
        <h1 className="mb-1 text-2xl font-bold">Nova Cotação</h1>
        <p className="mb-10 text-gray-500">Selecione o tipo de dimensionamento</p>
        <div className="flex flex-wrap items-stretch justify-center gap-6">
          {TIPOS.map(t => {
            const Icon = t.icon
            return (
              <button
                key={t.value}
                onClick={() => { setTipo(t.value); setStep('dados') }}
                className="flex w-60 flex-col items-center gap-4 rounded-2xl border-2 border-gray-200 bg-white p-8 text-center transition-all hover:-translate-y-1 hover:border-primary hover:shadow-lg"
              >
                <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                  <Icon size={40} />
                </div>
                <div>
                  <p className="text-lg font-bold text-gray-900">{t.label}</p>
                  <p className="mt-1 text-sm text-gray-500">{t.desc}</p>
                </div>
              </button>
            )
          })}
        </div>
      </div>
    )
  }

  // ── Step: Dados ─────────────────────────────────────────────────────────────
  if (step === 'dados') {
    return (
      <div className="p-6 max-w-5xl">
        <button onClick={() => setStep('tipo')} className="mb-4 text-sm text-gray-500 hover:text-primary">← Voltar</button>
        <h1 className="mb-1 text-2xl font-bold">
          {tipo === 'backup' ? 'Backup de Energia' : 'Arbitragem Tarifária'}
        </h1>
        <p className="mb-6 text-gray-500">Preencha os parâmetros do dimensionamento</p>

        <form onSubmit={handleSubmit} className="space-y-5">

          {/* ── BACKUP ──────────────────────────────────────────────────────── */}
          {tipo === 'backup' && (
            <>
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">Padrão de entrada da unidade</label>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {([
                    { v: 'mono_127', l: 'Monofásico', s: '127 V' },
                    { v: 'mono_220', l: 'Monofásico', s: '220 V' },
                    { v: 'tri_127_220', l: 'Trifásico', s: '127/220 V' },
                    { v: 'tri_220_380', l: 'Trifásico', s: '220/380 V' },
                  ] as const).map(o => (
                    <button key={o.v} type="button" onClick={() => setPadraoEntrada(o.v)}
                      className={`rounded-xl border-2 px-3 py-3 text-center transition-colors ${
                        padraoEntrada === o.v
                          ? 'border-primary bg-primary/5 text-primary'
                          : 'border-gray-200 text-gray-600 hover:border-gray-300'
                      }`}>
                      <span className="block text-sm font-semibold">{o.l}</span>
                      <span className="block text-xs">{o.s}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="max-w-xs">
                <Field label="Autonomia desejada (h)" value={autonomia} onChange={setAutonomia} placeholder="4" required />
                <p className="mt-1 text-xs text-gray-400">A profundidade de descarga (DoD) vem do datasheet da bateria.</p>
              </div>

              {/* ── Solar (opcional) ───────────────────────────────────────── */}
              <div className="rounded-lg border border-amber-100 bg-amber-50 p-4 space-y-3">
                <p className="text-xs font-semibold text-amber-700 uppercase tracking-wide">
                  ☀️ Dimensionamento Solar (opcional)
                </p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="mb-1 block text-sm font-medium text-gray-700">
                      Consumo Médio Mensal (kWh)
                    </label>
                    <input
                      type="number" step="any" min={0}
                      value={consumoMensal}
                      onChange={e => setConsumoMensal(e.target.value)}
                      placeholder="ex: 1200"
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-gray-700">
                      Cidade (HSP)
                    </label>
                    <CityCombobox
                      value={cidadeLabel}
                      onSelect={city => {
                        setHspMedia(city.hsp)
                        setCidadeLabel(`${city.nome} - ${city.sigla}`)
                      }}
                      placeholder="Buscar cidade..."
                    />
                    {hspMedia && (
                      <p className="mt-1 text-xs text-gray-400">HSP média: {hspMedia} kWh/m²/dia</p>
                    )}
                  </div>
                </div>
              </div>

              <div>
                <div className="mb-2 flex items-center justify-between">
                  <label className="block text-sm font-medium text-gray-700">Cargas da instalação</label>
                  <button type="button" onClick={() => setShowAddLoad(true)}
                    className="flex items-center gap-1 rounded-lg border-2 border-primary px-3 py-2 text-sm font-medium text-primary hover:bg-primary/5">
                    <Plus size={16} /> Adicionar carga
                  </button>
                </div>

                {loadsError && (
                  <p className="mb-2 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">
                    ⚠ Erro ao carregar o catálogo de cargas.
                  </p>
                )}

                {backupRows.length > 0 ? (
                  <div className="overflow-x-auto rounded-lg border border-gray-200">
                    <table className="w-full text-xs">
                      <thead className="bg-gray-50">
                        <tr className="text-left text-gray-500">
                          {['Equipamento','Categoria','Qtd','Pot (W)','Uso (h)','FP','FD','IP/IN','Tensão','Fase','Pn (kVA)','Pp (kVA)','E (kWh)',''].map(h => (
                            <th key={h} className="px-2 py-2 font-medium">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {backupRows.map(row => (
                          <tr key={row.id} className="border-t border-gray-100">
                            <td className="px-1 py-1"><TInput value={row.nome} onChange={v => patchRow(row.id, { nome: v })} w="w-32" /></td>
                            <td className="px-1 py-1"><TInput value={row.categoria} onChange={v => patchRow(row.id, { categoria: v })} w="w-24" /></td>
                            <td className="px-1 py-1"><NInput value={row.qtd} onChange={v => patchRow(row.id, { qtd: v })} /></td>
                            <td className="px-1 py-1"><NInput value={row.pnom_w} onChange={v => patchRow(row.id, { pnom_w: v })} /></td>
                            <td className="px-1 py-1"><NInput value={row.tdia_h} onChange={v => patchRow(row.id, { tdia_h: v })} /></td>
                            <td className="px-1 py-1"><NInput value={row.fp} onChange={v => patchRow(row.id, { fp: v })} /></td>
                            <td className="px-1 py-1"><NInput value={row.fd} onChange={v => patchRow(row.id, { fd: v })} /></td>
                            <td className="px-1 py-1"><NInput value={row.ip_in} onChange={v => patchRow(row.id, { ip_in: v })} /></td>
                            <td className="px-1 py-1">
                              <select value={row.tensao} onChange={e => patchRow(row.id, { tensao: e.target.value })}
                                className="w-16 rounded border border-gray-200 px-1 py-0.5 text-center text-xs focus:border-primary focus:outline-none">
                                <option value="127">127</option><option value="220">220</option><option value="380">380</option>
                              </select>
                            </td>
                            <td className="px-1 py-1">
                              <select value={row.fase} onChange={e => patchRow(row.id, { fase: e.target.value })}
                                className="w-16 rounded border border-gray-200 px-1 py-0.5 text-center text-xs focus:border-primary focus:outline-none">
                                <option value="monofasico">Mono</option><option value="trifasico">Tri</option>
                              </select>
                            </td>
                            <td className="px-2 py-1 text-right tabular-nums text-gray-700">{rowPn(row).toFixed(2)}</td>
                            <td className="px-2 py-1 text-right tabular-nums text-gray-700">{rowPp(row).toFixed(2)}</td>
                            <td className="px-2 py-1 text-right tabular-nums text-gray-700">{rowE(row).toFixed(2)}</td>
                            <td className="px-1 py-1">
                              <button type="button" onClick={() => removeBackupRow(row.id)}
                                className="text-red-400 hover:text-red-600 text-sm">✕</button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr className="border-t-2 border-gray-300 bg-gray-50 font-semibold text-gray-700">
                          <td className="px-2 py-2 text-right" colSpan={10}>TOTAIS</td>
                          <td className="px-2 py-2 text-right tabular-nums">{subtotais.pn.toFixed(2)}</td>
                          <td className="px-2 py-2 text-right tabular-nums">{subtotais.pp.toFixed(2)}</td>
                          <td className="px-2 py-2 text-right tabular-nums">{subtotais.energia.toFixed(2)}</td>
                          <td />
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                ) : (
                  <p className="rounded-lg border border-dashed border-gray-200 px-3 py-6 text-center text-xs text-gray-400">
                    Nenhuma carga adicionada. Clique em <strong>Adicionar carga</strong>.
                  </p>
                )}
              </div>
            </>
          )}

          {/* ── ARBITRAGEM ───────────────────────────────────────────────────── */}
          {tipo === 'arbitragem' && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Tarifa Fora da Ponta (R$/kWh)" value={arbTarifaForaPonta}
                  onChange={setArbTarifaForaPonta} placeholder="ex: 0.30" required />
                <Field label="Tarifa na Ponta (R$/kWh)" value={arbTarifaPonta}
                  onChange={setArbTarifaPonta} placeholder="ex: 2.50" required />
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">
                  Consumo e Demanda na Ponta — dados da fatura (12 meses)
                </label>
                <div className="overflow-x-auto rounded-lg border border-gray-200">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 w-28">Mês</th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Consumo Ponta (kWh)</th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Demanda Ponta (kW)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {MONTHS.map((mes, i) => (
                        <tr key={mes} className="border-t border-gray-100">
                          <td className="px-3 py-1 text-sm text-gray-500">{mes}</td>
                          <td className="px-2 py-1">
                            <input type="number" step="any" min={0}
                              value={arbConsumoPonta[i]} placeholder="0"
                              onChange={e => setArbConsumoPonta(prev => { const n = [...prev]; n[i] = e.target.value; return n })}
                              className="w-full rounded border border-gray-200 px-2 py-1 text-sm focus:border-primary focus:outline-none" />
                          </td>
                          <td className="px-2 py-1">
                            <input type="number" step="any" min={0}
                              value={arbDemandaPonta[i]} placeholder="0"
                              onChange={e => setArbDemandaPonta(prev => { const n = [...prev]; n[i] = e.target.value; return n })}
                              className="w-full rounded border border-gray-200 px-2 py-1 text-sm focus:border-primary focus:outline-none" />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}

          {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

          <button
            type="submit"
            disabled={isPending || (tipo === 'backup' && backupRows.length === 0)}
            className="w-full rounded-lg bg-primary px-4 py-3 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50"
          >
            {isPending ? 'Buscando…' : 'Buscar kits'}
          </button>
        </form>

        {showAddLoad && (
          <AddLoadDialog
            loads={loads ?? []}
            defaultTensao={tipoInstalacao === 'trifasico' ? '380' : '220'}
            onInsert={insertRow}
            onClose={() => setShowAddLoad(false)}
          />
        )}

        {result && <KitResult result={result} />}
      </div>
    )
  }

  return null
}

function Field({ label, value, onChange, placeholder, required }: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string; required?: boolean
}) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-gray-700">{label}</label>
      <input type="text" value={value} onChange={e => onChange(e.target.value)}
        placeholder={placeholder} required={required}
        className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:outline-none" />
    </div>
  )
}

// Inputs editáveis dentro da tabela de cargas
function TInput({ value, onChange, w = 'w-24' }: { value: string; onChange: (v: string) => void; w?: string }) {
  return (
    <input type="text" value={value} onChange={e => onChange(e.target.value)}
      className={`${w} rounded border border-gray-200 px-1 py-0.5 text-xs focus:border-primary focus:outline-none`} />
  )
}

function NInput({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <input type="number" step="any" min={0} value={value}
      onChange={e => onChange(parseFloat(e.target.value) || 0)}
      className="w-16 rounded border border-gray-200 px-1 py-0.5 text-center text-xs focus:border-primary focus:outline-none" />
  )
}
