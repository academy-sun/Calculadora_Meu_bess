/**
 * Executa o script do campo desenvolvedor de verdade, nos dois modos.
 *
 * O script mora em docs/ploomes-bridge-script.md porque é colado no Ploomes,
 * não importado por build nenhum — e por isso nunca teve teste. São ~600
 * linhas de manipulação de DOM que decidem o que entra na proposta.
 *
 * O que este arquivo protege é a garantia central da separação de perfis: o
 * campo do usuário final NÃO escreve valor do kit nem valor do frete. É a
 * segunda das duas camadas (a primeira é o filtro do backend, em
 * test_calculate_perfil.py). Testar o texto do script não bastaria: o que
 * importa é o que sobra nos campos depois que ele roda.
 */

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { JSDOM } from 'jsdom'
import { describe, expect, it } from 'vitest'

const DOC = resolve(__dirname, '../../../docs/ploomes-bridge-script.md')

/** Extrai o conteúdo do <script> do bloco "## Script" do documento. */
function extrairScript(): string {
  const md = readFileSync(DOC, 'utf-8')
  const corpo = md.slice(md.indexOf('\n## Script'))
  const ini = corpo.indexOf('<script>')
  const fim = corpo.indexOf('</script>')
  if (ini < 0 || fim < 0) throw new Error('bloco <script> não encontrado no doc')
  return corpo.slice(ini + '<script>'.length, fim)
}

/** As chaves dos campos, lidas do próprio script — não duplicadas aqui. */
function chaves(script: string): Record<string, string> {
  const bloco = script.slice(script.indexOf('var FIELD_KEYS = {'))
  const out: Record<string, string> = {}
  for (const m of bloco.slice(0, bloco.indexOf('};')).matchAll(/(\w+):\s*'([^']+)'/g)) {
    out[m[1]] = m[2]
  }
  return out
}

const SCRIPT = extrairScript()
const KEYS = chaves(SCRIPT)

/** Payload equivalente ao que o embed manda no perfil COMPLETO. */
const RESULTADO_COMPLETO = {
  type: 'meubess:saved',
  perfil: 'completo',
  kit_descricao: 'WEG — SIW200H M050 + 2× CB100',
  kit_preco: 25989.37,
  kit_preco_str: '25989,37',
  frete_valor: 7900,
  frete_valor_str: '7900,00',
  frete_descricao: 'CIF — AC',
  total_geral: 33889.37,
  total_geral_str: '33889,37',
  itens_texto: '1× Inversor | 2× Bateria',
  itens_html: '<table><tr><td>1×</td><td>Inversor</td></tr></table>',
  qtd_modulos: 16,
  kwp_sistema: 8.8,
  kwp_sistema_str: '8,80',
  descricao_modulos: '16× Longi 635 Wp',
  descricao_inversores: '1× SIW200H M050',
  descricao_baterias: '2× SBW CB100',
  cobertura_pct: 97.4,
  cobertura_pct_str: '97,4',
  autonomia_dias: 1,
  autonomia_dias_str: '1,0',
  energia_total_kwh: 20.14,
  energia_total_kwh_str: '20,14',
  potencia_partida_kw: 6,
  potencia_partida_kw_str: '6,0',
  potencia_inversao_kw: 5,
  potencia_inversao_kw_str: '5,0',
  cargas_html: '<table><tr><td>Geladeira</td></tr></table>',
  tipo_estrutura: 'Telha cerâmica',
}

/** No perfil restrito o backend manda null nos dois campos monetários. */
const RESULTADO_RESTRITO = {
  ...RESULTADO_COMPLETO,
  perfil: 'restrito',
  kit_preco: null,
  kit_preco_str: '',
  frete_valor: null,
  frete_valor_str: '',
}

/**
 * Uma instância de DOM POR cenário.
 *
 * O script registra seu listener de 'message' no window ao ser executado, e
 * não expõe como removê-lo. Reaproveitando o window do vitest, o listener do
 * teste anterior continua vivo e responde à mensagem do seguinte — foi o que
 * fez o modo completo tentar escrever durante um teste do modo restrito.
 */
