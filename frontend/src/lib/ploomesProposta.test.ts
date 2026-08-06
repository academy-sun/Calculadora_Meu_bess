import { describe, expect, it } from 'vitest'

import { montarTabelaCargasHtml, montarTabelaItensHtml, resumoParaProposta } from './ploomesProposta'
import type { KitInfo, KitItem } from '@/types'

const item = (p: Partial<KitItem>): KitItem => ({
  nome: 'X', tipo: 'acessorio', qtd: 1, preco_unitario: 0, preco_total: 0, ...p,
})

// kit híbrido do teste real: 1 inversor + 1 bateria + 15 módulos + acessórios
const KIT_HIBRIDO: KitInfo = {
  marca: 'WEG',
  bateria_modelo: 'W - Módulo de Bateria - SBW CB050 W00',
  inversor_modelo: 'W - WEG - 7,5KW 220V - SIW200H M075 W10 - Inversor Híbrido',
  qtd_baterias: 1, qtd_inversores: 1,
  capacidade_total_kwh: 5.0, potencia_total_kw: 7.5, preco_total: 23112.4,
  kwp_instalado: 8.25,
  itens: [
    item({ nome: 'W - WEG - 7,5KW 220V - SIW200H M075 W10 - Inversor Híbrido', tipo: 'inversor', qtd: 1, preco_unitario: 8654.16 }),
    item({ nome: 'W - Módulo de Bateria - SBW CB050 W00', tipo: 'bateria', qtd: 1, preco_unitario: 5987.03, energia_unit_kwh: 5.0 }),
    item({ nome: 'W - 550 Wp - WEG - Módulo (Estoque)', tipo: 'modulo_fv', qtd: 15, preco_unitario: 457.52 }),
    item({ nome: 'W - Conector MC4', tipo: 'acessorio', qtd: 3, preco_unitario: 7.95 }),
  ],
}

const KIT_ONGRID: KitInfo = {
  marca: '—', bateria_modelo: '—', inversor_modelo: 'Sistema FV On-Grid',
  qtd_baterias: 0, qtd_inversores: 1,
  capacidade_total_kwh: 0, potencia_total_kw: 0, preco_total: 10188.99,
  kwp_instalado: 8.8,
  itens: [
    item({ nome: 'W - 550 Wp - WEG - Módulo (Estoque)', tipo: 'modulo_fv', qtd: 16, preco_unitario: 457.52 }),
    item({ nome: 'W - WEG - 6,0KW 220V - SIW200G M060 W1', tipo: 'inversor_string', qtd: 1, preco_unitario: 2473.82 }),
  ],
}

describe('resumoParaProposta — kit híbrido', () => {
  // 5 kWh no kit sobre 3,68 kWh exigidos = 135,9%
  const r = resumoParaProposta(KIT_HIBRIDO, 3.68, 1)

  it('conta os módulos e leva o kWp do kit', () => {
    expect(r.qtd_modulos).toBe(15)
    expect(r.kwp_sistema).toBe(8.25)
  })

  it('descreve cada categoria no formato "N× nome"', () => {
    expect(r.descricao_modulos).toBe('15× W - 550 Wp - WEG - Módulo (Estoque)')
    expect(r.descricao_inversores).toBe('1× W - WEG - 7,5KW 220V - SIW200H M075 W10 - Inversor Híbrido')
    expect(r.descricao_baterias).toBe('1× W - Módulo de Bateria - SBW CB050 W00')
  })

  it('não inclui acessórios nas descrições por categoria', () => {
    expect(r.descricao_modulos).not.toContain('MC4')
    expect(r.descricao_inversores).not.toContain('MC4')
  })

  it('cobertura vem já multiplicada por 100', () => {
    expect(r.cobertura_pct).toBe(135.9)
  })

  it('autonomia real = cobertura × dias solicitados', () => {
    expect(r.autonomia_dias).toBe(1.4)             // 1,359 dia arredondado
    expect(resumoParaProposta(KIT_HIBRIDO, 3.68, 2).autonomia_dias).toBe(2.7)
  })

  it('cobertura não muda com os dias pedidos, autonomia sim', () => {
    // energia necessaria ja embute os dias, entao a cobertura se mantem
    const dois = resumoParaProposta(KIT_HIBRIDO, 7.36, 2)
    expect(dois.cobertura_pct).toBe(67.9)
    expect(dois.autonomia_dias).toBe(1.4)          // continua ~1,36 dia de fato
  })
})

