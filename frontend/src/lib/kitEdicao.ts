import { apiGet, apiPost } from '@/lib/api'
import type { KitItem } from '@/types'

/** Produto do catálogo servido por API key (embed). `price` vem null no
 *  perfil restrito — a omissão é do servidor, não da tela. */
export interface ProdutoParaKit {
  meubess_id: string
  title: string
  marca: string
  tipo: string
  price: number | null
}

export interface KitReprecificado {
  itens: KitItem[]
  preco_total: number
  frete_valor: number | null
  total_com_frete: number
}

export function buscarProdutosParaKit(f: {
  titulo?: string; tipo?: string; marca?: string
  potencia_min?: number; potencia_max?: number
}) {
  const p = new URLSearchParams()
  if (f.titulo) p.set('q', f.titulo)
  if (f.tipo) p.set('tipo', f.tipo)
  if (f.marca) p.set('marca', f.marca)
  if (f.potencia_min != null) p.set('potencia_min', String(f.potencia_min))
  if (f.potencia_max != null) p.set('potencia_max', String(f.potencia_max))
  const qs = p.toString()
  return apiGet<ProdutoParaKit[]>(`/calculate/produtos${qs ? `?${qs}` : ''}`, true)
}

/**
 * Preços e totais do kit editado, calculados no servidor.
 *
 * Manda só id e quantidade: é tudo que o cliente sabe no perfil restrito, onde
 * o preço unitário não trafega. A resposta traz de volta os itens completos —
 * inclusive os atributos de engenharia (energia, potência) que o card usa para
 * recalcular cobertura e potência de partida.
 */
export function reprecificarKit(
  itens: KitItem[],
  tipoFrete?: string | null,
  ufEntrega?: string | null,
) {
  return apiPost<KitReprecificado>('/calculate/reprecificar', {
    itens: itens
      .filter(i => i.meubess_id)
      .map(i => ({ meubess_id: i.meubess_id, qtd: i.qtd })),
    tipo_frete: tipoFrete ?? null,
    uf_entrega: ufEntrega ?? null,
  }, true)
}
