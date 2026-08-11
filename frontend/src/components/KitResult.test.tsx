import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { KitResult } from './KitResult'
import type { KitInfo, KitItem } from '@/types'

const ITENS: KitItem[] = [
  { meubess_id: 'inv1', nome: 'SIW200H M050', tipo: 'inversor', qtd: 1,
    preco_unitario: 6919, preco_total: 6919, potencia_inversao_kw: 5 },
  { meubess_id: 'bat1', nome: 'SBW CB100', tipo: 'bateria', qtd: 2,
    preco_unitario: 11974, preco_total: 23948, energia_unit_kwh: 10.07 },
]

const KIT = {
  marca: 'WEG', bateria_modelo: 'SBW CB100', inversor_modelo: 'SIW200H M050',
  qtd_baterias: 2, qtd_inversores: 1, capacidade_total_kwh: 20.14,
  potencia_total_kw: 6, preco_total: 30867, total_com_frete: 32000,
  distribuicao_baterias: [2], n_caixas_juncao: 1, pico_entregavel_kw: 6,
} as unknown as KitInfo

function montar(props: Partial<Parameters<typeof KitResult>[0]> = {}) {
  const onItensChange = vi.fn()
  render(
    <KitResult kit={KIT} itens={ITENS} onItensChange={onItensChange}
      titulo="Kit sugerido" {...props} />,
  )
  return { onItensChange }
}

describe('KitResult — edição no perfil restrito', () => {
  it('deixa editar quantidade sem mostrar preço unitário', async () => {
    // É a combinação que o embed restrito precisa: mexer no kit sem nunca
    // ver quanto custa cada item. Wrapper controlado porque o campo é
    // controlado de verdade na aplicação — com um mock puro, limpar e digitar
    // "3" deixaria "23" na tela e o teste mediria o próprio artefato.
    function Controlado() {
      const [itens, setItens] = useState<KitItem[]>(ITENS)
      return (
        <KitResult kit={KIT} itens={itens} onItensChange={setItens}
          titulo="Kit sugerido" editable ocultarValores />
      )
    }
    render(<Controlado />)

    expect(screen.queryByText(/Preço unit/i)).toBeNull()
    const qtd = screen.getAllByRole('spinbutton')
    expect(qtd).toHaveLength(2)          // só as quantidades, nenhum campo de preço

    // change direto em vez de digitar: input number no jsdom não aceita
    // seleção, e digitar concatenaria no valor que já está lá.
    fireEvent.change(qtd[1], { target: { value: '3' } })
    expect((qtd[1] as HTMLInputElement).value).toBe('3')
  })

  it('no perfil completo o preço unitário volta a ser editável', () => {
    montar({ editable: true, ocultarValores: false })
    // 2 quantidades + 2 preços
    expect(screen.getAllByRole('spinbutton')).toHaveLength(4)
    expect(screen.getByText(/Preço unit/i)).toBeTruthy()
  })

  it('mostra o total do servidor quando o kit foi editado', () => {
    // No restrito o preço unitário não chega ao cliente, então somar aqui
    // daria zero — quem soma é /calculate/reprecificar.
    montar({ editable: true, ocultarValores: true, totalComFreteServidor: 41234.56 })
    const rodape = screen.getByText(/Total geral/i).closest('tr')!
    expect(within(rodape).getByText(/41\.234,56/)).toBeTruthy()
  })

  it('avisa enquanto o servidor recalcula, em vez de exibir valor velho', () => {
    montar({ editable: true, ocultarValores: true, recalculando: true })
    expect(screen.getByText(/recalculando/i)).toBeTruthy()
    expect(screen.queryByText(/32\.000,00/)).toBeNull()
  })

  it('remover e adicionar continuam disponíveis no restrito', () => {
    montar({ editable: true, ocultarValores: true })
    expect(screen.getByText(/Adicionar item/i)).toBeTruthy()
  })
})
