import { useEffect, useState } from 'react'
import type { ElementType } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { BatteryCharging, TrendingUp, Plus, MapPin } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { CityCombobox } from '@/components/CityCombobox'
import { AddLoadDialog } from '@/components/AddLoadDialog'
import type { LoadRowInput } from '@/components/AddLoadDialog'
import { KitResult } from '@/components/KitResult'
import { SaveQuoteDialog } from '@/components/SaveQuoteDialog'
import { useCalculate, useProject, useSaveQuote, useUpdateQuote } from '@/hooks/useProjects'
import { useStandardLoads } from '@/hooks/useCatalog'
import type { CalculateResponse, FreteInfo, KitInfo, KitItem, TipoFrete } from '@/types'

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

function FreteCard({ frete }: { frete: FreteInfo }) {
  const brl = (v: number) => v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
  if (frete.tipo === 'fob') {
    return (
      <div className="flex items-center justify-between rounded-xl border border-amber-100 bg-amber-50/60 px-4 py-3 text-sm">
        <div>
          <span className="font-semibold text-amber-700">Frete FOB — Retirada no CD</span>
          <span className="ml-2 text-amber-500 text-xs">(taxa WEG → armazém: {(frete.percentual * 100).toFixed(0)}% do kit)</span>
        </div>
        <span className="font-mono font-bold text-amber-700">{brl(frete.valor)}</span>
      </div>
    )
  }
  return (
    <div className="flex items-center justify-between rounded-xl border border-blue-100 bg-blue-50/60 px-4 py-3 text-sm">
      <div>
        <span className="font-semibold text-blue-700">Frete CIF estimado — {frete.uf}</span>
        <span className="ml-2 text-blue-500 text-xs">({(frete.percentual * 100).toFixed(1)}% · mín. {brl(frete.valor_minimo)})</span>
      </div>
      <span className="font-mono font-bold text-blue-700">{brl(frete.valor)}</span>
    </div>
  )
}

