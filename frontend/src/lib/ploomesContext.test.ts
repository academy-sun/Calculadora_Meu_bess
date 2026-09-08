import { describe, expect, it } from 'vitest'

import { FIXING_TYPES, extrairUF, normalizarFixingType, rotuloFixingType } from './ploomesContext'

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

describe('rotuloFixingType', () => {
  it('traduz o código canônico para o texto do formulário', () => {
    expect(rotuloFixingType('tile_ceramic')).toBe('Telha cerâmica')
    expect(rotuloFixingType('ground_pratyc')).toBe('Solo — Pratyc')
    expect(rotuloFixingType('tile_metal_mini_high')).toBe('Telha metálica — mini trilho alto')
  })

  it('aceita o rótulo do CRM e devolve o texto padronizado', () => {
    expect(rotuloFixingType('Telhado Cerâmico')).toBe('Telha cerâmica')
  })

  it('nunca deixa o código interno vazar para a proposta', () => {
    for (const t of FIXING_TYPES) {
      expect(rotuloFixingType(t)).not.toMatch(/^[a-z_]+$/)
    }
  })

  it('valor não reconhecido volta como veio, sem perder informação', () => {
    expect(rotuloFixingType('Telhado Shingle')).toBe('Telhado Shingle')
  })

  it('vazio continua vazio', () => {
    expect(rotuloFixingType('')).toBe('')
    expect(rotuloFixingType(null)).toBe('')
  })
})

describe('estrutura da Lumie Solar', () => {
  // O campo "Tipo de estrutura" da conta deles tem TRÊS opções, contra as dez
  // da calculadora. O de:para não virou tabela nova: a heurística de
  // normalizarFixingType já resolve os três rótulos. Estes testes existem para
  // travar isso — se alguém mexer na heurística, o prefill de um cliente em
  // produção não pode quebrar em silêncio.
  //
  // Os rótulos vêm da tabela de opções 1062167, lidos pela API, não do print.
  it('Cerâmico / fibrocimento cai em telha cerâmica', () => {
    // Rótulo ambíguo por natureza: cita as duas estruturas, que têm preços
    // diferentes. Cerâmica é o desempate, e o vendedor troca na tela se for
    // fibrocimento.
    expect(normalizarFixingType('Cerâmico / fibrocimento')).toBe('tile_ceramic')
  })

  it('Estrutura de Solo cai em solo Pratyc', () => {
    expect(normalizarFixingType('Estrutura de Solo')).toBe('ground_pratyc')
  })

  it('Metálico / trapezoidal (mini trilho) cai em mini trilho baixo', () => {
    // Sem "alto" no rótulo, o baixo é o desempate — é o caso comum.
    expect(normalizarFixingType('Metálico / trapezoidal (mini trilho)'))
      .toBe('tile_metal_mini')
  })
})
