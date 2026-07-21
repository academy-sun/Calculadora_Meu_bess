import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Plus, CheckCircle2 } from 'lucide-react'
import { useCalculate } from '@/hooks/useProjects'
import { useStandardLoads } from '@/hooks/useCatalog'
import { AddLoadDialog } from '@/components/AddLoadDialog'
import type { LoadRowInput } from '@/components/AddLoadDialog'
import { FreightSection, estimarFreteParaPreco } from '@/components/FreightSection'
import { KitResult } from '@/components/KitResult'
import type { CalculateResponse, FreteInfo, KitInfo, KitItem, TipoFrete } from '@/types'

/**
 * Página embed para o campo desenvolvedor do Ploomes.
 *
 *   Ploomes (formulário da proposta) → campo desenvolvedor (script bridge)
 *     → <iframe src=".../embed/ploomes?kwp=8.5&uf=PR&fixing_type=tile_ceramic">
 *
 * O bridge lê os campos já preenchidos na proposta (Potência adequada, Cidade,
 * Estrutura) via PloomesDocument e passa os valores por query string — nada de
 * API/deal_id aqui, o formulário pode nem estar salvo ainda.
 *
 * Sem login Supabase (iframe de terceiro bloqueia cookies/storage) — a chamada
 * a /calculate usa a API key embutida no build (X-API-Key).
 *
 * Ao escolher um kit, a página NÃO grava nada no Ploomes diretamente — ela só
 * envia `postMessage({type:'meubess:saved', ...})` para o campo desenvolvedor,
 * que escreve nos campos da proposta via PloomesDocument (setAttribute +
 * dispatchEvent), em tempo real, antes de qualquer salvamento.
 */

type BackupRow = LoadRowInput & { id: string }