export function NewProjectPage() {
  const { user, perfil } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const editId = searchParams.get('editId')
  const { mutateAsync: calcular, isPending } = useCalculate()
  const { mutateAsync: salvarCotacao, isPending: isSavingNova } = useSaveQuote()
  const { mutateAsync: atualizarCotacao, isPending: isSavingEdicao } = useUpdateQuote()
  const isSaving = isSavingNova || isSavingEdicao
  const { data: editProject } = useProject(editId ?? '')
  const { data: loads, isLoading: loadsLoading, isError: loadsError } = useStandardLoads()

  const [step, setStep] = useState<Step>('tipo')
  const [tipo, setTipo] = useState<TipoCalculo>('backup')
  const [result, setResult] = useState<CalculateResponse | null>(null)
  const [lastPayload, setLastPayload] = useState<Record<string, unknown> | null>(null)
  const [error, setError] = useState<string | null>(null)

  // ── Sistema fotovoltaico (FV) ──────────────────────────────────────────────
  const [powerpeakKwp, setPowerpeakKwp] = useState('')      // kWp (calculado ou manual)
  const [kwpEdited, setKwpEdited] = useState(false)         // usuário editou a potência FV à mão
  const [taxaDesempenho, setTaxaDesempenho] = useState('0.80')
  const [fixingType, setFixingType] = useState('')
  const [pv_ativo, setPvAtivo] = useState(false)  // se a seção FV está expandida
  const [backupAtivo, setBackupAtivo] = useState(false)  // se a seção de backup está expandida

  // ── 3 opções de kit (sugerido + até 2 alternativas) — edição local por opção ──
  const [itensSugerido, setItensSugerido] = useState<KitItem[]>([])
  const [itensAlternativas, setItensAlternativas] = useState<KitItem[][]>([])
  useEffect(() => {
    setItensSugerido(result?.kit_selecionado?.itens ?? [])
    setItensAlternativas((result?.alternativas ?? []).map(a => a.itens ?? []))
  }, [result])

  // ── Salvar cotação (só ao escolher um kit) ───────────────────────────────────
  const [pendingChoice, setPendingChoice] = useState<{ kit: KitInfo; itens: KitItem[] } | null>(null)

  async function confirmSaveQuote(titulo: string) {
    if (!pendingChoice || !result || !lastPayload) return
    const { kit, itens } = pendingChoice
    const precoTotal = itens.reduce((s, it) => s + it.preco_unitario * it.qtd, 0)
    const energiaTotal = itens.reduce((s, it) => s + (it.energia_unit_kwh ?? 0) * it.qtd, 0)
    const potenciaInversao = itens.reduce((s, it) => s + (it.potencia_inversao_kw ?? 0) * it.qtd, 0)
    const chosenKit: KitInfo = {
      ...kit,
      itens,
      preco_total: precoTotal,
      capacidade_total_kwh: energiaTotal,
      potencia_total_kw: potenciaInversao,
    }
    const resultado: CalculateResponse = { ...result, kit_selecionado: chosenKit, alternativas: [] }
    try {
      const saved = editId
        ? await atualizarCotacao({ id: editId, payload: { titulo, calculo: lastPayload, resultado } })
        : await salvarCotacao({ titulo, calculo: lastPayload, resultado })
      setPendingChoice(null)
      navigate(`/projects/${saved.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao salvar cotação')
    }
  }

  // ── Editar cotação salva: prefill a partir do histórico ──────────────────────
  const [prefilled, setPrefilled] = useState(false)
  useEffect(() => {
    if (!editProject || prefilled) return
    const pm = editProject.parametros as Record<string, unknown> | undefined
    if (!pm) return
    setTipo((editProject.tipo_calculo as TipoCalculo) || 'backup')
    setStep('dados')
    if (Array.isArray(pm.cargas_backup)) {
      setBackupRows((pm.cargas_backup as Record<string, unknown>[]).map(r => ({
        id: crypto.randomUUID(),
        nome: String(r.nome ?? ''),
        categoria: '',
        qtd: Number(r.qtd ?? 1),
        pnom_w: Number(r.pnom_w ?? 0),
        fp: Number(r.fp ?? 1),
        fd: Number(r.fd ?? 1),
        ip_in: Number(r.ip_in ?? 1),
        tdia_h: Number(r.tdia_h ?? 4),
        tensao: String(r.tensao ?? '220'),
        fase: 'monofasico',
      })))
    }
    if (typeof pm.padrao_entrada === 'string') setPadraoEntrada(pm.padrao_entrada)
    if (typeof pm.autonomia_dias === 'number') setAutonomia(String(pm.autonomia_dias))
    if (typeof pm.consumo_medio_mensal_kwh === 'number') setConsumoMensal(String(pm.consumo_medio_mensal_kwh))
    if (typeof pm.hsp_media === 'number') setHspMedia(pm.hsp_media as number)
    setPrefilled(true)
  }, [editProject, prefilled])

  // ── Backup ──────────────────────────────────────────────────────────────────
  const [padraoEntrada, setPadraoEntrada] = useState('mono_220')
  const tipoInstalacao: 'monofasico' | 'trifasico' =
    padraoEntrada.startsWith('tri') ? 'trifasico' : 'monofasico'
  const [autonomia, setAutonomia] = useState('1')   // dias de autonomia
  const [backupRows, setBackupRows] = useState<BackupRow[]>([])
  const [consumoMensal, setConsumoMensal] = useState('')
  const [hspMedia, setHspMedia] = useState<number | null>(null)
  const [cidadeLabel, setCidadeLabel] = useState('')
  const [ufEntrega, setUfEntrega] = useState('')
  const [tipoFrete, setTipoFrete] = useState<TipoFrete | null>(null)
  const [showAddLoad, setShowAddLoad] = useState(false)

  // Potência FV auto-calculada (consumo ÷ (30 × HSP × PR)) enquanto o usuário não edita à mão
  useEffect(() => {
    if (kwpEdited) return
    const c = parseFloat(consumoMensal)
    const pr = parseFloat(taxaDesempenho)
    if (c > 0 && hspMedia && pr > 0 && pr <= 1) {
      setPowerpeakKwp((c / (30 * hspMedia * pr)).toFixed(2))
    }
  }, [consumoMensal, hspMedia, taxaDesempenho, kwpEdited])

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
      perfil_usuario: perfil,
      tipo_frete: tipoFrete ?? undefined,
      uf_entrega: tipoFrete === 'cif' ? ufEntrega || undefined : undefined,
    }

    if (tipo === 'backup') {
      payload.cargas_backup = backupRows.map(r => ({
        nome: r.nome, qtd: r.qtd, pnom_w: r.pnom_w, fp: r.fp, fd: r.fd,
        ip_in: r.ip_in, tdia_h: r.tdia_h, tensao: r.tensao,
      }))
      payload.tipo_instalacao = tipoInstalacao
      payload.padrao_entrada = padraoEntrada
      payload.autonomia_dias = parseFloat(autonomia)
      payload.eficiencia_roundtrip = 90
      const consumoNum = parseFloat(consumoMensal)
      if (consumoNum > 0 && hspMedia) {
        payload.consumo_medio_mensal_kwh = consumoNum
        payload.hsp_media = hspMedia
      }
      // ── FV opcional ────────────────────────────────────────────────────────
      const kwpNum = parseFloat(powerpeakKwp)
      const prNum = parseFloat(taxaDesempenho)
      if (kwpNum > 0) payload.powerpeak_kwp = kwpNum
      if (prNum > 0 && prNum <= 1) payload.taxa_desempenho = prNum
      if (fixingType) payload.fixing_type = fixingType
    } else {
      payload.consumo_ponta_kwh = arbConsumoPonta.map(v => parseFloat(v) || 0)
      payload.demanda_ponta_kw  = arbDemandaPonta.map(v => parseFloat(v) || 0)
      payload.tarifa_ponta_rs_kwh = parseFloat(arbTarifaPonta)
      payload.tarifa_fora_ponta_rs_kwh = parseFloat(arbTarifaForaPonta)
    }

    try {
      const res = await calcular(payload)
      setResult(res)  // mostra os kits na mesma página (abaixo do formulário)
      setLastPayload(payload)  // guardado para "Escolher este kit" / "Editar cotação"
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

              {/* ── SEÇÃO: Sistema fotovoltaico ────────────────────────── */}
              <CollapsibleSection
                icon="☀️" title="Sistema fotovoltaico"
                subtitle="Geração on-grid (opcional) — módulos, inversor e estrutura"
                open={pv_ativo} onToggle={() => setPvAtivo(v => !v)}
              >
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {/* 1 — Consumo médio mensal */}
                  <div>
                    <label className="mb-1 block text-xs font-semibold text-ink/60">Consumo médio mensal (kWh)</label>
                    <input type="number" step="any" min={0} value={consumoMensal}
                      onChange={e => setConsumoMensal(e.target.value)} placeholder="ex: 1200"
                      className="w-full rounded-xl border border-ink/15 px-3 py-2 text-sm focus:border-primary focus:outline-none" />
                  </div>
                  {/* 2 — Cidade (HSP) */}
                  <div>
                    <label className="mb-1 block text-xs font-semibold text-ink/60">Cidade (HSP)</label>
                    <CityCombobox
                      value={cidadeLabel}
                      onSelect={city => { setHspMedia(city.hsp); setCidadeLabel(`${city.nome} - ${city.sigla}`) }}
                      placeholder="Buscar cidade..."
                    />
                    {hspMedia && <p className="mt-1 text-[11px] text-ink/40">HSP média: {hspMedia} kWh/m²/dia</p>}
                  </div>
                  {/* 3 — Taxa de desempenho */}
                  <div>
                    <label className="mb-1 block text-xs font-semibold text-ink/60">Taxa de desempenho (PR)</label>
                    <input type="number" step="0.01" min={0.5} max={1} value={taxaDesempenho}
                      onChange={e => setTaxaDesempenho(e.target.value)}
                      className="w-full rounded-xl border border-ink/15 px-3 py-2 text-sm focus:border-primary focus:outline-none" />
                    <p className="mt-1 text-[11px] text-ink/40">Performance ratio típico: 0.75–0.85</p>
                  </div>
                  {/* 4 — Potência FV (calculada, editável) */}
                  <div>
                    <div className="mb-1 flex items-center justify-between">
                      <label className="block text-xs font-semibold text-ink/60">Potência FV (kWp)</label>
                      {kwpEdited && parseFloat(consumoMensal) > 0 && hspMedia && (
                        <button type="button" onClick={() => setKwpEdited(false)}
                          className="text-[11px] text-primary hover:underline">↻ recalcular</button>
                      )}
                    </div>
                    <input type="number" step="0.01" min={0} value={powerpeakKwp}
                      onChange={e => { setKwpEdited(true); setPowerpeakKwp(e.target.value) }}
                      placeholder="calculada automaticamente"
                      className="w-full rounded-xl border border-ink/15 px-3 py-2 font-mono text-sm tabular-nums focus:border-primary focus:outline-none" />
                    <p className="mt-1 text-[11px] text-ink/40">
                      {kwpEdited ? 'Editada manualmente' : 'Calculada por consumo ÷ (30 × HSP × PR) — pode ajustar'}
                    </p>
                  </div>
                </div>
                {/* 5 — Tipo de estrutura */}
                <div>
                  <label className="mb-1 block text-xs font-semibold text-ink/60">Tipo de estrutura de fixação</label>
                  <select value={fixingType} onChange={e => setFixingType(e.target.value)}
                    className="w-full rounded-xl border border-ink/15 bg-white px-3 py-2 text-sm focus:border-primary focus:outline-none">
                    <option value="">Selecionar (opcional)</option>
                    <option value="tile_ceramic">Telha cerâmica</option>
                    <option value="tile_fiber_wood">Telha fibrocimento (terça madeira)</option>
                    <option value="tile_fiber_metal">Telha fibrometálica</option>
                    <option value="tile_metal_mini">Telha metálica — mini trilho baixo</option>
                    <option value="tile_metal_mini_high">Telha metálica — mini trilho alto</option>
                    <option value="tile_metal_long">Telha metálica ondulada</option>
                    <option value="tile_zipped">Telha zipada</option>
                    <option value="slab_portrait">Laje (retrato)</option>
                    <option value="ground_pratyc">Solo — Pratyc</option>
                    <option value="ground_ccs">Solo — CCS</option>
                  </select>
                </div>
              </CollapsibleSection>

              {/* ── SEÇÃO: Sistema de Backup ───────────────────────────── */}
              <CollapsibleSection
                icon="🔋" title="Sistema de Backup"
                subtitle="Cargas a alimentar na falta de energia (opcional)"
                open={backupAtivo} onToggle={() => setBackupAtivo(v => !v)}
              >
                {/* Alerta de incoerência (com tolerância p/ arredondamento) */}
                {(() => {
                  const energiaDiaria = subtotais.energia   // kWh/dia das cargas
                  const consumoNum = parseFloat(consumoMensal)
                  const incoerente = backupRows.length > 0 && consumoNum > 0 && consumoNum < energiaDiaria * 30 * 0.98
                  return incoerente ? (
                    <div className="rounded-xl border border-accent/40 bg-accent/[0.08] px-4 py-3 text-sm text-accent-dark">
                      ⚠ O consumo médio mensal informado ({consumoNum} kWh) é menor que a energia
                      diária das cargas × 30 ({(energiaDiaria * 30).toFixed(1)} kWh).
                      Verifique se os dados estão consistentes.
                    </div>
                  ) : null
                })()}

                <div className="mb-2 flex items-center justify-between">
                  <label className="block text-sm font-medium text-gray-700">Cargas da instalação</label>
                  <div className="flex gap-2">
                    {parseFloat(consumoMensal) > 0 && (
                      <button type="button"
                        onClick={() => {
                          const consumoNum = parseFloat(consumoMensal)
                          // carga constante que representa TODO o consumo do mês (24h/dia, IP/IN=1)
                          const pnomW = Math.round((consumoNum * 1000) / 30 / 24 * 100) / 100
                          insertRow({ nome: 'Consumo total (estimado)', categoria: 'Estimado',
                            qtd: 1, pnom_w: pnomW, fp: 1, fd: 1, ip_in: 1, tdia_h: 24,
                            tensao: tipoInstalacao === 'trifasico' ? '380' : '220', fase: tipoInstalacao })
                        }}
                        className="flex items-center gap-1 rounded-lg border border-primary/40 px-3 py-2 text-sm font-medium text-primary hover:bg-primary/5">
                        📊 Dimensionar considerando todo o consumo
                      </button>
                    )}
                    <button type="button" onClick={() => setShowAddLoad(true)}
                      className="flex items-center gap-1 rounded-lg border-2 border-primary px-3 py-2 text-sm font-medium text-primary hover:bg-primary/5">
                      <Plus size={16} /> Adicionar carga
                    </button>
                  </div>
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
                          {['Equipamento','Categoria','Qtd','Pot (W)','Uso diário (h)','FP','FD','IP/IN','Tensão','Fase','Pn (kVA)','Pp (kVA)','E (kWh)',''].map(h => (
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

                {/* Dias de autonomia (dentro da seção de backup) */}
                <div className="flex flex-col gap-3 rounded-2xl border border-primary/30 bg-primary/[0.04] p-5 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="font-display text-base font-bold text-ink">Dias de autonomia</p>
                    <p className="mt-0.5 text-xs text-ink/55">
                      Quantos dias o sistema deve atender com o perfil de uso diário acima.
                      A energia necessária = consumo diário das cargas × dias.
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <input type="number" min={1} step={1} value={autonomia}
                      onChange={e => setAutonomia(e.target.value)}
                      className="w-24 rounded-xl border border-primary/30 bg-white px-3 py-2 text-center font-mono text-lg font-semibold tabular-nums text-primary focus:border-primary focus:outline-none" />
                    <span className="text-sm font-medium text-ink/60">{Number(autonomia) === 1 ? 'dia' : 'dias'}</span>
                  </div>
                </div>
              </CollapsibleSection>
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

          {/* ── SEÇÃO: Localização e Frete (obrigatório) ─────────────────── */}
          <FreightSection
            tipoFrete={tipoFrete}
            onTipoFrete={setTipoFrete}
            ufEntrega={ufEntrega}
            onUfEntrega={setUfEntrega}
          />

          {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

          {(() => {
            const temCargas = backupRows.length > 0
            const temPv = parseFloat(powerpeakKwp) > 0
              || (parseFloat(consumoMensal) > 0 && hspMedia != null && parseFloat(taxaDesempenho) > 0)
            const temDados = tipo !== 'backup' || temCargas || temPv
            const freteOk = tipoFrete === 'fob' || (tipoFrete === 'cif' && ufEntrega !== '')
            const podeSubmeter = temDados && freteOk
            return (
              <>
                {!freteOk && (
                  <p className="rounded-lg border border-orange-200 bg-orange-50 px-3 py-2 text-sm text-orange-700">
                    Preencha a seção <strong>Localização e Frete</strong> antes de calcular.
                  </p>
                )}
                <button
                  type="submit"
                  disabled={isPending || !podeSubmeter}
                  className="w-full rounded-lg bg-primary px-4 py-3 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50"
                >
                  {isPending ? 'Buscando…' : 'Buscar kits'}
                </button>
              </>
            )
          })()}
        </form>

        {showAddLoad && (
          <AddLoadDialog
            loads={loads ?? []}
            defaultTensao={tipoInstalacao === 'trifasico' ? '380' : '220'}
            onInsert={insertRow}
            onClose={() => setShowAddLoad(false)}
          />
        )}

        {result && (
          result.kit_selecionado ? (
            <div className="mt-8 space-y-3">
              <h2 className="font-display text-xl font-bold tracking-tight text-ink">Opções de kit</h2>
              {result.frete && <FreteCard frete={result.frete as FreteInfo} />}
              <KitResult
                kit={result.kit_selecionado}
                itens={itensSugerido}
                onItensChange={setItensSugerido}
                titulo={result.kit_selecionado.rotulo ?? 'Kit sugerido'}
                energiaNecessariaKwh={result.energia_necessaria_kwh}
                kwpInstalado={result.kit_selecionado.kwp_instalado}
                solar={result.solar_dimensionamento}
                collapsible defaultOpen
                onEscolher={() => setPendingChoice({ kit: result.kit_selecionado!, itens: itensSugerido })}
              />
              {result.alternativas.map((alt, i) => (
                <KitResult
                  key={i}
                  kit={alt}
                  itens={itensAlternativas[i] ?? []}
                  onItensChange={its => setItensAlternativas(prev => prev.map((a, idx) => idx === i ? its : a))}
                  titulo={alt.rotulo ?? 'Kit alternativo'}
                  energiaNecessariaKwh={result.energia_necessaria_kwh}
                  kwpInstalado={alt.kwp_instalado}
                  collapsible defaultOpen={false}
                  onEscolher={() => setPendingChoice({ kit: alt, itens: itensAlternativas[i] ?? [] })}
                />
              ))}
            </div>
          ) : (
            <div className="mt-10 rounded-2xl border border-dashed border-ink/15 bg-white/60 px-6 py-12 text-center">
              <p className="font-display text-lg text-ink/70">Nenhum kit compatível</p>
              <p className="mt-1 text-sm text-ink/50">Ajuste os parâmetros e busque novamente.</p>
            </div>
          )
        )}

        {pendingChoice && (
          <SaveQuoteDialog
            onConfirm={confirmSaveQuote}
            onClose={() => setPendingChoice(null)}
            isPending={isSaving}
            isEdicao={!!editId}
            initialTitulo={editId ? ((editProject?.parametros as Record<string, unknown> | undefined)?.titulo as string | undefined) : undefined}
          />
        )}
      </div>
    )
  }

  return null
}

const UFS = ['AC','AL','AM','AP','BA','CE','DF','ES','GO','MA','MG','MS','MT','PA','PB','PE','PI','PR','RJ','RN','RO','RR','RS','SC','SE','SP','TO']

const UF_NAMES: Record<string, string> = {
  AC:'Acre', AL:'Alagoas', AM:'Amazonas', AP:'Amapá', BA:'Bahia',
  CE:'Ceará', DF:'Distrito Federal', ES:'Espírito Santo', GO:'Goiás',
  MA:'Maranhão', MG:'Minas Gerais', MS:'Mato Grosso do Sul', MT:'Mato Grosso',
  PA:'Pará', PB:'Paraíba', PE:'Pernambuco', PI:'Piauí', PR:'Paraná',
  RJ:'Rio de Janeiro', RN:'Rio Grande do Norte', RO:'Rondônia', RR:'Roraima',
  RS:'Rio Grande do Sul', SC:'Santa Catarina', SE:'Sergipe', SP:'São Paulo', TO:'Tocantins',
}

function FreightSection({ tipoFrete, onTipoFrete, ufEntrega, onUfEntrega }: {
  tipoFrete: TipoFrete | null
  onTipoFrete: (t: TipoFrete) => void
  ufEntrega: string
  onUfEntrega: (v: string) => void
}) {
  const preenchido = tipoFrete === 'fob' || (tipoFrete === 'cif' && ufEntrega !== '')
  const badge = tipoFrete === 'fob'
    ? 'FOB — Retirada no CD'
    : tipoFrete === 'cif' && ufEntrega
    ? `CIF — ${ufEntrega}`
    : null

  return (
    <div className={`rounded-2xl border bg-white shadow-card ${preenchido ? 'border-ink/10' : 'border-orange-300'}`}>
      <div className="flex items-center justify-between px-5 py-4">
        <div className="flex items-center gap-2">
          <MapPin size={16} className={preenchido ? 'text-primary' : 'text-orange-500'} />
          <div>
            <p className="font-display text-base font-bold text-ink">
              Localização e Frete
              {!preenchido && <span className="ml-2 text-xs font-normal text-orange-600">obrigatório</span>}
            </p>
            {badge
              ? <p className="text-xs text-ink/50">{badge}</p>
              : <p className="text-xs text-orange-500">Selecione o tipo de frete para continuar</p>
            }
          </div>
        </div>
      </div>

      <div className="space-y-4 border-t border-ink/10 px-5 py-4">
        {/* Tipo de frete */}
        <div>
          <p className="mb-2 text-xs font-semibold text-ink/60">Tipo de Frete</p>
          <div className="grid grid-cols-2 gap-2">
            {([
              { v: 'cif' as TipoFrete, label: 'CIF (Frete Incluso)', desc: 'Entregue no endereço do cliente' },
              { v: 'fob' as TipoFrete, label: 'FOB (Retirada no CD)', desc: 'Cliente retira no armazém — taxa WEG→CD' },
            ]).map(o => (
              <button
                key={o.v}
                type="button"
                onClick={() => onTipoFrete(o.v)}
                className={`rounded-xl border-2 px-4 py-3 text-left transition-colors ${
                  tipoFrete === o.v
                    ? 'border-primary bg-primary/5 text-primary'
                    : 'border-gray-200 text-gray-600 hover:border-gray-300'
                }`}
              >
                <p className="text-sm font-semibold">{o.label}</p>
                <p className="mt-0.5 text-xs text-ink/50">{o.desc}</p>
              </button>
            ))}
          </div>
        </div>

        {/* CIF: selecionar estado */}
        {tipoFrete === 'cif' && (
          <div>
            <p className="mb-2 text-xs font-semibold text-ink/60">Estado de entrega</p>
            <select
              value={ufEntrega}
              onChange={e => onUfEntrega(e.target.value)}
              className="w-full rounded-xl border border-ink/15 bg-white px-3 py-2 text-sm focus:border-primary focus:outline-none"
            >
              <option value="">Selecionar estado…</option>
              {UFS.map(uf => (
                <option key={uf} value={uf}>{uf} — {UF_NAMES[uf]}</option>
              ))}
            </select>
          </div>
        )}

        {/* FOB: informativo */}
        {tipoFrete === 'fob' && (
          <div className="rounded-xl border border-amber-100 bg-amber-50/60 px-4 py-3 text-sm text-amber-800">
            <p className="font-semibold">Taxa de transporte WEG → CD</p>
            <p className="mt-0.5 text-xs text-amber-700">
              Equivale a 1% do valor do kit. O resultado final mostrará o custo exato após selecionar o kit.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

// Seção colapsável (usada para Sistema fotovoltaico e Sistema de Backup)
function CollapsibleSection({ icon, title, subtitle, open, onToggle, children }: {
  icon: string; title: string; subtitle: string; open: boolean; onToggle: () => void; children: React.ReactNode
}) {
  return (
    <div className="rounded-2xl border border-ink/10 bg-white shadow-card">
      <button type="button" onClick={onToggle}
        className="flex w-full items-center justify-between px-5 py-4 text-left">
        <div>
          <p className="font-display text-base font-bold text-ink">{icon} {title}</p>
          <p className="text-xs text-ink/50">{subtitle}</p>
        </div>
        <span className="text-sm text-ink/40">{open ? '▲ ocultar' : '▼ configurar'}</span>
      </button>
      {open && <div className="space-y-3 border-t border-ink/10 px-5 py-4">{children}</div>}
    </div>
  )
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
