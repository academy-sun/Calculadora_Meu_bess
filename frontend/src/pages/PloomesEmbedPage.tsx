import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Plus, CheckCircle2 } from 'lucide-react'
import { useCalculate } from '@/hooks/useProjects'
import { useStandardLoads } from '@/hooks/useCatalog'
import { AddLoadDialog } from '@/components/AddLoadDialog'
import type { LoadRowInput } from '@/components/AddLoadDialog'
import { FreightSection } from '@/components/FreightSection'
import { KitResult } from '@/components/KitResult'
import { DiagnosticoKit } from '@/components/DiagnosticoKit'
import { extrairUF, normalizarFixingType, rotuloFixingType } from '@/lib/ploomesContext'
import { resumoParaProposta } from '@/lib/ploomesProposta'
import { definirApiKey } from '@/lib/api'
import { reprecificarKit } from '@/lib/kitEdicao'
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

// Mesmas fórmulas da tabela de cargas do NewProjectPage (paridade visual)
const rowPn = (r: BackupRow) => (r.qtd * r.pnom_w) / (r.fp || 1) / 1000
const rowPp = (r: BackupRow) => rowPn(r) * (r.ip_in || 1)
const rowE = (r: BackupRow) => (r.qtd * r.pnom_w * r.tdia_h) / 1000

