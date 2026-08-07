import { useState } from 'react'
import { AlertTriangle, ChevronDown, HelpCircle, Info } from 'lucide-react'

import type { Diagnostico } from '@/types'

/**
 * "Por que este kit" — avisos e produtos descartados, com o motivo.
 *
 * O motor sempre soube disso; a informação era descartada antes de sair do
 * backend. Os erros de dimensionamento encontrados em campo eram todos
 * silenciosos: o consultor não tinha como desconfiar antes de apresentar.
 */
export function DiagnosticoKit({ diagnostico }: { diagnostico?: Diagnostico | null }) {
  const [aberto, setAberto] = useState(false)
  if (!diagnostico) return null

  const { avisos = [], descartados = [] } = diagnostico
  const porFaltaDeDado = descartados.filter(d => d.tipo === 'dado_ausente')
  if (avisos.length === 0 && descartados.length === 0) return null

  // Aviso é o que exige atenção agora; a lista de descartados é consulta.
  const grave = avisos.length > 0 || porFaltaDeDado.length > 0

  return (
    <div className={`rounded-2xl border px-4 py-3 ${
      grave ? 'border-accent/40 bg-accent/[0.06]' : 'border-ink/10 bg-white'
    }`}>
      {avisos.length > 0 && (
        <ul className="mb-2 space-y-1.5">
          {avisos.map((a, i) => (
            <li key={i} className="flex gap-2 text-sm text-ink/80">
              <AlertTriangle size={15} className="mt-0.5 shrink-0 text-accent-dark" />
              <span>{a}</span>
            </li>
          ))}
        </ul>
      )}

      <button
        type="button"
        onClick={() => setAberto(v => !v)}
        className="flex w-full items-center gap-1.5 text-left text-xs font-semibold text-ink/60 hover:text-ink"
      >
        <HelpCircle size={14} />
        Por que este kit — {descartados.length} produto(s) avaliado(s) e não usado(s)
        <ChevronDown size={14} className={`ml-auto transition ${aberto ? 'rotate-180' : ''}`} />
      </button>

      {aberto && (
        descartados.length === 0 ? (
          <p className="mt-2 text-xs text-ink/50">
            Nenhum produto foi descartado nesta busca.
          </p>
        ) : (
          <div className="mt-2 overflow-hidden rounded-lg border border-ink/10">
            <table className="w-full text-xs">
              <thead className="bg-ink/[0.03] text-left text-ink/50">
                <tr>
                  <th className="px-3 py-1.5 font-medium">Produto</th>
                  <th className="px-3 py-1.5 font-medium">Motivo</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink/[0.06]">
                {descartados.map((d, i) => (
                  <tr key={i}>
                    <td className="px-3 py-1.5 text-ink/80">{d.titulo}</td>
                    <td className="px-3 py-1.5">
                      <span className={d.tipo === 'dado_ausente' ? 'text-accent-dark' : 'text-ink/60'}>
                        {d.motivo}
                      </span>
                      {d.tipo === 'dado_ausente' && (
                        <span
                          className="ml-2 whitespace-nowrap rounded bg-accent/15 px-1.5 py-0.5 text-[10px] font-medium text-accent-dark"
                          title="Não é incompatibilidade — faltou dado no cadastro do produto"
                        >
                          cadastro incompleto
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}

      {porFaltaDeDado.length > 0 && aberto && (
        <p className="mt-2 flex gap-1.5 text-[11px] text-ink/50">
          <Info size={12} className="mt-0.5 shrink-0" />
          Itens marcados como cadastro incompleto podem ser opções válidas — o
          motor não teve dado para avaliá-los.
        </p>
      )}
    </div>
  )
}
