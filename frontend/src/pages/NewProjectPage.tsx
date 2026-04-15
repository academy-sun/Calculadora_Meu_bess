import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { useCalculate } from '@/hooks/useProjects'
import { useStandardLoads } from '@/hooks/useCatalog'
import type { TipoCalculo, LoadItem, CalculateResponse } from '@/types'

const TIPOS: { value: TipoCalculo; label: string; desc: string }[] = [
  { value: 'backup', label: 'Backup de Energia', desc: 'Garante autonomia em caso de falta de energia' },
  { value: 'peak_shaving', label: 'Peak Shaving', desc: 'Reduz a demanda de ponta para cortar tarifa' },
  { value: 'arbitragem', label: 'Arbitragem Tarifária', desc: 'Carrega no off-peak, descarrega no peak' },
  { value: 'solar', label: 'Solar FV', desc: 'Dimensiona sistema fotovoltaico' },
  { value: 'solar_storage', label: 'Solar + Storage', desc: 'Sistema híbrido solar com armazenamento' },
]

type Step = 'tipo' | 'dados' | 'resultado'

interface SelectedLoad extends LoadItem {
  id: string
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

  const [potenciaCritica, setPotenciaCritica] = useState('')
  const [autonomia, setAutonomia] = useState('')
  const [tensao, setTensao] = useState('220')
  const [demandaAlvo, setDemandaAlvo] = useState('')
  const [tarifaDemanda, setTarifaDemanda] = useState('')
  const [pontaInicio, setPontaInicio] = useState('18')
  const [pontaFim, setPontaFim] = useState('21')
  const [tarifaPonta, setTarifaPonta] = useState('')
  const [tarifaForaPonta, setTarifaForaPonta] = useState('')
  const [irradiacao, setIrradiacao] = useState('5.0')
  const [area, setArea] = useState('')
  const [selectedLoads, setSelectedLoads] = useState<SelectedLoad[]>([])
  const [curvaInput, setCurvaInput] = useState('')

  function addLoad(id: string) {
    const load = loads?.find(l => l.id === id)
    if (!load) return
    setSelectedLoads(prev => [
      ...prev,
      { id, nome: load.nome, potencia_w: load.potencia_w, quantidade: 1, horas_uso_dia: 4 },
    ])
  }

  function updateLoad(id: string, field: 'quantidade' | 'horas_uso_dia', value: number) {
    setSelectedLoads(prev => prev.map(l => l.id === id ? { ...l, [field]: value } : l))
  }

  function removeLoad(id: string) {
    setSelectedLoads(prev => prev.filter(l => l.id !== id))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    const curva = curvaInput
      ? curvaInput.split(',').map(v => parseFloat(v.trim())).filter(v => !isNaN(v))
      : undefined

    const cargas: LoadItem[] | undefined = selectedLoads.length > 0
      ? selectedLoads.map(({ nome, potencia_w, quantidade, horas_uso_dia }) => ({
          nome, potencia_w, quantidade, horas_uso_dia,
        }))
      : undefined

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
      curva_carga_kw: curva,
      cargas,
    }