function cenario(modo: 'completo' | 'restrito') {
  const dom = new JSDOM(`<!doctype html><html><body>
    <div id="mb-widget">
      <button id="mb-pull"></button>
      <div id="mb-diag" style="display:none"></div>
      <iframe id="mb-iframe"></iframe>
    </div>
    ${Object.values(KEYS).map(k => `<input name="${k}" />`).join('')}
  </body></html>`)
  const { window: w } = dom
  const fonte = SCRIPT
    .replace("apiKey: 'COLE_AQUI_A_CHAVE'", `apiKey: 'K-TESTE-${modo}'`)
    .replace(/modo: '(restrito|completo)'/, `modo: '${modo}'`)
  // window/document como parâmetros: sombreiam os globais do vitest, para o
  // script agir só sobre este DOM.
  // eslint-disable-next-line no-new-func
  new Function('PloomesDocument', 'window', 'document', 'setTimeout', fonte)(
    w.document, w, w.document, setTimeout,
  )

  return {
    aplicar(d: unknown) {
      w.dispatchEvent(new w.MessageEvent('message', { data: d }))
    },
    valor(nome: string): string {
      const el = w.document.querySelector(`input[name="${KEYS[nome]}"]`) as HTMLInputElement | null
      if (!el) throw new Error(`campo ${nome} não montado no DOM de teste`)
      return el.value
    },
    temPainelDeConferencia(): boolean {
      return w.document.getElementById('mb-diag') !== null
    },
  }
}

describe('bridge do Ploomes — campos escritos por modo', () => {
  it('o doc expõe as chaves dos 18 campos de saída', () => {
    for (const nome of ['kit_descricao', 'kit_valor', 'frete_valor', 'total_geral',
      'itens_kit', 'cobertura_pct', 'autonomia_dias', 'energia_total',
      'potencia_partida', 'potencia_inversao', 'tabela_cargas', 'tipo_estrutura']) {
      expect(KEYS[nome], `chave ${nome} sumiu do script`).toMatch(/^quote_/)
    }
  })

  describe('modo completo (campo de admin)', () => {
    it('escreve valor do kit e do frete separados', () => {
      const c = cenario('completo')
      c.aplicar(RESULTADO_COMPLETO)
      expect(c.valor('kit_valor')).toBe('25989,37')
      expect(c.valor('frete_valor')).toBe('7900,00')
      expect(c.valor('total_geral')).toBe('33889,37')
    })

    it('mantém o painel de conferência', () => {
      expect(cenario('completo').temPainelDeConferencia()).toBe(true)
    })
  })

  describe('modo restrito (campo do usuário final)', () => {
    it('NÃO escreve valor do kit nem valor do frete', () => {
      const c = cenario('restrito')
      c.aplicar(RESULTADO_RESTRITO)
      expect(c.valor('kit_valor')).toBe('')
      expect(c.valor('frete_valor')).toBe('')
    })

    it('escreve o total (kit + frete) — o único valor que o usuário final vê', () => {
      const c = cenario('restrito')
      c.aplicar(RESULTADO_RESTRITO)
      expect(c.valor('total_geral')).toBe('33889,37')
    })

    it('escreve os demais campos normalmente', () => {
      const c = cenario('restrito')
      c.aplicar(RESULTADO_RESTRITO)
      expect(c.valor('kit_descricao')).toBe(RESULTADO_COMPLETO.kit_descricao)
      // Campos numéricos saem com PONTO: medido em campo que os decimais
      // (TypeId 6) e percentuais (TypeId 13) desta conta descartam a vírgula
      // na máscara e ficam vazios. Ver writeNumero no script.
      expect(c.valor('cobertura_pct')).toBe('97.4')
      expect(c.valor('autonomia_dias')).toBe('1.0')
      expect(c.valor('energia_total')).toBe('20.14')
      expect(c.valor('potencia_partida')).toBe('6.0')
      expect(c.valor('potencia_inversao')).toBe('5.0')
      expect(c.valor('tipo_estrutura')).toBe('Telha cerâmica')
      expect(c.valor('descricao_baterias')).toBe('2× SBW CB100')
    })

    it('remove o painel de conferência', () => {
      expect(cenario('restrito').temPainelDeConferencia()).toBe(false)
    })

    it('não escreve os valores nem se o backend mandá-los por engano', () => {
      // Cinto e suspensório: as duas camadas foram feitas para falhar
      // separado. Se um dia o filtro do servidor for afrouxado, o script
      // ainda assim não escreve.
      const c = cenario('restrito')
      c.aplicar(RESULTADO_COMPLETO)
      expect(c.valor('kit_valor')).toBe('')
      expect(c.valor('frete_valor')).toBe('')
      expect(c.valor('total_geral')).toBe('33889,37')
    })
  })
})
