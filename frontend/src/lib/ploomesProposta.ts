/**
 * Deriva os campos que vão para a proposta do Ploomes a partir do kit escolhido.
 *
 * Fica separado da página para poder ser testado sem montar o React — são
 * números que vão parar numa proposta comercial, então erram caro.
 */
import type { KitInfo, KitItem } from '@/types'

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

/** Energia armazenável do kit — mesma soma que o card usa para a cobertura. */
export function energiaTotalKwh(itens: KitItem[]): number {
  return itens.reduce((s, it) => s + (it.energia_unit_kwh ?? 0) * it.qtd, 0)
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

export interface ResumoProposta {
  qtd_modulos: number | null
  kwp_sistema: number | null
  descricao_modulos: string
  descricao_inversores: string
  descricao_baterias: string
  cobertura_pct: number | null
  autonomia_dias: number | null
  itens_html: string
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
): ResumoProposta {
  const itens = kit.itens ?? []
  const energia = energiaTotalKwh(itens)

  const temBase = !!energiaNecessariaKwh && energiaNecessariaKwh > 0 && energia > 0
  const cobertura = temBase ? (energia / energiaNecessariaKwh!) * 100 : null

  const dias = autonomiaSolicitadaDias && autonomiaSolicitadaDias > 0
    ? autonomiaSolicitadaDias : null
  const autonomia = cobertura != null && dias != null ? (cobertura / 100) * dias : null

  const qtdModulos = qtdDaCategoria(itens, TIPO_MODULO)

  return {
    qtd_modulos: qtdModulos > 0 ? qtdModulos : null,
    kwp_sistema: kit.kwp_instalado ?? null,
    descricao_modulos: descreverItens(itens, TIPO_MODULO),
    descricao_inversores: descreverItens(itens, TIPO_INVERSOR),
    descricao_baterias: descreverItens(itens, TIPO_BATERIA),
    cobertura_pct: cobertura != null ? Math.round(cobertura * 10) / 10 : null,
    autonomia_dias: autonomia != null ? Math.round(autonomia * 10) / 10 : null,
    itens_html: montarTabelaItensHtml(itens),
  }
}
