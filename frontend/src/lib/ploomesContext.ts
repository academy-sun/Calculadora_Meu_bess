/**
 * Interpretação do contexto que vem da proposta do Ploomes.
 *
 * O script do campo desenvolvedor (bridge) é um leitor burro: lê o texto cru dos
 * campos e manda pra cá. Toda a tradução mora aqui, na ferramenta, porque cada
 * conta de CRM escreve a estrutura de um jeito — mudar o de:para não pode exigir
 * recolar o script em cada conta.
 */

/** Valores canônicos aceitos pelo backend em `fixing_type`. */
export const FIXING_TYPES = [
  'tile_ceramic',
  'tile_fiber_wood',
  'tile_fiber_metal',
  'tile_metal_mini',
  'tile_metal_mini_high',
  'tile_metal_long',
  'tile_zipped',
  'slab_portrait',
  'ground_pratyc',
  'ground_ccs',
] as const

export type FixingType = (typeof FIXING_TYPES)[number]

// Marcas diacríticas combinantes (U+0300–U+036F). Construído a partir de string
// escapada de propósito: o caractere literal some em alguns editores/pipelines.
const DIACRITICOS = new RegExp('[\\u0300-\\u036f]', 'g')

function normalizar(s: string): string {
  return s
    .normalize('NFD')
    .replace(DIACRITICOS, '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
}

/** Rótulos conhecidos → canônico. Chaves já normalizadas por `normalizar`. */
const APELIDOS: Record<string, FixingType> = {}

function registrar(canonico: FixingType, ...rotulos: string[]) {
  for (const r of rotulos) APELIDOS[normalizar(r)] = canonico
}

registrar('tile_ceramic', 'Telhado Cerâmico', 'Telha Cerâmica', 'Cerâmico', 'Colonial')
registrar('tile_fiber_wood',
  'Telhado Fibrocimento Terça Madeira', 'Fibrocimento Madeira', 'Telha Fibrocimento (terça madeira)')
registrar('tile_fiber_metal',
  'Telhado Fibrocimento Terça Metálica', 'Fibrocimento Metálica', 'Telha Fibrometálica')
registrar('tile_metal_long', 'Telhado Metálico Ondulado', 'Telha Metálica Ondulada', 'Metálico Ondulado')
registrar('tile_metal_mini',
  'Telhado Metálico Mini Trilho - 0,55m - baixo(2cm)',
  'Telhado Metálico Mini Trilho Longo - 2,40m - baixo(2cm)',
  'Mini Trilho Baixo')
registrar('tile_metal_mini_high',
  'Telhado Metálico Mini Trilho - 0,55m - alto(10cm)',
  'Telhado Metálico Mini Trilho Longo - 2,40m - alto(10cm)',
  'Mini Trilho Alto')
registrar('tile_zipped', 'Telhado Zipado', 'Telha Zipada', 'Zipado')
registrar('slab_portrait', 'Laje em Retrato', 'Laje', 'Laje Retrato')
registrar('ground_pratyc', 'Especial Solo Pratyc', 'Solo Fixo Pratyc', 'Solo Fixo', 'Solo', 'Pratyc')
registrar('ground_ccs', 'Solo CCS', 'CCS')

const CANONICOS = new Set<string>(FIXING_TYPES)

/**
 * Texto da proposta → `fixing_type` canônico. Devolve '' quando não reconhece,
 * para o formulário ficar em branco em vez de escolher errado.
 *
 * Ordem: já-canônico → rótulo conhecido → heurística por palavra-chave.
 */
export function normalizarFixingType(raw: string | null | undefined): FixingType | '' {
  if (!raw) return ''
  const bruto = String(raw).trim()
  if (!bruto) return ''

  // 1) o campo já vem na nomenclatura do fixing_type
  const direto = bruto.toLowerCase()
  if (CANONICOS.has(direto)) return direto as FixingType

  // 2) rótulo conhecido do CRM
  const n = normalizar(bruto)
  if (APELIDOS[n]) return APELIDOS[n]

  // 3) heurística — cobre variações de escrita entre contas
  const tem = (...termos: string[]) => termos.every(t => n.includes(t))
  if (tem('ceram') || tem('colonial')) return 'tile_ceramic'
  if (tem('zipad')) return 'tile_zipped'
  if (tem('laje')) return 'slab_portrait'
  if (tem('ccs')) return 'ground_ccs'
  if (tem('solo')) return 'ground_pratyc'
  if (tem('fibrometal')) return 'tile_fiber_metal'
  if (tem('fibrocimento')) {
    if (tem('metal')) return 'tile_fiber_metal'
    if (tem('madeira')) return 'tile_fiber_wood'
  }
  if (tem('trilho')) {
    // "alto(10cm)" vs "baixo(2cm)"
    return n.includes('alto') ? 'tile_metal_mini_high' : 'tile_metal_mini'
  }
  if (tem('metal') && tem('ondulad')) return 'tile_metal_long'
  return ''
}

const UFS = new Set([
  'AC', 'AL', 'AM', 'AP', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MG', 'MS', 'MT',
  'PA', 'PB', 'PE', 'PI', 'PR', 'RJ', 'RN', 'RO', 'RR', 'RS', 'SC', 'SE', 'SP', 'TO',
])

/**
 * UF a partir do texto de cidade da proposta. Aceita as formas que aparecem nas
 * contas: "LONDRINA-PR", "Londrina - PR", "Londrina/PR", "Londrina (PR)" e a UF
 * sozinha. Devolve '' se não achar uma UF válida — nunca chuta.
 */
export function extrairUF(raw: string | null | undefined): string {
  if (!raw) return ''
  const bruto = String(raw).trim().toUpperCase()
  if (!bruto) return ''

  if (UFS.has(bruto)) return bruto

  // última sequência de 2 letras precedida por separador ou parêntese
  const m = bruto.match(/[-/(,\s]\s*([A-Z]{2})\s*\)?\s*$/)
  if (m && UFS.has(m[1])) return m[1]

  // fallback: qualquer token de 2 letras que seja UF válida, do fim para o começo
  const tokens = bruto.split(/[^A-Z]+/).filter(Boolean)
  for (let i = tokens.length - 1; i >= 0; i--) {
    if (tokens[i].length === 2 && UFS.has(tokens[i])) return tokens[i]
  }
  return ''
}