describe('resumoParaProposta — on-grid puro', () => {
  const r = resumoParaProposta(KIT_ONGRID, null, 1)

  it('traz módulos e potência', () => {
    expect(r.qtd_modulos).toBe(16)
    expect(r.kwp_sistema).toBe(8.8)
    expect(r.descricao_modulos).toBe('16× W - 550 Wp - WEG - Módulo (Estoque)')
    expect(r.descricao_inversores).toBe('1× W - WEG - 6,0KW 220V - SIW200G M060 W1')
  })

  it('não inventa bateria, cobertura nem autonomia', () => {
    expect(r.descricao_baterias).toBe('')
    expect(r.cobertura_pct).toBeNull()
    expect(r.autonomia_dias).toBeNull()
  })
})

describe('montarTabelaItensHtml', () => {
  const html = montarTabelaItensHtml(KIT_HIBRIDO.itens!)

  it('tem as duas colunas pedidas, nessa ordem', () => {
    expect(html).toContain('>Quantidade<')
    expect(html).toContain('>Descrição<')
    expect(html.indexOf('>Quantidade<')).toBeLessThan(html.indexOf('>Descrição<'))
  })

  it('não expõe valores unitários', () => {
    expect(html).not.toContain('R$')
    expect(html).not.toContain('8.654,16')
    expect(html).not.toContain('/un')
  })

  it('traz todos os itens, inclusive acessórios', () => {
    expect((html.match(/<tr>/g) || []).length).toBe(5)   // cabeçalho + 4 itens
    expect(html).toContain('W - Conector MC4')
    expect(html).toContain('>15</td>')                   // qtd de módulos
    expect(html).toContain('>W - 550 Wp - WEG - Módulo (Estoque)</td>')
  })

  it('as duas colunas se ajustam ao conteúdo', () => {
    // sem width:100% a tabela não estica até a borda do editor
    expect(html).not.toContain('width:100%')
    expect(html).toContain('width:auto')
    // nenhuma coluna leva largura fixa; só a quantidade evita quebra de linha
    expect(html).not.toContain('width:1%')
    expect((html.match(/white-space:nowrap/g) || []).length).toBe(1 + 4)
  })

  it('cabeçalho em negrito, bordas e centralização em todas as células', () => {
    expect(html).toContain('font-weight:bold')
    expect((html.match(/border:1px solid #000/g) || []).length).toBe(2 + 4 * 2)
    expect((html.match(/text-align:center/g) || []).length).toBe(2 + 4 * 2)
    expect(html).toContain('border-collapse:collapse')
  })

  it('escapa HTML vindo do nome do produto', () => {
    const perigoso = montarTabelaItensHtml([item({ nome: 'Módulo <script>x</script>', qtd: 1 })])
    expect(perigoso).not.toContain('<script>')
    expect(perigoso).toContain('&lt;script&gt;')
  })

  it('kit sem itens não vira tabela vazia', () => {
    expect(montarTabelaItensHtml([])).toBe('')
  })
})

describe('métricas do kit', () => {
  it('energia total soma a energia unitária das baterias', () => {
    const r = resumoParaProposta(KIT_HIBRIDO, 3.68, 1)
    expect(r.energia_total_kwh).toBe(5)
  })

  it('potência de inversão soma os inversores', () => {
    const kit: KitInfo = {
      ...KIT_HIBRIDO,
      itens: [
        item({ nome: 'Híbrido', tipo: 'inversor', qtd: 1, potencia_inversao_kw: 7.5 }),
        item({ nome: 'String', tipo: 'inversor_string', qtd: 1, potencia_inversao_kw: 7.5 }),
        item({ nome: 'Bateria', tipo: 'bateria', qtd: 2, energia_unit_kwh: 5 }),
      ],
    }
    const r = resumoParaProposta(kit, 5, 1)
    expect(r.potencia_inversao_kw).toBe(15)
    expect(r.energia_total_kwh).toBe(10)
  })

  it('kit on-grid não tem energia de bateria nem potência de partida', () => {
    const r = resumoParaProposta(KIT_ONGRID, null, 1)
    expect(r.energia_total_kwh).toBeNull()
    expect(r.potencia_partida_kw).toBeNull()
  })
})

describe('montarTabelaCargasHtml', () => {
  const CARGAS = [
    { nome: 'AR CONDICIONADO - BTU 12000', qtd: 1, pnom_w: 1150, fp: 0.9, fd: 1, ip_in: 3, tdia_h: 8, tensao: '220' },
    { nome: 'GELADEIRA', qtd: 2, pnom_w: 200, fp: 1, fd: 1, ip_in: 1, tdia_h: 24, tensao: '127' },
  ]
  const html = montarTabelaCargasHtml(CARGAS)

  it('traz as 9 colunas do formulário, na ordem', () => {
    const heads = [...html.matchAll(/<th[^>]*>([^<]+)<\/th>/g)].map(m => m[1])
    expect(heads).toEqual(['Equipamento', 'Qtd', 'Pot (W)', 'Uso (h/dia)', 'Tensão',
                           'IP/IN', 'Pn (kVA)', 'Pp (kVA)', 'E (kWh)'])
  })

  it('calcula Pn, Pp e E com as fórmulas do formulário', () => {
    // 1 x 1150 / 0,9 / 1000 = 1,28 kVA; x IP/IN 3 = 3,83 kVA; 1150 x 8 / 1000 = 9,20 kWh
    expect(html).toContain('>1,28</td>')
    expect(html).toContain('>3,83</td>')
    expect(html).toContain('>9,20</td>')
  })

  it('fecha com a linha de TOTAIS somando as três colunas', () => {
    expect(html).toContain('TOTAIS')
    // 1,2778 + 0,4 = 1,68 | 3,8333 + 0,4 = 4,23 | 9,2 + 9,6 = 18,80
    expect(html).toContain('>1,68</td>')
    expect(html).toContain('>4,23</td>')
    expect(html).toContain('>18,80</td>')
    expect(html).toContain('colspan="6"')
  })

  it('mostra a tensão de cada carga', () => {
    expect(html).toContain('>220 V</td>')
    expect(html).toContain('>127 V</td>')
  })

  it('escapa o nome do equipamento', () => {
    const perigo = montarTabelaCargasHtml([{ ...CARGAS[0], nome: '<script>x</script>' }])
    expect(perigo).not.toContain('<script>')
  })

  it('sem cargas não gera tabela', () => {
    expect(montarTabelaCargasHtml([])).toBe('')
  })

  it('entra no resumo quando há cargas', () => {
    expect(resumoParaProposta(KIT_HIBRIDO, 3.68, 1, CARGAS).cargas_html).toContain('TOTAIS')
    expect(resumoParaProposta(KIT_HIBRIDO, 3.68, 1).cargas_html).toBe('')
  })
})

describe('tipo de estrutura no resumo', () => {
  it('passa adiante o rótulo recebido', () => {
    const r = resumoParaProposta(KIT_HIBRIDO, 3.68, 1, [], 'Telha cerâmica')
    expect(r.tipo_estrutura).toBe('Telha cerâmica')
  })

  it('fica vazio quando não houve estrutura no dimensionamento', () => {
    expect(resumoParaProposta(KIT_HIBRIDO, 3.68, 1).tipo_estrutura).toBe('')
  })
})
