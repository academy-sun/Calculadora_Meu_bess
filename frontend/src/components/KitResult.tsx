import { AlertTriangle } from 'lucide-react'
import type { CalculateResponse } from '@/types'

const brl = (v: number) => v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })

export function KitResult({ result }: { result: CalculateResponse }) {
  const kit = result.kit_selecionado
  const solar = result.solar_dimensionamento

  return (
    <div className="mt-8 border-t border-gray-200 pt-6">
      <h2 className="mb-4 text-lg font-bold text-gray-900">Kit encontrado</h2>

      {/* Cards de resumo */}
      <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <SummaryCard label="Capacidade" value={`${result.capacidade_kwh ?? '—'} kWh`} />
        <SummaryCard label="Potência de pico" value={`${kit?.pico_entregavel_kw ?? result.potencia_kw ?? '—'} kVA`} />
        <SummaryCard label="Investimento" value={kit ? brl(kit.preco_total) : '—'} highlight />
        <SummaryCard label="Payback" value={result.payback_meses ? `${result.payback_meses} meses` : '—'} />
      </div>

      {/* Tabela de itens do kit */}
      {kit?.itens && kit.itens.length > 0 ? (
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs font-semibold uppercase text-gray-500">
              <tr>
                <th className="px-4 py-3 text-left">Item</th>
                <th className="px-4 py-3 text-left">Tipo</th>
                <th className="px-4 py-3 text-right">Qtd</th>
                <th className="px-4 py-3 text-right">Preço unit.</th>
                <th className="px-4 py-3 text-right">Total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {kit.itens.map((it, i) => (
                <tr key={i}>
                  <td className="px-4 py-2.5 font-medium text-gray-800">{it.nome}</td>
                  <td className="px-4 py-2.5 capitalize text-gray-500">{it.tipo}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{it.qtd}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{it.preco_unitario ? brl(it.preco_unitario) : '—'}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{it.preco_total ? brl(it.preco_total) : '—'}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-gray-300 bg-gray-50 font-semibold">
                <td className="px-4 py-3" colSpan={4}>Total do kit</td>
                <td className="px-4 py-3 text-right tabular-nums text-green-700">{brl(kit.preco_total)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-gray-200 px-4 py-8 text-center text-sm text-gray-400">
          Nenhum kit compatível encontrado para os parâmetros informados.
        </div>
      )}

      {/* Detalhes técnicos do dimensionamento */}
      {kit && (
        <div className="mt-4 grid grid-cols-2 gap-x-6 gap-y-1.5 rounded-xl bg-gray-50 p-4 text-sm sm:grid-cols-3">
          <Detail label="Baterias" value={`${kit.qtd_baterias}×`} />
          <Detail label="Inversores" value={`${kit.qtd_inversores ?? 1}×`} />
          <Detail label="Distribuição por entrada" value={kit.distribuicao_baterias?.join(' + ') ?? '—'} />
          <Detail label="Caixas de junção" value={`${kit.n_caixas_juncao ?? 0}×`} />
          <Detail label="Capacidade útil" value={`${kit.capacidade_total_kwh} kWh`} />
          <Detail label="Pico entregável" value={`${kit.pico_entregavel_kw ?? '—'} kVA`} />
        </div>
      )}

      {/* Geração solar (se houver) */}
      {solar && (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-amber-800">☀️ Sistema fotovoltaico</p>
          <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 sm:grid-cols-3">
            <Detail label="Módulo" value={`${solar.modulo_marca} ${solar.modulo_modelo} (${solar.modulo_wp} Wp)`} />
            <Detail label="Configuração" value={`${solar.n_serie}S × ${solar.n_paralelo}P × ${solar.mppt_qty} MPPT`} />
            <Detail label="Módulos" value={`${solar.qty_modulos} un.`} />
            <Detail label="Potência instalada" value={`${solar.kwp_instalado} kWp`} />
            <Detail label="Cobertura" value={`${solar.cobertura_pct}% do consumo`} />
            <Detail label="Custo módulos" value={brl(solar.preco_modulos_total)} />
          </div>
        </div>
      )}

      {/* Alertas */}
      {kit?.alertas && kit.alertas.length > 0 && (
        <div className="mt-4 space-y-2">
          {kit.alertas.map((a, i) => (
            <div key={i} className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              <AlertTriangle size={16} className="mt-0.5 flex-shrink-0" /> <span>{a}</span>
            </div>
          ))}
        </div>
      )}

      {/* Arbitragem */}
      {result.qty_bess != null && (
        <div className="mt-4 grid grid-cols-2 gap-x-6 gap-y-1.5 rounded-xl bg-gray-50 p-4 text-sm sm:grid-cols-4">
          <Detail label="Qtd BESS" value={String(result.qty_bess)} />
          <Detail label="Média consumo ponta" value={`${result.avg_consumo_ponta?.toFixed(1)} kWh/mês`} />
          <Detail label="Maior demanda ponta" value={`${result.max_demanda_ponta?.toFixed(1)} kW`} />
          <Detail label="Economia" value={result.economia_mensal_rs ? `${brl(result.economia_mensal_rs)}/mês` : '—'} />
        </div>
      )}
    </div>
  )
}

function SummaryCard({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <p className="text-xs uppercase tracking-wide text-gray-400">{label}</p>
      <p className={`mt-1 text-xl font-bold ${highlight ? 'text-green-700' : 'text-gray-900'}`}>{value}</p>
    </div>
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-gray-500">{label}</p>
      <p className="font-medium text-gray-800">{value}</p>
    </div>
  )
}