    if (tipo === 'backup') {
      payload.potencia_critica_kw = parseFloat(potenciaCritica)
      payload.autonomia_horas = parseFloat(autonomia)
      payload.tensao_instalacao_v = parseFloat(tensao)
    } else if (tipo === 'peak_shaving') {
      payload.demanda_alvo_kw = parseFloat(demandaAlvo)
      payload.tarifa_demanda_rs_kw = parseFloat(tarifaDemanda)
    } else if (tipo === 'arbitragem') {
      payload.horario_ponta_inicio = parseInt(pontaInicio)
      payload.horario_ponta_fim = parseInt(pontaFim)
      payload.tarifa_ponta_rs_kwh = parseFloat(tarifaPonta)
      payload.tarifa_fora_ponta_rs_kwh = parseFloat(tarifaForaPonta)
    } else if (tipo === 'solar' || tipo === 'solar_storage') {
      payload.irradiacao_kwh_m2_dia = parseFloat(irradiacao)
      payload.area_disponivel_m2 = parseFloat(area)
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
          {(tipo === 'peak_shaving' || tipo === 'arbitragem') && (
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
              <p className="mt-1 text-xs text-gray-400">Ou adicione cargas abaixo para gerar curva sintética</p>
            </div>
          )}

          {tipo !== 'solar' && tipo !== 'solar_storage' && (
            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700">Cargas da Instalação</label>
              {loads && loads.length > 0 && (
                <select
                  onChange={e => { if (e.target.value) addLoad(e.target.value); e.target.value = '' }}
                  className="mb-2 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                >
                  <option value="">+ Adicionar carga do catálogo...</option>
                  {loads.map(l => (
                    <option key={l.id} value={l.id}>{l.nome} ({l.potencia_w}W)</option>
                  ))}
                </select>
              )}
              {selectedLoads.map(l => (
                <div key={l.id} className="mb-2 flex items-center gap-3 rounded-lg border border-gray-200 bg-white px-3 py-2">
                  <span className="flex-1 text-sm">{l.nome} ({l.potencia_w}W)</span>
                  <input type="number" min={1} value={l.quantidade}
                    onChange={e => updateLoad(l.id, 'quantidade', parseInt(e.target.value))}
                    title="Quantidade"
                    className="w-16 rounded border border-gray-300 px-2 py-1 text-center text-sm" />
                  <input type="number" min={0.5} max={24} step={0.5} value={l.horas_uso_dia}
                    onChange={e => updateLoad(l.id, 'horas_uso_dia', parseFloat(e.target.value))}
                    title="Horas/dia"
                    className="w-16 rounded border border-gray-300 px-2 py-1 text-center text-sm" />
                  <button type="button" onClick={() => removeLoad(l.id)} className="text-red-400 hover:text-red-600">✕</button>
                </div>
              ))}
            </div>
          )}

          {tipo === 'backup' && (
            <>
              <Field label="Potência Crítica da Carga (kW)" value={potenciaCritica} onChange={setPotenciaCritica} placeholder="ex: 5.0" required />
              <Field label="Autonomia Desejada (horas)" value={autonomia} onChange={setAutonomia} placeholder="ex: 4" required />
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Tensão da Instalação</label>
                <select value={tensao} onChange={e => setTensao(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm">
                  <option value="127">127V</option>
                  <option value="220">220V</option>
                  <option value="380">380V</option>
                </select>
              </div>
            </>
          )}

          {tipo === 'peak_shaving' && (
            <>
              <Field label="Demanda-Alvo (kW)" value={demandaAlvo} onChange={setDemandaAlvo} placeholder="ex: 80" required />
              <Field label="Tarifa de Demanda (R$/kW/mês)" value={tarifaDemanda} onChange={setTarifaDemanda} placeholder="ex: 45.00" required />
            </>
          )}

          {tipo === 'arbitragem' && (
            <>
              <div className="flex gap-3">
                <Field label="Início da Ponta (hora)" value={pontaInicio} onChange={setPontaInicio} placeholder="18" />
                <Field label="Fim da Ponta (hora)" value={pontaFim} onChange={setPontaFim} placeholder="21" />
              </div>
              <Field label="Tarifa na Ponta (R$/kWh)" value={tarifaPonta} onChange={setTarifaPonta} placeholder="ex: 0.90" required />
              <Field label="Tarifa Fora da Ponta (R$/kWh)" value={tarifaForaPonta} onChange={setTarifaForaPonta} placeholder="ex: 0.30" required />
            </>
          )}

          {(tipo === 'solar' || tipo === 'solar_storage') && (
            <>
              <Field label="Irradiação Solar (kWh/m²/dia)" value={irradiacao} onChange={setIrradiacao} placeholder="ex: 5.0" required />
              <Field label="Área Disponível (m²)" value={area} onChange={setArea} placeholder="ex: 100" required />
              <Field label="Consumo Médio Mensal (kWh)" value={curvaInput} onChange={setCurvaInput} placeholder="ex: 500" />
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
          <p className="text-2xl font-bold">{result?.payback_meses ? `${result.payback_meses} meses` : '—'}</p>
        </div>
      </div>

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
            {result.kit_selecionado.qtd_baterias}× baterias · {result.kit_selecionado.capacidade_total_kwh} kWh úteis · {result.kit_selecionado.potencia_total_kw} kW
          </p>
        </div>
      )}

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

      {(result?.economia_mensal_rs || result?.economia_anual_rs) && (
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
