/**
 * Métricas derivadas dos itens de um kit.
 *
 * Vivem aqui, e não no componente que as exibe, porque também alimentam os
 * campos da proposta no Ploomes — importar o componente arrastaria o cliente
 * Supabase junto, que não tem o que fazer nesse caminho.
 */
import type { KitItem } from '@/types'

/** Tipos de item que o motor emite para inversor. O híbrido é 'inversor';
 *  'inversor_hibrido' é o vocabulário do CATÁLOGO e não deve chegar aqui. */
const TIPOS_INVERSOR = ['inversor', 'inversor_string']

/**
 * Réplica exata de `_distribuir` + `_pico_dc_kw` em kit_builder.py (backend): distribui as
 * baterias uniformemente entre as entradas (1 slot por entrada física, cada um com seu próprio
 * limite de corrente do inversor a que pertence), trunca a corrente por entrada e converte em kW.
 * Mantida idêntica ao motor — qualquer aproximação aqui pode causar erro de dimensionamento.
 */
export function calcPotenciaPartidaKw(itens: KitItem[]): number {
  const inversores = itens.filter(
    it => TIPOS_INVERSOR.includes(String(it.tipo || '').toLowerCase())
      && it.potencia_pico_kw != null)
  const baterias = itens.filter(it => it.tipo === 'bateria' && it.corrente_pico_a != null && it.tensao_v != null)
  const picoInvTotal = inversores.reduce((s, inv) => s + (inv.potencia_pico_kw ?? 0) * inv.qtd, 0)
  if (inversores.length === 0 || baterias.length === 0) return picoInvTotal

  const slots: number[] = []
  for (const inv of inversores) {
    const nEntradas = (inv.entradas_bateria ?? 0) * inv.qtd
    for (let i = 0; i < nEntradas; i++) slots.push(inv.corrente_entrada_a ?? 0)
  }
  if (slots.length === 0) return picoInvTotal

  const nBaterias = baterias.reduce((s, b) => s + b.qtd, 0)
  const correntePico = baterias[0].corrente_pico_a ?? 0
  const tensao = baterias[0].tensao_v ?? 0

  const base = Math.floor(nBaterias / slots.length)
  const extra = nBaterias % slots.length
  const dist = slots.map((_, i) => base + (i < extra ? 1 : 0))

  const totalA = dist.reduce((s, n, i) => s + (n > 0 ? Math.min(n * correntePico, slots[i]) : 0), 0)
  const picoDc = (totalA * tensao) / 1000

  return Math.min(picoDc, picoInvTotal)
}

/** Energia armazenável do kit — soma da energia unitária das baterias. */
export function energiaTotalKwh(itens: KitItem[]): number {
  return itens.reduce((s, it) => s + (it.energia_unit_kwh ?? 0) * it.qtd, 0)
}

/** Potência total de inversão — soma dos inversores, híbridos e string.
 *
 * Filtra por tipo em vez de somar o campo onde quer que ele apareça: uma
 * bateria que viesse com potencia_inversao_kw preenchido entrava na conta e
 * inflava o número (visto em campo: 25,1 kW num kit de 16,2). */
export function potenciaInversaoKw(itens: KitItem[]): number {
  return itens
    .filter(it => TIPOS_INVERSOR.includes(String(it.tipo || '').toLowerCase()))
    .reduce((s, it) => s + (it.potencia_inversao_kw ?? 0) * it.qtd, 0)
}