export function PloomesEmbedPage() {
  const [searchParams] = useSearchParams()
  const kwpParam = searchParams.get('kwp')
  const ufParam = searchParams.get('uf')
  const fixingTypeParam = searchParams.get('fixing_type')
  const perfil = searchParams.get('perfil') ?? 'consultor'

  const { mutateAsync: calcular, isPending: calculando } = useCalculate()
  const { data: loads } = useStandardLoads(true)

  // ── Formulário (pré-preenchido pelo bridge via query string) ────────────────
  // A query string também passa pelo de:para — o bridge pode mandar o rótulo do
  // CRM em vez do valor canônico.
  const ufInicial = extrairUF(ufParam)
  const [kwp, setKwp] = useState(kwpParam ?? '')
  const [fixingType, setFixingType] = useState<string>(normalizarFixingType(fixingTypeParam))
  const [padraoEntrada, setPadraoEntrada] = useState('mono_220')
  const [autonomia, setAutonomia] = useState('1')
  const [rows, setRows] = useState<BackupRow[]>([])
  const [showAddLoad, setShowAddLoad] = useState(false)
  const [tipoFrete, setTipoFrete] = useState<TipoFrete | null>(ufInicial ? 'cif' : null)
  const [ufEntrega, setUfEntrega] = useState(ufInicial)

  // ── Resultado / envio ───────────────────────────────────────────────────────
  const [result, setResult] = useState<CalculateResponse | null>(null)
  // Itens editáveis do kit sugerido. Ficam fora de `result` porque a
  // resposta do cálculo é o que o servidor mandou; isto é o que o vendedor
  // montou, e é isso que vai para a proposta no clique.
  // Um estado por kit da tela: 0 é o sugerido, 1..n as alternativas. As
  // alternativas também são editáveis, e cada uma tem o próprio total.
  const [itensPorKit, setItensPorKit] = useState<Record<number, KitItem[]>>({})
  const [totalPorKit, setTotalPorKit] = useState<Record<number, number>>({})
  const [recalculandoKit, setRecalculandoKit] = useState<Record<number, boolean>>({})
  const [editadoKit, setEditadoKit] = useState<Record<number, boolean>>({})
  const [ultimaEdicao, setUltimaEdicao] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [enviado, setEnviado] = useState(false)
  const [contextoRecebido, setContextoRecebido] = useState(false)
  // Só habilita o cálculo depois que o campo desenvolvedor mandar a chave:
  // calcular antes usaria a do build e devolveria o payload completo mesmo
  // no campo do usuário final.
  const [configRecebida, setConfigRecebida] = useState(false)
  // Modo de TELA. A fronteira de dado é a chave, conferida no servidor; isto
  // aqui só decide o que desenhar antes da primeira resposta chegar (o frete,
  // por exemplo, é escolhido antes de calcular). Depois que `result` existe,
  // `result.perfil` é quem manda.
  const [modoUI, setModoUI] = useState<'completo' | 'restrito'>('completo')

  // Canal com o campo desenvolvedor: o bridge envia 'ploomes:context' com os
  // valores ATUAIS da proposta (no load e sempre que o consultor clicar em
  // "Puxar valores da proposta") — atualiza o formulário sem recarregar o
  // iframe, preservando as cargas já digitadas.
  useEffect(() => {
    function onMessage(e: MessageEvent) {
      const d = e.data
      if (!d || typeof d !== 'object') return

      // A chave de API vem do campo desenvolvedor, não do build. É ela que
      // decide o perfil da resposta no servidor: o campo de admin carrega a
      // chave completa, o do usuário final carrega a restrita. Se as duas
      // estivessem no bundle (que é público), ler o JavaScript daria acesso
      // ao payload completo.
      if (d.type === 'ploomes:config' && typeof d.apiKey === 'string') {
        definirApiKey(d.apiKey)
        if (d.modo === 'restrito') {
          setModoUI('restrito')
          setTipoFrete('cif')   // sem opção de FOB neste perfil
        }
        setConfigRecebida(true)
        return
      }

      if (d.type !== 'ploomes:context') return
      if (d.kwp != null && d.kwp !== '') setKwp(String(d.kwp))

      // O bridge manda o texto cru dos campos (`estrutura`/`cidade`); o de:para
      // mora aqui para não depender de recolar o script em cada conta de CRM.
      // `fixing_type`/`uf` continuam aceitos por compatibilidade com a v3.
      const fixing = normalizarFixingType(d.estrutura ?? d.fixing_type)
      if (fixing) setFixingType(fixing)

      const uf = extrairUF(d.cidade ?? d.uf)
      if (uf) {
        setUfEntrega(uf)
        setTipoFrete(prev => prev ?? 'cif')
      }
      setContextoRecebido(true)
    }
    window.addEventListener('message', onMessage)
    // avisa o bridge que a página está pronta para receber o contexto
    window.parent.postMessage({ type: 'meubess:ready' }, '*')
    return () => window.removeEventListener('message', onMessage)
  }, [])

  const tipoInstalacao: 'monofasico' | 'trifasico' =
    padraoEntrada.startsWith('tri') ? 'trifasico' : 'monofasico'

  function handleTipoFrete(t: TipoFrete) {
    setTipoFrete(t)
    if (t === 'cif' && !ufEntrega && ufInicial) setUfEntrega(ufInicial)
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
        // `fase` é o que impede um inversor mono de "atender" carga trifásica —
        // sem ele o backend só vê a tensão, e trifásico 220 passa por 220 mono
        ip_in: r.ip_in, tdia_h: r.tdia_h, tensao: r.tensao, fase: r.fase,
      }))
    }
    try {
      const res = await calcular(payload)
      setResult(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao calcular')
    }
  }

  /**
   * Escreve o kit na proposta. `itensAtuais` é o que está na tela AGORA —
   * antes, o kit original do servidor ia para a proposta mesmo depois de
   * editado, e a diferença passava despercebida.
   */
  async function aplicarNaProposta(kit: KitInfo, idxKit = 0) {
    const itensAtuais = itensPorKit[idxKit]
    const editou = !!editadoKit[idxKit]
    // Kit que não cobre a energia pedida (a "alternativa mais econômica" é
    // sub-dimensionada de propósito). Vale para qualquer kit abaixo de 100%,
    // não só o rotulado como econômico: o risco de aplicar sem perceber é o
    // mesmo venha de onde vier.
    if (kit.cobertura_energia != null && kit.cobertura_energia < 1) {
      const pct = (kit.cobertura_energia * 100).toLocaleString('pt-BR', { maximumFractionDigits: 0 })
      const kwhKit = kit.capacidade_total_kwh.toLocaleString('pt-BR', { maximumFractionDigits: 1 })
      const kwhPedido = (result?.energia_necessaria_kwh ?? 0)
        .toLocaleString('pt-BR', { maximumFractionDigits: 1 })
      const ok = window.confirm(
        `Este kit cobre ${kwhKit} dos ${kwhPedido} kWh pedidos (${pct}% da autonomia).\n\n`
        + `Aplicar mesmo assim?`,
      )
      if (!ok) return
    }

    const itens: KitItem[] = itensAtuais ?? kit.itens ?? []
    // Kit editado: o total tem de vir do servidor. No perfil restrito o
    // preço unitário nem chega aqui, e mesmo no completo o frete CIF muda
    // de faixa com o preço — somar na tela erraria na virada.
    let totalServidorAplicar = totalPorKit[idxKit] ?? null
    if (itensAtuais && editou) {
      try {
        const r = await reprecificarKit(
          itens, tipoFrete, tipoFrete === 'cif' ? ufEntrega : null)
        totalServidorAplicar = r.total_com_frete
      } catch {
        window.alert('Não foi possível recalcular o total do kit editado. '
          + 'Tente novamente antes de aplicar à proposta.')
        return
      }
    }
    // arredonda ANTES de enviar — float sujo (ex. 62822.489999999996) fazia a
    // máscara de moeda do Ploomes interpretar os dígitos extras como milhares
    const round2 = (v: number) => Math.round(v * 100) / 100
    // Valores vêm do servidor, que calcula o frete de CADA kit na faixa de
    // preço correta. A estimativa que se fazia aqui reaplicava o percentual do
    // kit sugerido a outro preço e errava quando a alternativa caía em outra
    // faixa. No perfil restrito esses campos nem chegam — daí os null.
    const restrito = result?.perfil === 'restrito'
    // Com kit editado o preço do kit sai da soma dos itens (perfil completo,
    // onde os unitários existem); no restrito continua null, como antes.
    const precoItens = itens.reduce((acc, it) => acc + it.preco_unitario * it.qtd, 0)
    const kitPreco = restrito ? null : round2(editou ? precoItens : kit.preco_total)
    const freteValor = restrito || kit.frete_valor == null
      ? null
      : round2(editou && totalServidorAplicar != null
          ? totalServidorAplicar - precoItens
          : kit.frete_valor)
    const totalGeral = round2(
      totalServidorAplicar ?? kit.total_com_frete ?? kit.preco_total)
    const freteDescricao = result?.frete
      ? ((result.frete as FreteInfo).tipo === 'fob'
          ? 'FOB — Retirada no CD'
          : `CIF — ${(result.frete as FreteInfo).uf}`)
      : null
    // Texto puro só como fallback; o campo é um TinyMCE e recebe a tabela HTML.
    const itensTexto = itens.map(it => `${it.qtd}× ${it.nome}`).join(' | ')
    // itens do momento do clique: é deles que saem a tabela de Itens do
    // Kit, as descrições, energia, potências, cobertura e kWp. Antes tudo
    // isso vinha de kit.itens e a proposta contradizia o preço aplicado.
    const resumo = resumoParaProposta(
      kit,
      result?.energia_necessaria_kwh,
      parseFloat(autonomia) || null,
      rows,
      rotuloFixingType(fixingType),
      itens,
    )

    // Kit sem bateria (on-grid puro): o template híbrido produzia
    // "— — Sistema FV On-Grid + 0× —", porque marca/bateria vêm vazias.
    // Descrição derivada dos itens da tela, não dos campos do kit original:
    // trocar a quantidade de baterias ou o inversor tem de aparecer aqui.
    const baterias = itens.filter(i => i.tipo === 'bateria')
    const inversores = itens.filter(i => i.tipo.startsWith('inversor'))
    const qtdBaterias = baterias.reduce((s, i) => s + i.qtd, 0)
    const semBateria = qtdBaterias === 0
    const kwpTxt = resumo.kwp_sistema
      ? `${resumo.kwp_sistema.toLocaleString('pt-BR', { maximumFractionDigits: 2 })} kWp`
      : null
    const nomeInversores = inversores.length
      ? inversores.map(i => (i.qtd > 1 ? `${i.qtd}× ` : '') + i.nome).join(' + ')
      : kit.inversor_modelo
    const kitDescricao = semBateria
      ? [nomeInversores || 'Sistema FV On-Grid', kwpTxt].filter(Boolean).join(' — ')
      : `${kit.marca} — ${nomeInversores} + ${baterias.map(b => `${b.qtd}× ${b.nome}`).join(' + ')}`
    // string decimal com vírgula, sem milhar — formato que a máscara de moeda
    // pt-BR do Ploomes interpreta corretamente ao ser "digitado" via script
    const brStr = (v: number | null) => v == null ? '' : v.toFixed(2).replace('.', ',')
    const brNum = (v: number | null, casas: number) =>
      v == null ? '' : v.toFixed(casas).replace('.', ',')

    // No perfil restrito, valor do kit e frete saem como null e o bridge não
    // escreve esses dois campos — é o que impede o usuário final de segmentar
    // o total. Os outros 16 campos continuam sendo preenchidos normalmente.
    window.parent.postMessage({
      type: 'meubess:saved',
      perfil: result?.perfil ?? 'completo',
      kit_descricao: kitDescricao,
      kit_preco: kitPreco,
      kit_preco_str: brStr(kitPreco),
      frete_valor: freteValor,
      frete_valor_str: brStr(freteValor),
      frete_descricao: freteDescricao,
      total_geral: totalGeral,
      total_geral_str: brStr(totalGeral),
      itens_texto: itensTexto,
      itens_html: resumo.itens_html,

      // campos pré-existentes da proposta
      qtd_modulos: resumo.qtd_modulos,
      kwp_sistema: resumo.kwp_sistema,
      kwp_sistema_str: brNum(resumo.kwp_sistema, 2),
      // campos novos
      descricao_modulos: resumo.descricao_modulos,
      descricao_inversores: resumo.descricao_inversores,
      descricao_baterias: resumo.descricao_baterias,
      cobertura_pct: resumo.cobertura_pct,
      cobertura_pct_str: brNum(resumo.cobertura_pct, 1),
      autonomia_dias: resumo.autonomia_dias,
      autonomia_dias_str: brNum(resumo.autonomia_dias, 1),

      // métricas do kit (mesmos números do card) + contexto do dimensionamento
      energia_total_kwh: resumo.energia_total_kwh,
      energia_total_kwh_str: brNum(resumo.energia_total_kwh, 2),
      potencia_partida_kw: resumo.potencia_partida_kw,
      potencia_partida_kw_str: brNum(resumo.potencia_partida_kw, 1),
      potencia_inversao_kw: resumo.potencia_inversao_kw,
      potencia_inversao_kw_str: brNum(resumo.potencia_inversao_kw, 1),
      cargas_html: resumo.cargas_html,
      tipo_estrutura: resumo.tipo_estrutura,
    }, '*')
    setEnviado(true)
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  // Resultado novo do servidor: adota os itens dele e zera as edições.
  useEffect(() => {
    const mapa: Record<number, KitItem[]> = {}
    if (result?.kit_selecionado) mapa[0] = result.kit_selecionado.itens ?? []
    ;(result?.alternativas ?? []).forEach((a, i) => { mapa[i + 1] = a.itens ?? [] })
    setItensPorKit(mapa)
    setTotalPorKit({})
    setEditadoKit({})
    setUltimaEdicao(null)
  }, [result])

  function editarItens(idx: number, itens: KitItem[]) {
    setItensPorKit(m => ({ ...m, [idx]: itens }))
    setEditadoKit(m => ({ ...m, [idx]: true }))
    setUltimaEdicao(idx)
  }

  // Reprecifica SÓ depois de uma edição — a resposta do cálculo já vem com
  // os totais certos, e bater no servidor à toa a cada abertura só
  // adicionaria latência. Debounce porque quantidade se edita digitando.
  useEffect(() => {
    const idx = ultimaEdicao
    if (idx == null) return
    const itens = itensPorKit[idx] ?? []
    if (itens.length === 0) return
    let vivo = true
    setRecalculando(idx, true)
    const t = setTimeout(() => {
      reprecificarKit(itens, tipoFrete, tipoFrete === 'cif' ? ufEntrega : null)
        .then(r => {
          if (!vivo) return
          // Substitui pelos itens do servidor: eles voltam com os atributos
          // de engenharia (energia, potência) que o card usa para recalcular
          // cobertura e potência de partida, e que o item recém-adicionado
          // pelo picker do embed não tinha.
          setItensPorKit(m => ({ ...m, [idx]: r.itens }))
          setTotalPorKit(m => ({ ...m, [idx]: r.total_com_frete }))
        })
        .catch(() => { if (vivo) setTotalPorKit(m => { const n = { ...m }; delete n[idx]; return n }) })
        .finally(() => { if (vivo) setRecalculando(idx, false) })
    }, 400)
    return () => { vivo = false; clearTimeout(t) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ultimaEdicao, JSON.stringify((itensPorKit[ultimaEdicao ?? -1] ?? []).map(i => [i.meubess_id, i.qtd])), tipoFrete, ufEntrega])

  function setRecalculando(idx: number, v: boolean) {
    setRecalculandoKit(m => ({ ...m, [idx]: v }))
  }

  const restritoUI = (result?.perfil ?? modoUI) === 'restrito'

  const freteOk = tipoFrete === 'fob' || (tipoFrete === 'cif' && ufEntrega !== '')
  const temDados = parseFloat(kwp) > 0 || rows.length > 0
  // Falha FECHADA: sem a chave do campo, a página cairia na chave embutida no
  // build — que é a completa. Um campo de usuário final com script
  // desatualizado passaria a receber o payload inteiro sem ninguém perceber.
  // Melhor não calcular e dizer por quê.
  const podeCalcular = freteOk && temDados && configRecebida

  return (
    <div className="mx-auto max-w-3xl space-y-4 bg-paper p-4">
      {/* Sistema FV */}
      <div className="rounded-2xl border border-ink/10 bg-white px-5 py-4 shadow-card">
        <div className="mb-3 flex items-center justify-between">
          <p className="font-display text-base font-bold text-ink">☀️ Sistema fotovoltaico</p>
          {contextoRecebido && (
            <span className="rounded-full bg-green-50 px-2 py-0.5 text-[11px] font-medium text-green-700">
              ✓ valores da proposta
            </span>
          )}
        </div>
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
                  {['Equipamento','Qtd','Pot (W)','Uso (h/dia)','Tensão','IP/IN','Pn (kVA)','Pp (kVA)','E (kWh)',''].map(h => (
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
                    <td className="px-2 py-1.5 text-right tabular-nums text-gray-600">{rowPn(r).toFixed(2)}</td>
                    <td className="px-2 py-1.5 text-right tabular-nums text-gray-600">{rowPp(r).toFixed(2)}</td>
                    <td className="px-2 py-1.5 text-right tabular-nums text-gray-600">{rowE(r).toFixed(2)}</td>
                    <td className="px-2 py-1.5 text-center">
                      <button type="button" onClick={() => setRows(prev => prev.filter(x => x.id !== r.id))}
                        className="text-red-400 hover:text-red-600">✕</button>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-gray-300 bg-gray-50 font-semibold text-gray-700">
                  <td className="px-2 py-2 text-right" colSpan={6}>TOTAIS</td>
                  <td className="px-2 py-2 text-right tabular-nums">{rows.reduce((s, r) => s + rowPn(r), 0).toFixed(2)}</td>
                  <td className="px-2 py-2 text-right tabular-nums">{rows.reduce((s, r) => s + rowPp(r), 0).toFixed(2)}</td>
                  <td className="px-2 py-2 text-right tabular-nums">{rows.reduce((s, r) => s + rowE(r), 0).toFixed(2)}</td>
                  <td />
                </tr>
              </tfoot>
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
              <label className="mb-1 block text-xs font-semibold text-ink/60">Ciclos de autonomia</label>
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
        somenteCif={restritoUI}
      />

      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

      {!configRecebida && (
        <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          <b>Campo desconfigurado.</b> O script do campo desenvolvedor não
          enviou a chave de acesso — atualize-o para a versão 11
          (<code>docs/ploomes-bridge-script.md</code>). Sem ela o cálculo fica
          bloqueado, para não devolver dados de um perfil que não é o deste
          campo.
        </p>
      )}
      {configRecebida && !podeCalcular && (
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
            {/* Antes de apresentar ao cliente: o que o motor deixou de fora e por quê */}
            {!restritoUI && <DiagnosticoKit diagnostico={result.diagnostico} />}
            {enviado && (
              <p className="flex items-center gap-2 rounded-lg bg-green-50 px-3 py-2 text-sm text-green-700">
                <CheckCircle2 size={16} /> Kit aplicado à proposta — confira os campos no formulário.
              </p>
            )}
            <KitResult
              kit={result.kit_selecionado}
              itens={itensPorKit[0] ?? []}
              onItensChange={itens => editarItens(0, itens)}
              titulo={result.kit_selecionado.rotulo ?? 'Kit sugerido'}
              energiaNecessariaKwh={result.energia_necessaria_kwh}
              kwpInstalado={result.kit_selecionado.kwp_instalado}
              solar={result.solar_dimensionamento}
              frete={result.frete as FreteInfo | null | undefined}
              ocultarValores={restritoUI}
              editable
              pickerPorApiKey
              totalComFreteServidor={totalPorKit[0] ?? null}
              recalculando={!!recalculandoKit[0]}
              collapsible defaultOpen
              onEscolher={() => aplicarNaProposta(result.kit_selecionado!, 0)}
              escolherLabel="Aplicar à proposta"
            />
            {result.alternativas.map((alt, i) => (
              <KitResult
                key={i}
                kit={alt}
                itens={itensPorKit[i + 1] ?? []}
                onItensChange={itens => editarItens(i + 1, itens)}
                titulo={alt.rotulo ?? 'Kit alternativo'}
                energiaNecessariaKwh={result.energia_necessaria_kwh}
                kwpInstalado={alt.kwp_instalado}
                frete={result.frete && alt.frete_valor != null
                  ? { ...(result.frete as FreteInfo), valor: alt.frete_valor }
                  : undefined}
                ocultarValores={restritoUI}
                editable
                pickerPorApiKey
                totalComFreteServidor={totalPorKit[i + 1] ?? null}
                recalculando={!!recalculandoKit[i + 1]}
                collapsible defaultOpen={false}
                onEscolher={() => aplicarNaProposta(alt, i + 1)}
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
