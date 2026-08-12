/**
 * Campos de edição de uma linha da tabela de cargas.
 *
 * Extraídos porque a tabela existe em dois lugares — a calculadora interna e o
 * embed do Ploomes — e só a interna era editável. Duplicar o input teria
 * deixado as duas telas divergindo na primeira mudança de regra (o passo do
 * número, o piso, a lista de tensões).
 */

/** Número da tabela de cargas: quantidade, potência, horas, IP/IN. */
export function NumeroCarga({ value, onChange, titulo }: {
  value: number
  onChange: (v: number) => void
  titulo?: string
}) {
  return (
    <input type="number" step="any" min={0} value={value} title={titulo}
      onChange={e => onChange(parseFloat(e.target.value) || 0)}
      className="w-16 rounded border border-gray-200 px-1 py-0.5 text-center text-xs
                 tabular-nums focus:border-primary focus:outline-none" />
  )
}

/** Tensão da carga. Lista fechada porque é o que a R8 do motor compara — texto
 *  livre viraria "220V" ou "220 " e a regra deixaria de casar em silêncio. */
export function TensaoCarga({ value, onChange }: {
  value: string
  onChange: (v: string) => void
}) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)}
      className="w-16 rounded border border-gray-200 px-1 py-0.5 text-center text-xs
                 focus:border-primary focus:outline-none">
      <option value="127">127</option>
      <option value="220">220</option>
      <option value="380">380</option>
    </select>
  )
}

/** Fase da carga. Junto com a tensão é o que decide se o cenário existe na
 *  instalação — sem poder editá-la, uma carga marcada com a fase errada só
 *  podia ser corrigida apagando e recriando a linha. */
export function FaseCarga({ value, onChange }: {
  value: string
  onChange: (v: string) => void
}) {
  return (
    <select value={value || 'monofasico'} onChange={e => onChange(e.target.value)}
      className="w-20 rounded border border-gray-200 px-1 py-0.5 text-center text-xs
                 focus:border-primary focus:outline-none">
      <option value="monofasico">Mono</option>
      <option value="bifasico">Bi</option>
      <option value="trifasico">Tri</option>
    </select>
  )
}
