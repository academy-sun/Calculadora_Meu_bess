import { describe, expect, it } from 'vitest'
import { calcPotenciaPartidaKw, potenciaInversaoKw } from './kitMetrics'
import type { KitItem } from '@/types'

/**
 * Regressão do que apareceu em campo depois que o kit virou editável: o
 * endpoint de reprecificação devolvia o tipo do CATÁLOGO ('inversor_hibrido')
 * em vez do tipo do ITEM ('inversor'), e preenchia potencia_inversao_kw em
 * todo produto. As métricas caíam junto.
 */
describe('métricas do kit não confundem bateria com inversor', () => {
  const S057: KitItem = { nome: 'S057', tipo: 'inversor', qtd: 1,
    preco_unitario: 0, preco_total: 0, potencia_inversao_kw: 5.7,
    potencia_pico_kw: 7.7, corrente_entrada_a: 50, entradas_bateria: 1 }
  const M105: KitItem = { nome: 'M105', tipo: 'inversor', qtd: 1,
    preco_unitario: 0, preco_total: 0, potencia_inversao_kw: 10.5,
    potencia_pico_kw: 12, corrente_entrada_a: 50, entradas_bateria: 1 }
  const CB100 = (qtd: number): KitItem => ({ nome: 'CB100', tipo: 'bateria', qtd,
    preco_unitario: 0, preco_total: 0, energia_unit_kwh: 10.07,
    corrente_pico_a: 65, tensao_v: 384 })

  it('soma só os inversores na potência de inversão', () => {
    expect(potenciaInversaoKw([S057, M105, CB100(3)])).toBeCloseTo(16.2, 2)
  })

  it('ignora potencia_inversao_kw que apareça numa bateria', () => {
    // Foi assim que 16,2 virou 25,1 na tela.
    const bateriaSuja = { ...CB100(3), potencia_inversao_kw: 3 } as KitItem
    expect(potenciaInversaoKw([S057, M105, bateriaSuja])).toBeCloseTo(16.2, 2)
  })

  it('potência de partida usa o inversor, não zera', () => {
    expect(calcPotenciaPartidaKw([S057, CB100(2)])).toBeGreaterThan(0)
  })

  it('tipo do catálogo em vez do tipo do item zerava a partida', () => {
    const comTipoErrado = { ...S057, tipo: 'inversor_hibrido' } as KitItem
    expect(calcPotenciaPartidaKw([comTipoErrado, CB100(2)])).toBe(0)
  })
})
