import { MapPin } from 'lucide-react'
import type { FreteInfo, TipoFrete } from '@/types'

/** Reaplica a regra de frete do kit sugerido a outro preço de kit (alternativas/kit editado). */
export function estimarFreteParaPreco(ref: FreteInfo, preco: number): FreteInfo {
  if (ref.tipo === 'fob') {
    return { ...ref, valor: Math.round(preco * ref.percentual * 100) / 100 }
  }
  const valorBruto = preco * ref.percentual
  return { ...ref, valor: Math.round(Math.max(valorBruto, ref.valor_minimo) * 100) / 100 }
}

export const UFS = ['AC','AL','AM','AP','BA','CE','DF','ES','GO','MA','MG','MS','MT','PA','PB','PE','PI','PR','RJ','RN','RO','RR','RS','SC','SE','SP','TO']

export const UF_NAMES: Record<string, string> = {
  AC:'Acre', AL:'Alagoas', AM:'Amazonas', AP:'Amapá', BA:'Bahia',
  CE:'Ceará', DF:'Distrito Federal', ES:'Espírito Santo', GO:'Goiás',
  MA:'Maranhão', MG:'Minas Gerais', MS:'Mato Grosso do Sul', MT:'Mato Grosso',
  PA:'Pará', PB:'Paraíba', PE:'Pernambuco', PI:'Piauí', PR:'Paraná',
  RJ:'Rio de Janeiro', RN:'Rio Grande do Norte', RO:'Rondônia', RR:'Roraima',
  RS:'Rio Grande do Sul', SC:'Santa Catarina', SE:'Sergipe', SP:'São Paulo', TO:'Tocantins',
}

export function FreightSection({ tipoFrete, onTipoFrete, ufEntrega, onUfEntrega, somenteCif = false }: {
  tipoFrete: TipoFrete | null
  onTipoFrete: (t: TipoFrete) => void
  ufEntrega: string
  onUfEntrega: (v: string) => void
  /** Esconde a opção FOB. O usuário final cota sempre CIF — deixar a escolha
   *  visível abre espaço para uma proposta sair sem frete embutido. */
  somenteCif?: boolean
}) {
  const preenchido = tipoFrete === 'fob' || (tipoFrete === 'cif' && ufEntrega !== '')
  const badge = tipoFrete === 'fob'
    ? 'FOB — Retirada no CD'
    : tipoFrete === 'cif' && ufEntrega
    ? `CIF — ${ufEntrega}`
    : null

  return (
    <div className={`rounded-2xl border bg-white shadow-card ${preenchido ? 'border-ink/10' : 'border-orange-300'}`}>
      <div className="flex items-center justify-between px-5 py-4">
        <div className="flex items-center gap-2">
          <MapPin size={16} className={preenchido ? 'text-primary' : 'text-orange-500'} />
          <div>
            <p className="font-display text-base font-bold text-ink">
              Localização e Frete
              {!preenchido && <span className="ml-2 text-xs font-normal text-orange-600">obrigatório</span>}
            </p>
            {badge
              ? <p className="text-xs text-ink/50">{badge}</p>
              : <p className="text-xs text-orange-500">Selecione o tipo de frete para continuar</p>
            }
          </div>
        </div>
      </div>

      <div className="space-y-4 border-t border-ink/10 px-5 py-4">
        {/* Tipo de frete */}
        <div>
          <p className="mb-2 text-xs font-semibold text-ink/60">Tipo de Frete</p>
          <div className={`grid gap-2 ${somenteCif ? 'grid-cols-1' : 'grid-cols-2'}`}>
            {([
              { v: 'cif' as TipoFrete, label: 'CIF (Frete Incluso)', desc: 'Entregue no endereço do cliente' },
              ...(somenteCif ? [] : [
                { v: 'fob' as TipoFrete, label: 'FOB (Retirada no CD)', desc: 'Cliente retira no armazém — taxa WEG→CD' },
              ]),
            ]).map(o => (
              <button
                key={o.v}
                type="button"
                onClick={() => onTipoFrete(o.v)}
                className={`rounded-xl border-2 px-4 py-3 text-left transition-colors ${
                  tipoFrete === o.v
                    ? 'border-primary bg-primary/5 text-primary'
                    : 'border-gray-200 text-gray-600 hover:border-gray-300'
                }`}
              >
                <p className="text-sm font-semibold">{o.label}</p>
                <p className="mt-0.5 text-xs text-ink/50">{o.desc}</p>
              </button>
            ))}
          </div>
        </div>

        {/* CIF: selecionar estado */}
        {tipoFrete === 'cif' && (
          <div>
            <p className="mb-2 text-xs font-semibold text-ink/60">Estado de entrega</p>
            <select
              value={ufEntrega}
              onChange={e => onUfEntrega(e.target.value)}
              className="w-full rounded-xl border border-ink/15 bg-white px-3 py-2 text-sm focus:border-primary focus:outline-none"
            >
              <option value="">Selecionar estado…</option>
              {UFS.map(uf => (
                <option key={uf} value={uf}>{uf} — {UF_NAMES[uf]}</option>
              ))}
            </select>
          </div>
        )}

        {/* FOB: informativo */}
        {tipoFrete === 'fob' && (
          <div className="rounded-xl border border-amber-100 bg-amber-50/60 px-4 py-3 text-sm text-amber-800">
            <p className="font-semibold">Taxa de transporte WEG → CD</p>
            <p className="mt-0.5 text-xs text-amber-700">
              Equivale a 1% do valor do kit. O resultado final mostrará o custo exato após selecionar o kit.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
