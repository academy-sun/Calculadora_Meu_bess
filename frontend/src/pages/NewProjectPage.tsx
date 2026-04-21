import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { useCalculate } from '@/hooks/useProjects'
import { useStandardLoads } from '@/hooks/useCatalog'
import type { TipoCalculo, CalculateResponse, StandardLoad } from '@/types'

const TIPOS: { value: TipoCalculo; label: string; desc: string }[] = [
  { value: 'backup', label: 'Backup de Energia', desc: 'Garante autonomia em caso de falta de energia' },
  { value: 'peak_shaving', label: 'Peak Shaving', desc: 'Reduz a demanda de ponta para cortar tarifa' },
  { value: 'arbitragem', label: 'Arbitragem Tarifária', desc: 'Carrega no off-peak, descarrega no peak' },
  { value: 'solar', label: 'Solar FV', desc: 'Dimensiona sistema fotovoltaico' },
  { value: 'solar_storage', label: 'Solar + Storage', desc: 'Sistema híbrido solar com armazenamento' },
]

const MONTHS = [
  'Janeiro','Fevereiro','Março','Abril','Maio','Junho',
  'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro',
]

type Step = 'tipo' | 'dados' | 'resultado'

// ── Backup row type ───────────────────────────────────────────────────────────
type BackupRow = {
  id: string
  nome: string
  qtd: number
  pnom_w: number
  fp: number
  fd: number
  ip_in: number
  tdia_h: number
}