export function PloomesEmbedPage() {
  const [searchParams] = useSearchParams()
  const kwpParam = searchParams.get('kwp')
  const ufParam = searchParams.get('uf')
  const fixingTypeParam = searchParams.get('fixing_type')
  const perfil = searchParams.get('perfil') ?? 'consultor'

  const { mutateAsync: calcular, isPending: calculando } = useCalculate()
  const { data: loads } = useStandardLoads(true)

  // ── Formulário (pré-preenchido pelo bridge via query string) ────────────────
  const [kwp, setKwp] = useState(kwpParam ?? '')
  const [fixingType, setFixingType] = useState(fixingTypeParam ?? '')
  const [padraoEntrada, setPadraoEntrada] = useState('mono_220')
  const [autonomia, setAutonomia] = useState('1')
  const [rows, setRows] = useState<BackupRow[]>([])
  const [showAddLoad, setShowAddLoad] = useState(false)
  const [tipoFrete, setTipoFrete] = useState<TipoFrete | null>(ufParam ? 'cif' : null)
  const [ufEntrega, setUfEntrega] = useState(ufParam ?? '')

  // ── Resultado / envio ───────────────────────────────────────────────────────
  const [result, setResult] = useState<CalculateResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [enviado, setEnviado] = useState(false)

  const tipoInstalacao: 'monofasico' | 'trifasico' =
    padraoEntrada.startsWith('tri') ? 'trifasico' : 'monofasico'

  function handleTipoFrete(t: TipoFrete) {
    setTipoFrete(t)
    if (t === 'cif' && !ufEntrega && ufParam) setUfEntrega(ufParam)
  }

  async function handleCalcular() {
    setError(null)
    setResult(null)
    setEnviado(false)
    const kwpNum = parseFloat(kwp)
    const payload: Record<string, unknown> = {
      origem_info: {
        origem: 'ploomes',
        solicitante_id: 'ploomes-embed',
        solicitante_nome: 'Ploomes (embed)',
        solicitado_em: new Date().toISOString(),
      },
      tipo_calculo: 'backup',
      perfil_usuario: perfil,
      tipo_frete: tipoFrete ?? undefined,
      uf_entrega: tipoFrete === 'cif' ? ufEntrega || undefined : undefined,
      padrao_entrada: padraoEntrada,
      tipo_instalacao: tipoInstalacao,
      autonomia_dias: parseFloat(autonomia) || 1,
      eficiencia_roundtrip: 90,
    }
    if (kwpNum > 0) payload.powerpeak_kwp = kwpNum
    if (fixingType) payload.fixing_type = fixingType
    if (rows.length > 0) {
      payload.cargas_backup = rows.map(r => ({
        nome: r.nome, qtd: r.qtd, pnom_w: r.pnom_w, fp: r.fp, fd: r.fd,
        ip_in: r.ip_in, tdia_h: r.tdia_h, tensao: r.tensao,
      }))
    }
    try {
      const res = await calcular(payload)
      setResult(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao calcular')
    }
  }

  function aplicarNaProposta(kit: KitInfo) {
    const itens: KitItem[] = kit.itens ?? []
    const kitPreco = itens.length > 0
      ? itens.reduce((s, it) => s + it.preco_unitario * it.qtd, 0)
      : kit.preco_total
    const frete = result?.frete
      ? estimarFreteParaPreco(result.frete as FreteInfo, kitPreco)
      : null
    const freteDescricao = frete
      ? (frete.tipo === 'fob' ? 'FOB — Retirada no CD' : `CIF — ${frete.uf}`)
      : null
    const itensTexto = itens
      .map(it => `${it.qtd}× ${it.nome} — ${it.preco_unitario.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}/un`)
      .join(' | ')

    window.parent.postMessage({
      type: 'meubess:saved',
      kit_descricao: `${kit.marca} — ${kit.inversor_modelo} + ${kit.qtd_baterias}× ${kit.bateria_modelo}`,
      kit_preco: kitPreco,
      frete_valor: frete?.valor ?? null,
      frete_descricao: freteDescricao,
      total_geral: kitPreco + (frete?.valor ?? 0),
      itens_texto: itensTexto,
    }, '*')
    setEnviado(true)
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  const freteOk = tipoFrete === 'fob' || (tipoFrete === 'cif' && ufEntrega !== '')
  const temDados = parseFloat(kwp) > 0 || rows.length > 0
  const podeCalcular = freteOk && temDados

  return (
    <div className="mx-auto max-w-3xl space-y-4 bg-paper p-4">
      {/* Sistema FV */}
      <div className="rounded-2xl border border-ink/10 bg-white px-5 py-4 shadow-card">
        <p className="mb-3 font-display text-base font-bold text-ink">☀️ Sistema fotovoltaico</p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-semibold text-ink/60">
              Potência FV (kWp) {kwpParam ? <span className="font-normal text-ink/40">— da proposta</span> : null}
            </label>
            <input type="number" step="0.01" min={0} value={kwp}
              onChange={e => setKwp(e.target.value)}
              placeholder="ex: 8.50"
              className="w-full rounded-xl border border-ink/15 px-3 py-2 font-mono text-sm tabular-nums focus:border-primary focus:outline-none" />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-ink/60">
              Tipo de estrutura {fixingTypeParam ? <span className="font-normal text-ink/40">— da proposta</span> : null}
            </label>
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
        </div>
      </div>

      {/* Cargas de backup */}
      <div className="rounded-2xl border border-ink/10 bg-white px-5 py-4 shadow-card">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <p className="font-display text-base font-bold text-ink">🔋 Cargas de backup</p>
            <p className="text-xs text-ink/50">Cargas críticas a alimentar na falta de energia (com tensão por carga)</p>
          </div>
          <button type="button" onClick={() => setShowAddLoad(true)}
            className="flex items-center gap-1 rounded-lg border-2 border-primary px-3 py-1.5 text-sm font-medium text-primary hover:bg-primary/5">
            <Plus size={15} /> Adicionar
          </button>
        </div>

        {rows.length > 0 ? (
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="w-full text-xs">
              <thead className="bg-gray-50">
                <tr className="text-left text-gray-500">
                  {['Equipamento','Qtd','Pot (W)','Uso (h/dia)','Tensão','IP/IN',''].map(h => (
                    <th key={h} className="px-2 py-2 font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map(r => (
                  <tr key={r.id} className="border-t border-gray-100">
                    <td className="px-2 py-1.5 font-medium text-ink">{r.nome}</td>
                    <td className="px-2 py-1.5 text-center tabular-nums">{r.qtd}</td>
                    <td className="px-2 py-1.5 text-center tabular-nums">{r.pnom_w}</td>
                    <td className="px-2 py-1.5 text-center tabular-nums">{r.tdia_h}</td>
                    <td className="px-2 py-1.5 text-center tabular-nums">{r.tensao} V</td>
                    <td className="px-2 py-1.5 text-center tabular-nums">{r.ip_in}</td>
                    <td className="px-2 py-1.5 text-center">
                      <button type="button" onClick={() => setRows(prev => prev.filter(x => x.id !== r.id))}
                        className="text-red-400 hover:text-red-600">✕</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="rounded-lg border border-dashed border-gray-200 px-3 py-4 text-center text-xs text-gray-400">
            Sem cargas — o kit será dimensionado só pelo FV (on-grid).
          </p>
        )}

        {rows.length > 0 && (
          <div className="mt-3 grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-semibold text-ink/60">Padrão de entrada</label>
              <select value={padraoEntrada} onChange={e => setPadraoEntrada(e.target.value)}
                className="w-full rounded-xl border border-ink/15 bg-white px-3 py-2 text-sm focus:border-primary focus:outline-none">
                <option value="mono_127">Monofásico 127 V</option>
                <option value="mono_220">Monofásico 220 V</option>
                <option value="tri_127_220">Trifásico 127/220 V</option>
                <option value="tri_220_380">Trifásico 220/380 V</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-ink/60">Dias de autonomia</label>
              <input type="number" min={1} step={1} value={autonomia}
                onChange={e => setAutonomia(e.target.value)}
                className="w-full rounded-xl border border-ink/15 px-3 py-2 text-center font-mono text-sm tabular-nums focus:border-primary focus:outline-none" />
            </div>
          </div>
        )}
      </div>

      {/* Frete (obrigatório) */}
      <FreightSection
        tipoFrete={tipoFrete}
        onTipoFrete={handleTipoFrete}
        ufEntrega={ufEntrega}
        onUfEntrega={setUfEntrega}
      />

      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

      {!podeCalcular && (
        <p className="rounded-lg border border-orange-200 bg-orange-50 px-3 py-2 text-xs text-orange-700">
          {!temDados && 'Informe a potência FV ou adicione cargas de backup. '}
          {!freteOk && 'Preencha a seção Localização e Frete.'}
        </p>
      )}

      <button
        type="button"
        onClick={handleCalcular}
        disabled={calculando || !podeCalcular}
        className="w-full rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-white transition hover:bg-primary-dark disabled:opacity-50"
      >
        {calculando ? 'Buscando…' : 'Buscar kits'}
      </button>

      {/* Resultado */}
      {result && (
        result.kit_selecionado ? (
          <div className="space-y-3">
            <h2 className="font-display text-lg font-bold text-ink">Opções de kit</h2>
            {enviado && (
              <p className="flex items-center gap-2 rounded-lg bg-green-50 px-3 py-2 text-sm text-green-700">
                <CheckCircle2 size={16} /> Kit aplicado à proposta — confira os campos no formulário.
              </p>
            )}
            <KitResult
              kit={result.kit_selecionado}
              itens={result.kit_selecionado.itens ?? []}
              onItensChange={() => {}}
              titulo={result.kit_selecionado.rotulo ?? 'Kit sugerido'}
              energiaNecessariaKwh={result.energia_necessaria_kwh}
              kwpInstalado={result.kit_selecionado.kwp_instalado}
              solar={result.solar_dimensionamento}
              frete={result.frete as FreteInfo | null | undefined}
              editable={false}
              collapsible defaultOpen
              onEscolher={() => aplicarNaProposta(result.kit_selecionado!)}
              escolherLabel="Aplicar à proposta"
            />
            {result.alternativas.map((alt, i) => (
              <KitResult
                key={i}
                kit={alt}
                itens={alt.itens ?? []}
                onItensChange={() => {}}
                titulo={alt.rotulo ?? 'Kit alternativo'}
                energiaNecessariaKwh={result.energia_necessaria_kwh}
                kwpInstalado={alt.kwp_instalado}
                frete={result.frete ? estimarFreteParaPreco(result.frete as FreteInfo, alt.preco_total) : undefined}
                editable={false}
                collapsible defaultOpen={false}
                onEscolher={() => aplicarNaProposta(alt)}
                escolherLabel="Aplicar à proposta"
              />
            ))}
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-ink/15 bg-white/60 px-6 py-8 text-center">
            <p className="font-display text-base text-ink/70">Nenhum kit compatível</p>
            <p className="mt-1 text-xs text-ink/50">Ajuste os parâmetros e busque novamente.</p>
          </div>
        )
      )}

      {showAddLoad && (
        <AddLoadDialog
          loads={loads ?? []}
          defaultTensao={tipoInstalacao === 'trifasico' ? '380' : '220'}
          onInsert={r => setRows(prev => [...prev, { id: crypto.randomUUID(), ...r }])}
          onClose={() => setShowAddLoad(false)}
          persistNew={false}
        />
      )}
    </div>
  )
}
