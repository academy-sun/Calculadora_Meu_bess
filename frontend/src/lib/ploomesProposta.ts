/**
 * Deriva os campos que vão para a proposta do Ploomes a partir do kit escolhido.
 *
 * Fica separado da página para poder ser testado sem montar o React — são
 * números que vão parar numa proposta comercial, então erram caro.
 */
import { calcPotenciaPartidaKw, energiaTotalKwh, potenciaInversaoKw } from '@/lib/kitMetrics'
import type { KitInfo, KitItem } from '@/types'

/** Uma linha da tabela de cargas do formulário. */
export interface CargaLinha {
  nome: string
  qtd: number
  pnom_w: number
  fp: number
  fd: number
  ip_in: number
  tdia_h: number
  tensao?: string
}

// Mesmas fórmulas da tabela exibida no formulário — a proposta não pode
// mostrar número diferente do que o consultor viu na tela.
export const cargaPnKva = (r: CargaLinha) => (r.qtd * r.pnom_w) / (r.fp || 1) / 1000
export const cargaPpKva = (r: CargaLinha) => cargaPnKva(r) * (r.ip_in || 1)
export const cargaEKwh = (r: CargaLinha) => (r.qtd * r.pnom_w * r.tdia_h) / 1000

// tipos de item produzidos pelos motores (engines/pv_kit.py, engines/kit_builder.py)
const TIPO_MODULO = ['modulo_fv']
const TIPO_INVERSOR = ['inversor', 'inversor_string']
const TIPO_BATERIA = ['bateria']

function daCategoria(itens: KitItem[], tipos: string[]): KitItem[] {
  return itens.filter(it => tipos.includes(String(it.tipo || '').toLowerCase()))
}

/** "16× W - 550 Wp - WEG - Módulo (Estoque)". Vários produtos viram "a + b". */
export function descreverItens(itens: KitItem[], tipos: string[], limite = 250): string {
  const txt = daCategoria(itens, tipos)
    .map(it => `${it.qtd}× ${it.nome}`)
    .join(' + ')
  return txt.length > limite ? txt.slice(0, limite - 1) + '…' : txt
}

export function qtdDaCategoria(itens: KitItem[], tipos: string[]): number {
  return daCategoria(itens, tipos).reduce((s, it) => s + it.qtd, 0)
}

function escaparHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

// O campo é um TinyMCE e o HTML vai para a proposta impressa, onde as classes
// CSS da nossa app não existem — por isso estilo inline em cada célula.
const BORDA = 'border:1px solid #000;padding:4px 8px;text-align:center'
// Sem largura na coluna e sem width:100% na tabela: o layout automático dimensiona
// cada coluna pelo conteúdo. Com width:100% a tabela esticava até a borda do editor
// e sobrava espaço vazio dos dois lados da descrição.
const COL_QTD = `${BORDA};white-space:nowrap`

/** Tabela de duas colunas (quantidade, descrição), sem valores unitários. */
export function montarTabelaItensHtml(itens: KitItem[]): string {
  if (!itens.length) return ''
  const linhas = itens
    .map(it => `<tr><td style="${COL_QTD}">${it.qtd}</td>` +
               `<td style="${BORDA}">${escaparHtml(it.nome)}</td></tr>`)
    .join('')
  return (
    `<table style="border-collapse:collapse;width:auto">` +
    `<thead><tr>` +
    `<th style="${COL_QTD};font-weight:bold">Quantidade</th>` +
    `<th style="${BORDA};font-weight:bold">Descrição</th>` +
    `</tr></thead>` +
    `<tbody>${linhas}</tbody></table>`
  )
}

const num = (v: number, casas: number) =>
  v.toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas })

/**
 * Tabela de cargas com as mesmas colunas e a mesma linha de totais que o
 * formulário mostra. Vai para um campo multilinha (TinyMCE), daí o estilo inline.
 */
export function montarTabelaCargasHtml(cargas: CargaLinha[]): string {
  if (!cargas.length) return ''
  const COLS = ['Equipamento', 'Qtd', 'Pot (W)', 'Uso (h/dia)', 'Tensão',
                'IP/IN', 'Pn (kVA)', 'Pp (kVA)', 'E (kWh)']
  const cabecalho = COLS
    .map(c => `<th style="${BORDA};font-weight:bold">${c}</th>`)
    .join('')
  const linhas = cargas.map(r => [
    escaparHtml(r.nome), r.qtd, r.pnom_w, num(r.tdia_h, 0),
    r.tensao ? `${r.tensao} V` : '—', r.ip_in,
    num(cargaPnKva(r), 2), num(cargaPpKva(r), 2), num(cargaEKwh(r), 2),
  ].map(v => `<td style="${BORDA}">${v}</td>`).join(''))
    .map(tds => `<tr>${tds}</tr>`).join('')

  const somaPn = cargas.reduce((s, r) => s + cargaPnKva(r), 0)
  const somaPp = cargas.reduce((s, r) => s + cargaPpKva(r), 0)
  const somaE = cargas.reduce((s, r) => s + cargaEKwh(r), 0)
  const totais =
    `<tr>` +
    `<td colspan="6" style="${BORDA};font-weight:bold">TOTAIS</td>` +
    `<td style="${BORDA};font-weight:bold">${num(somaPn, 2)}</td>` +
    `<td style="${BORDA};font-weight:bold">${num(somaPp, 2)}</td>` +
    `<td style="${BORDA};font-weight:bold">${num(somaE, 2)}</td>` +
    `</tr>`

  return `<table style="border-collapse:collapse;width:auto">` +
    `<thead><tr>${cabecalho}</tr></thead>` +
    `<tbody>${linhas}${totais}</tbody></table>`
}

