// Padrão de entrada da unidade — a lista de opções vivia copiada em três
// telas (botões do projeto novo, select do embed, rótulo do detalhe). Quando o
// bifásico entrou, manter as três em dia manualmente seria só questão de tempo
// até uma delas ficar para trás.

export type PadraoEntrada =
  | 'mono_127' | 'mono_220'
  | 'bi_127_220' | 'bi_220_380'
  | 'tri_127_220' | 'tri_220_380'

export type FaseInstalacao = 'monofasico' | 'bifasico' | 'trifasico'

export const PADROES_ENTRADA: {
  v: PadraoEntrada; l: string; s: string; fase: FaseInstalacao
}[] = [
  { v: 'mono_127',    l: 'Monofásico', s: '127 V',     fase: 'monofasico' },
  { v: 'mono_220',    l: 'Monofásico', s: '220 V',     fase: 'monofasico' },
  { v: 'bi_127_220',  l: 'Bifásico',   s: '127/220 V', fase: 'bifasico'   },
  { v: 'bi_220_380',  l: 'Bifásico',   s: '220/380 V', fase: 'bifasico'   },
  { v: 'tri_127_220', l: 'Trifásico',  s: '127/220 V', fase: 'trifasico'  },
  { v: 'tri_220_380', l: 'Trifásico',  s: '220/380 V', fase: 'trifasico'  },
]

export const PADRAO_LABEL: Record<string, { l: string; s: string }> =
  Object.fromEntries(PADROES_ENTRADA.map(p => [p.v, { l: p.l, s: p.s }]))

/** Quantas fases o padrão tem. Era `startsWith('tri') ? 'tri' : 'mono'`, que
 *  classificava o bifásico como monofásico e mandava isso ao backend. */
export function faseDoPadrao(padrao: string): FaseInstalacao {
  return PADROES_ENTRADA.find(p => p.v === padrao)?.fase ?? 'monofasico'
}

/** Tensão sugerida para uma carga nova, dado o padrão: a maior que a
 *  instalação oferece. Num 127/220 a carga típica de backup é 220 V. */
export function tensaoPadraoDaCarga(padrao: string): string {
  return padrao.endsWith('_380') ? '380' : padrao === 'mono_127' ? '127' : '220'
}
