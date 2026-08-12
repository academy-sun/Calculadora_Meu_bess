import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { FaseCarga, NumeroCarga, TensaoCarga } from './CampoCarga'

describe('campos de edição da carga', () => {
  it('número devolve valor numérico e trata campo vazio como 0', () => {
    function W() {
      const [v, setV] = useState(3)
      return (<><NumeroCarga value={v} onChange={setV} /><span>v={v}</span></>)
    }
    render(<W />)
    const input = screen.getByRole('spinbutton')
    fireEvent.change(input, { target: { value: '7' } })
    expect(screen.getByText('v=7')).toBeTruthy()
    // Apagar o campo não pode virar NaN: NaN em qtd propaga para Pn, Pp e E,
    // e a tabela inteira mostra "NaN".
    fireEvent.change(input, { target: { value: '' } })
    expect(screen.getByText('v=0')).toBeTruthy()
  })

  it('tensão é lista fechada com os três valores que a R8 compara', () => {
    // Texto livre viraria "220V" ou "220 " e a regra de compatibilidade
    // deixaria de casar sem erro nenhum.
    render(<TensaoCarga value="220" onChange={() => {}} />)
    const opcoes = Array.from(screen.getByRole('combobox').querySelectorAll('option'))
    expect(opcoes.map(o => o.value)).toEqual(['127', '220', '380'])
  })

  it('fase é lista fechada no vocabulário do motor', () => {
    render(<FaseCarga value="trifasico" onChange={() => {}} />)
    const opcoes = Array.from(screen.getByRole('combobox').querySelectorAll('option'))
    expect(opcoes.map(o => o.value)).toEqual(['monofasico', 'bifasico', 'trifasico'])
    expect((screen.getByRole('combobox') as HTMLSelectElement).value).toBe('trifasico')
  })

  it('fase vazia cai em monofásico em vez de ficar sem seleção', () => {
    render(<FaseCarga value="" onChange={() => {}} />)
    expect((screen.getByRole('combobox') as HTMLSelectElement).value).toBe('monofasico')
  })
})