export interface ResumoProposta {
  qtd_modulos: number | null
  kwp_sistema: number | null
  descricao_modulos: string
  descricao_inversores: string
  descricao_baterias: string
  cobertura_pct: number | null
  autonomia_dias: number | null
  itens_html: string
  energia_total_kwh: number | null
  potencia_partida_kw: number | null
  potencia_inversao_kw: number | null
  cargas_html: string
  tipo_estrutura: string
}

/**
 * @param energiaNecessariaKwh  E_BAT exigida = energia diária das cargas × dias
 *                              solicitados (backend: total_e_eps × autonomia_dias)
 * @param autonomiaSolicitadaDias  dias pedidos no formulário
 *
 * Cobertura e autonomia saem da mesma base, então são coerentes entre si:
 * autonomia real = cobertura × dias solicitados. Sem cargas (kit on-grid puro)
 * não há o que cobrir nem autonomia a informar — ambos ficam nulos.
 */
export function resumoParaProposta(
  kit: KitInfo,
  energiaNecessariaKwh: number | null | undefined,
  autonomiaSolicitadaDias: number | null | undefined,
  cargas: CargaLinha[] = [],
  tipoEstrutura = '',
  /** Itens como estão na tela. Sem isto TODOS os campos da proposta —
   *  tabela, descrições, energia, potências, cobertura — sairiam do kit
   *  original do servidor, ignorando o que o vendedor editou. */
  itensEditados?: KitItem[],
): ResumoProposta {
  const itens = itensEditados ?? kit.itens ?? []
  const energia = energiaTotalKwh(itens)

  const temBase = !!energiaNecessariaKwh && energiaNecessariaKwh > 0 && energia > 0
  const cobertura = temBase ? (energia / energiaNecessariaKwh!) * 100 : null

  const dias = autonomiaSolicitadaDias && autonomiaSolicitadaDias > 0
    ? autonomiaSolicitadaDias : null
  const autonomia = cobertura != null && dias != null ? (cobertura / 100) * dias : null

  const qtdModulos = qtdDaCategoria(itens, TIPO_MODULO)

  return {
    qtd_modulos: qtdModulos > 0 ? qtdModulos : null,
    kwp_sistema: kwpDosItens(itens) ?? kit.kwp_instalado ?? null,
    descricao_modulos: descreverItens(itens, TIPO_MODULO),
    descricao_inversores: descreverItens(itens, TIPO_INVERSOR),
    descricao_baterias: descreverItens(itens, TIPO_BATERIA),
    cobertura_pct: cobertura != null ? Math.round(cobertura * 10) / 10 : null,
    autonomia_dias: autonomia != null ? Math.round(autonomia * 10) / 10 : null,
    itens_html: montarTabelaItensHtml(itens),

    // mesmas métricas exibidas no card do kit, com as mesmas casas decimais
    energia_total_kwh: energia > 0 ? Math.round(energia * 100) / 100 : null,
    potencia_partida_kw: arredondar1(calcPotenciaPartidaKw(itens)),
    potencia_inversao_kw: arredondar1(potenciaInversaoKw(itens)),
    cargas_html: montarTabelaCargasHtml(cargas),
    tipo_estrutura: tipoEstrutura,
  }
}

/** kWp somado dos módulos que estão no kit AGORA.
 *
 * O kit_instalado do servidor descreve o kit que ELE montou. Trocar a
 * quantidade de módulos na tela mudava o preço e não mudava o kWp, e a
 * proposta saía com os dois números se contradizendo. Cai no valor do
 * servidor quando nenhum módulo traz o Wp (item antigo, em cache). */
function kwpDosItens(itens: KitItem[]): number | null {
  const wp = itens
    .filter(i => TIPO_MODULO.includes(i.tipo) && i.potencia_wp)
    .reduce((s, i) => s + (i.potencia_wp ?? 0) * i.qtd, 0)
  return wp > 0 ? Math.round(wp / 1000 * 1000) / 1000 : null
}

function arredondar1(v: number): number | null {
  return v > 0 ? Math.round(v * 10) / 10 : null
}
