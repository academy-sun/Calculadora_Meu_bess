import { describe, expect, it } from 'vitest'

import { extrairUF, normalizarFixingType } from './ploomesContext'

describe('normalizarFixingType', () => {
  it('aceita o valor canônico direto — caso do campo "Estrutura Requisição"', () => {
    expect(normalizarFixingType('tile_ceramic')).toBe('tile_ceramic')
    expect(normalizarFixingType('ground_pratyc')).toBe('ground_pratyc')
    expect(normalizarFixingType('  TILE_ZIPPED  ')).toBe('tile_zipped')
  })

  it('traduz os rótulos do Ploomes', () => {
    expect(normalizarFixingType('Telhado Cerâmico')).toBe('tile_ceramic')
    expect(normalizarFixingType('Telhado Fibrocimento Terça Madeira')).toBe('tile_fiber_wood')
    expect(normalizarFixingType('Telhado Fibrocimento Terça Metálica')).toBe('tile_fiber_metal')
    expect(normalizarFixingType('Telhado Metálico Ondulado')).toBe('tile_metal_long')
    expect(normalizarFixingType('Telhado Zipado')).toBe('tile_zipped')
    expect(normalizarFixingType('Laje em Retrato')).toBe('slab_portrait')
    expect(normalizarFixingType('Solo Fixo Pratyc')).toBe('ground_pratyc')
  })

  it('distingue mini trilho alto de baixo', () => {
    expect(normalizarFixingType('Telhado Metálico Mini Trilho - 0,55m - baixo(2cm)'))
      .toBe('tile_metal_mini')
    expect(normalizarFixingType('Telhado Metálico Mini Trilho Longo - 2,40m - alto(10cm)'))
      .toBe('tile_metal_mini_high')
  })

  it('ignora acentuação, caixa e espaçamento — cada conta escreve de um jeito', () => {
    expect(normalizarFixingType('TELHADO CERAMICO')).toBe('tile_ceramic')
    expect(normalizarFixingType('telhado   ceramico')).toBe('tile_ceramic')
    expect(normalizarFixingType('Telha Cerâmica')).toBe('tile_ceramic')
  })

  it('cai na heurística para variações não catalogadas', () => {
    expect(normalizarFixingType('Cobertura em telha ceramica portuguesa')).toBe('tile_ceramic')
    expect(normalizarFixingType('Estrutura de solo')).toBe('ground_pratyc')
    expect(normalizarFixingType('Telhado metalico ondulado trapezoidal')).toBe('tile_metal_long')
  })

  it('devolve vazio em vez de chutar quando não reconhece', () => {
    expect(normalizarFixingType('Micro Metal')).toBe('')
    expect(normalizarFixingType('Telhado Shingle')).toBe('')
    expect(normalizarFixingType('')).toBe('')
    expect(normalizarFixingType(null)).toBe('')
    expect(normalizarFixingType(undefined)).toBe('')
  })
})

describe('extrairUF', () => {
  it('lê o formato do campo de opção do Ploomes', () => {
    expect(extrairUF('LONDRINA-PR')).toBe('PR')
  })

  it('aceita as variações do campo de texto', () => {
    expect(extrairUF('Londrina - PR')).toBe('PR')
    expect(extrairUF('Londrina/PR')).toBe('PR')
    expect(extrairUF('Londrina (PR)')).toBe('PR')
    expect(extrairUF('Rio Branco, AC')).toBe('AC')
    expect(extrairUF('São Paulo - SP')).toBe('SP')
  })

  it('aceita a UF sozinha', () => {
    expect(extrairUF('PR')).toBe('PR')
    expect(extrairUF('pr')).toBe('PR')
  })

  it('não confunde sigla inválida com UF', () => {
    expect(extrairUF('Cidade - XX')).toBe('')
    expect(extrairUF('Londrina')).toBe('')
    expect(extrairUF('')).toBe('')
    expect(extrairUF(null)).toBe('')
  })

  it('não se perde com nome de cidade que termina em duas letras', () => {
    // "BA" aqui é o fim de "Bahia"? Não — o separador exige token isolado.
    expect(extrairUF('Barreiras - BA')).toBe('BA')
  })
})