export function NewProjectPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const { mutateAsync: calcular, isPending } = useCalculate()
  const { data: loads } = useStandardLoads()

  const [step, setStep] = useState<Step>('tipo')
  const [tipo, setTipo] = useState<TipoCalculo>('backup')
  const [result, setResult] = useState<CalculateResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  // ── Backup ────────────────────────────────────────────────────────────────
  const [tipoInstalacao, setTipoInstalacao] = useState<'monofasico' | 'trifasico'>('monofasico')
  const [autonomia, setAutonomia] = useState('4')
  const [dod, setDod] = useState('90')
  const [backupRows, setBackupRows] = useState<BackupRow[]>([])

  function addBackupRow(load: StandardLoad) {
    const id = crypto.randomUUID()
    setBackupRows(prev => [...prev, {
      id,
      nome: load.nome,
      qtd: 1,
      pnom_w: load.potencia_w,
      fp: load.fator_potencia ?? 1,
      fd: load.fator_demanda ?? 1,
      ip_in: load.ip_in ?? 1,
      tdia_h: load.tdia_horas ?? 4,
    }])
  }

  function updateBackupRow(id: string, field: keyof Omit<BackupRow, 'id' | 'nome'>, value: number) {
    setBackupRows(prev => prev.map(r => r.id === id ? { ...r, [field]: value } : r))
  }

  function removeBackupRow(id: string) {
    setBackupRows(prev => prev.filter(r => r.id !== id))
  }

  // ── Arbitragem ────────────────────────────────────────────────────────────
  const [arbConsumoPonta, setArbConsumoPonta] = useState<string[]>(Array(12).fill(''))
  const [arbDemandaPonta, setArbDemandaPonta] = useState<string[]>(Array(12).fill(''))
  const [arbTarifaPonta, setArbTarifaPonta] = useState('2.50')
  const [arbTarifaForaPonta, setArbTarifaForaPonta] = useState('0.30')

  // ── Peak Shaving ──────────────────────────────────────────────────────────
  const [demandaAlvo, setDemandaAlvo] = useState('')
  const [tarifaDemanda, setTarifaDemanda] = useState('')
  const [curvaInput, setCurvaInput] = useState('')

  // ── Solar ─────────────────────────────────────────────────────────────────
  const [irradiacao, setIrradiacao] = useState('5.0')
  const [area, setArea] = useState('')
  const [consumoSolar, setConsumoSolar] = useState('')

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
      payload.cargas_backup = backupRows.map(({ id: _id, ...r }) => r)
      payload.tipo_instalacao = tipoInstalacao
      payload.autonomia_horas = parseFloat(autonomia)
      payload.dod_percent = parseFloat(dod)
      payload.eficiencia_roundtrip = 90
    } else if (tipo === 'peak_shaving') {
      const curva = curvaInput
        ? curvaInput.split(',').map(v => parseFloat(v.trim())).filter(v => !isNaN(v))
        : undefined
      payload.curva_carga_kw = curva
      payload.demanda_alvo_kw = parseFloat(demandaAlvo)
      payload.tarifa_demanda_rs_kw = parseFloat(tarifaDemanda)
    } else if (tipo === 'arbitragem') {
      payload.consumo_ponta_kwh = arbConsumoPonta.map(v => parseFloat(v) || 0)
      payload.demanda_ponta_kw  = arbDemandaPonta.map(v => parseFloat(v) || 0)
      payload.tarifa_ponta_rs_kwh = parseFloat(arbTarifaPonta)
      payload.tarifa_fora_ponta_rs_kwh = parseFloat(arbTarifaForaPonta)
    } else if (tipo === 'solar' || tipo === 'solar_storage') {
      payload.irradiacao_kwh_m2_dia = parseFloat(irradiacao)
      payload.area_disponivel_m2 = parseFloat(area)
      if (consumoSolar) {
        payload.curva_carga_kw = Array(24).fill(parseFloat(consumoSolar) / 24 / 30)
      }
    }

    try {
      const res = await calcular(payload)
      setResult(res)
      setStep('resultado')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erro ao calcular')
    }
  }

  // ── Step: Tipo ──────────────────────────────────────────────────────────────
  if (step === 'tipo') {
    return (
      <div className="p-6 max-w-2xl">
        <h1 className="mb-1 text-2xl font-bold">Novo Cálculo</h1>
        <p className="mb-6 text-gray-500">Selecione o tipo de dimensionamento</p>
        <div className="space-y-3">
          {TIPOS.map(t => (
            <button
              key={t.value}
              onClick={() => setTipo(t.value)}
              className={`flex w-full items-start gap-4 rounded-xl border-2 p-4 text-left transition-colors ${
                tipo === t.value ? 'border-primary bg-primary/5' : 'border-gray-200 bg-white hover:border-gray-300'
              }`}
            >
              <div className={`mt-0.5 h-4 w-4 flex-shrink-0 rounded-full border-2 ${
                tipo === t.value ? 'border-primary bg-primary' : 'border-gray-300'
              }`} />
              <div>
                <p className="font-semibold text-gray-900">{t.label}</p>
                <p className="text-sm text-gray-500">{t.desc}</p>
              </div>
            </button>
          ))}
        </div>
        <button
          onClick={() => setStep('dados')}
          className="mt-6 rounded-lg bg-primary px-6 py-2 text-sm font-medium text-white hover:bg-primary-dark"
        >
          Próximo →
        </button>
      </div>
    )
  }

  // ── Step: Dados ─────────────────────────────────────────────────────────────
  if (step === 'dados') {
    return (
      <div className="p-6 max-w-2xl">
        <button onClick={() => setStep('tipo')} className="mb-4 text-sm text-gray-500 hover:text-primary">← Voltar</button>
        <h1 className="mb-1 text-2xl font-bold capitalize">{tipo.replace(/_/g, ' ')}</h1>
        <p className="mb-6 text-gray-500">Preencha os parâmetros do dimensionamento</p>

        <form onSubmit={handleSubmit} className="space-y-5">

          {/* ── BACKUP ──────────────────────────────────────────────────────── */}
          {tipo === 'backup' && (
            <>
              {/* Tipo de instalação */}
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Tipo de Instalação</label>
                <div className="flex gap-3">
                  {(['monofasico', 'trifasico'] as const).map(t => (
                    <button key={t} type="button"
                      onClick={() => setTipoInstalacao(t)}
                      className={`flex-1 rounded-lg border-2 py-2 text-sm font-medium transition-colors ${
                        tipoInstalacao === t
                          ? 'border-primary bg-primary/5 text-primary'
                          : 'border-gray-200 text-gray-600 hover:border-gray-300'
                      }`}>
                      {t === 'monofasico' ? 'Monofásico' : 'Trifásico'}
                    </button>
                  ))}
                </div>
              </div>

              {/* Parâmetros */}
              <div className="grid grid-cols-2 gap-3">
                <Field label="Autonomia (h)" value={autonomia} onChange={setAutonomia} placeholder="4" required />
                <Field label="DoD (%)" value={dod} onChange={setDod} placeholder="90" required />
              </div>

              {/* Tabela de cargas */}
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">Cargas da Instalação</label>
                {loads && loads.length > 0 && (
                  <select
                    className="mb-2 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                    onChange={e => {
                      const load = loads.find(l => l.id === e.target.value)
                      if (load) { addBackupRow(load); e.target.value = '' }
                    }}
                  >
                    <option value="">+ Adicionar carga do catálogo...</option>
                    {loads.map(l => (
                      <option key={l.id} value={l.id}>{l.nome} ({l.potencia_w}W)</option>
                    ))}
                  </select>
                )}
                {backupRows.length > 0 && (
                  <div className="overflow-x-auto rounded-lg border border-gray-200">
                    <table className="w-full text-xs">
                      <thead className="bg-gray-50">
                        <tr>
                          {['Equipamento','Qtd','PNOM (W)','TDIA (h)','FP','FD','IP/IN',''].map(h => (
                            <th key={h} className="px-2 py-2 text-left text-gray-500 font-medium">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {backupRows.map(row => (
                          <tr key={row.id} className="border-t border-gray-100">
                            <td className="px-2 py-1 text-gray-700 min-w-[100px]">{row.nome}</td>
                            {(['qtd', 'pnom_w', 'tdia_h', 'fp', 'fd', 'ip_in'] as const).map(f => (
                              <td key={f} className="px-1 py-1">
                                <input type="number" value={row[f]} step="any" min={0}
                                  onChange={e => updateBackupRow(row.id, f, parseFloat(e.target.value))}
                                  className="w-16 rounded border border-gray-200 px-1 py-0.5 text-center text-xs focus:border-primary focus:outline-none" />
                              </td>
                            ))}
                            <td className="px-1 py-1">
                              <button type="button" onClick={() => removeBackupRow(row.id)}
                                className="text-red-400 hover:text-red-600">✕</button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {backupRows.length === 0 && (
                  <p className="text-xs text-gray-400">Adicione ao menos uma carga do catálogo.</p>
                )}
              </div>
            </>
          )}

          {/* ── PEAK SHAVING ─────────────────────────────────────────────────── */}
          {tipo === 'peak_shaving' && (
            <>
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">
                  Curva de Carga (kW separados por vírgula, hora a hora)
                </label>
                <textarea
                  value={curvaInput}
                  onChange={e => setCurvaInput(e.target.value)}
                  rows={3}
                  placeholder="10.5, 9.8, 8.2, ..., 15.3"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
                />
              </div>
              <Field label="Demanda-Alvo (kW)" value={demandaAlvo} onChange={setDemandaAlvo} placeholder="ex: 80" required />
              <Field label="Tarifa de Demanda (R$/kW/mês)" value={tarifaDemanda} onChange={setTarifaDemanda} placeholder="ex: 45.00" required />
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
                        <th className="px-3 py-2 text-left text-gray-500 font-medium w-28">Mês</th>
                        <th className="px-3 py-2 text-left text-gray-500 font-medium">Consumo Ponta (kWh)</th>
                        <th className="px-3 py-2 text-left text-gray-500 font-medium">Demanda Ponta (kW)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {MONTHS.map((mes, i) => (
                        <tr key={mes} className="border-t border-gray-100">
                          <td className="px-3 py-1 text-gray-500">{mes}</td>
                          <td className="px-2 py-1">
                            <input type="number" step="any" min={0}
                              value={arbConsumoPonta[i]}
                              placeholder="0"
                              onChange={e => setArbConsumoPonta(prev => {
                                const next = [...prev]; next[i] = e.target.value; return next
                              })}
                              className="w-full rounded border border-gray-200 px-2 py-1 text-sm focus:border-primary focus:outline-none" />
                          </td>
                          <td className="px-2 py-1">
                            <input type="number" step="any" min={0}
                              value={arbDemandaPonta[i]}
                              placeholder="0"
                              onChange={e => setArbDemandaPonta(prev => {
                                const next = [...prev]; next[i] = e.target.value; return next
                              })}
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

          {/* ── SOLAR / SOLAR + STORAGE ──────────────────────────────────────── */}
          {(tipo === 'solar' || tipo === 'solar_storage') && (
            <>
              <Field label="Irradiação Solar (kWh/m²/dia)" value={irradiacao} onChange={setIrradiacao} placeholder="ex: 5.0" required />
              <Field label="Área Disponível (m²)" value={area} onChange={setArea} placeholder="ex: 100" required />
              <Field label="Consumo Médio Mensal (kWh)" value={consumoSolar} onChange={setConsumoSolar} placeholder="ex: 500" />
            </>
          )}

          {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

          <button
            type="submit"
            disabled={isPending}
            className="w-full rounded-lg bg-primary px-4 py-3 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50"
          >
            {isPending ? 'Calculando...' : 'Calcular Dimensionamento'}
          </button>
        </form>
      </div>
    )
  }

  // ── Step: Resultado ─────────────────────────────────────────────────────────
  return (
    <div className="p-6 max-w-3xl">
      <h1 className="mb-1 text-2xl font-bold text-green-700">✅ Dimensionamento Concluído</h1>
      <p className="mb-6 text-gray-500">Tipo: <span className="font-medium capitalize">{tipo.replace(/_/g, ' ')}</span></p>

      {/* Summary cards */}
      <div className="mb-6 grid grid-cols-3 gap-4">
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <p className="text-xs text-gray-400 uppercase">Capacidade</p>
          <p className="text-2xl font-bold">{result?.capacidade_kwh} kWh</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <p className="text-xs text-gray-400 uppercase">Potência</p>
          <p className="text-2xl font-bold">{result?.potencia_kw} kW</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <p className="text-xs text-gray-400 uppercase">Payback</p>
          <p className="text-2xl font-bold">{result?.payback_meses ? `${result.payback_meses} m` : '—'}</p>
        </div>
      </div>

      {/* Backup: per-row results table */}
      {result?.backup_rows && result.backup_rows.length > 0 && (
        <div className="mb-4 overflow-x-auto rounded-lg border border-gray-200">
          <table className="w-full text-xs">
            <thead className="bg-gray-50">
              <tr>
                {['Equipamento','Pn (kVA)','Dmn (kVA)','Pp (kVA)','DMp (kVA)','E_EPS (kWh)'].map(h => (
                  <th key={h} className="px-3 py-2 text-left text-gray-500 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.backup_rows.map((r, i) => (
                <tr key={i} className="border-t border-gray-100">
                  <td className="px-3 py-1 text-gray-700">{r.nome}</td>
                  <td className="px-3 py-1">{r.pn_kva}</td>
                  <td className="px-3 py-1">{r.dmn_kva}</td>
                  <td className="px-3 py-1">{r.pp_kva}</td>
                  <td className="px-3 py-1">{r.dmp_kva}</td>
                  <td className="px-3 py-1 font-medium">{r.e_eps_kwh}</td>
                </tr>
              ))}
              <tr className="border-t-2 border-gray-300 bg-gray-50 font-semibold text-xs">
                <td className="px-3 py-1">TOTAL</td>
                <td className="px-3 py-1">{result.total_pn_kva}</td>
                <td className="px-3 py-1">{result.total_dmn_kva}</td>
                <td className="px-3 py-1">{result.total_pp_kva}</td>
                <td className="px-3 py-1">{result.total_dmp_kva}</td>
                <td className="px-3 py-1">{result.capacidade_kwh} kWh</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {/* Arbitragem: dimensionamento stats */}
      {result?.qty_bess !== undefined && (
        <div className="mb-4 rounded-xl border border-gray-200 bg-white p-4">
          <p className="mb-3 text-xs font-bold uppercase text-gray-500">Dimensionamento Arbitragem</p>
          <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div>
              <p className="text-xs text-gray-400">Qtd BESS</p>
              <p className="text-2xl font-bold text-primary">{result.qty_bess}</p>
              <p className="text-xs text-gray-400">
                {result.qty_bess === result.qty_consumo ? 'limitado por consumo' : 'limitado por demanda'}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-400">Média Consumo Ponta</p>
              <p className="font-semibold">{result.avg_consumo_ponta?.toFixed(1)} kWh/mês</p>
            </div>
            <div>
              <p className="text-xs text-gray-400">Maior Demanda Ponta</p>
              <p className="font-semibold">{result.max_demanda_ponta?.toFixed(1)} kW</p>
            </div>
            <div>
              <p className="text-xs text-gray-400">Economia Estimada</p>
              <p className="font-semibold text-green-700">
                R$ {result.economia_mensal_rs?.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}/mês
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Kit recomendado */}
      {result?.kit_selecionado && (
        <div className="mb-4 rounded-xl border-2 border-primary/40 bg-primary/5 p-4">
          <p className="mb-3 text-xs font-bold uppercase text-primary">Kit Recomendado — Menor Preço</p>
          <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div><p className="text-xs text-gray-500">Marca</p><p className="font-semibold">{result.kit_selecionado.marca}</p></div>
            <div><p className="text-xs text-gray-500">Bateria</p><p className="font-semibold">{result.kit_selecionado.bateria_modelo}</p></div>
            <div><p className="text-xs text-gray-500">Inversor</p><p className="font-semibold">{result.kit_selecionado.inversor_modelo}</p></div>
            <div>
              <p className="text-xs text-gray-500">Preço Total</p>
              <p className="font-bold text-green-700">R$ {result.kit_selecionado.preco_total.toLocaleString('pt-BR')}</p>
            </div>
          </div>
          <p className="mt-2 text-xs text-gray-500">
            {result.kit_selecionado.qtd_baterias}× baterias
            {result.kit_selecionado.qtd_inversores && result.kit_selecionado.qtd_inversores > 1
              ? ` · ${result.kit_selecionado.qtd_inversores}× inversores`
              : ''}
            {' '}· {result.kit_selecionado.capacidade_total_kwh} kWh úteis · {result.kit_selecionado.potencia_total_kw} kW
          </p>
        </div>
      )}

      {/* Alternativas */}
      {result?.alternativas && result.alternativas.length > 0 && (
        <div className="mb-4">
          <p className="mb-2 text-xs font-semibold uppercase text-gray-400">Alternativas</p>
          <div className="space-y-2">
            {result.alternativas.map((k, i) => (
              <div key={i} className="flex items-center justify-between rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm">
                <span>{k.marca} — {k.bateria_modelo} + {k.inversor_modelo}</span>
                <span className="font-medium">R$ {k.preco_total.toLocaleString('pt-BR')}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {(result?.economia_mensal_rs || result?.economia_anual_rs) && !result?.qty_bess && (
        <div className="mb-4 rounded-lg bg-green-50 px-4 py-3 text-sm text-green-800">
          {result?.economia_mensal_rs && <>Economia mensal: <strong>R$ {result.economia_mensal_rs.toLocaleString('pt-BR')}</strong></>}
          {result?.economia_anual_rs && <> · Anual: <strong>R$ {result.economia_anual_rs.toLocaleString('pt-BR')}</strong></>}
        </div>
      )}

      <div className="mt-6 flex gap-3">
        <button onClick={() => { setStep('tipo'); setResult(null); setError(null) }}
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm hover:bg-gray-50">
          Novo Cálculo
        </button>
        <button onClick={() => navigate(`/projects/${result?.projeto_id}`)}
          className="rounded-lg bg-primary px-4 py-2 text-sm text-white hover:bg-primary-dark">
          Ver Projeto
        </button>
      </div>
    </div>
  )
}

function Field({ label, value, onChange, placeholder, required }: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string; required?: boolean
}) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-gray-700">{label}</label>
      <input type="number" value={value} onChange={e => onChange(e.target.value)}
        placeholder={placeholder} required={required} step="any"
        className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:outline-none" />
    </div>
  )
}
