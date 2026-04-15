import { useParams, Link } from 'react-router-dom'
import { useProject } from '@/hooks/useProjects'
import { ArrowLeft } from 'lucide-react'
import type { KitInfo } from '@/types'

export function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: project, isLoading, isError, error } = useProject(id!)
  const errorMessage = error instanceof Error ? error.message : 'Erro ao carregar projeto'

  if (isLoading) return <div className="p-6 text-gray-500 font-medium animate-pulse">Carregando detalhes...</div>
  
  if (isError) {
    return (
      <div className="p-6">
        <Link to="/projects" className="mb-4 flex items-center gap-1 text-sm text-gray-500 hover:text-primary">
          <ArrowLeft size={14} /> Voltar
        </Link>
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-red-800">
          <h2 className="mb-2 text-lg font-bold">Erro ao carregar projeto</h2>
          <p className="text-sm opacity-90">{errorMessage}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <button 
              onClick={() => window.location.reload()} 
              className="rounded-lg bg-red-600 px-4 py-2 text-xs font-bold text-white transition-colors hover:bg-red-700"
            >
              Tentar Novamente
            </button>
            <Link 
              to="/projects" 
              className="rounded-lg border border-red-300 bg-white px-4 py-2 text-xs font-bold text-red-600 transition-colors hover:bg-red-50"
            >
              Ver Lista de Projetos
            </Link>
          </div>
        </div>
      </div>
    )
  }

  if (!project) return (
    <div className="p-6 text-center">
      <Link to="/projects" className="mb-4 inline-flex items-center gap-1 text-sm text-gray-500 hover:text-primary">
        <ArrowLeft size={14} /> Voltar
      </Link>
      <div className="mt-8 rounded-lg bg-gray-50 p-12 text-gray-500">
        <p className="text-lg font-medium">Projeto não encontrado.</p>
      </div>
    </div>
  )

  const params = project.parametros as Record<string, unknown> | undefined
  const capacidade = params?.capacidade_kwh as number | undefined
  const potencia = params?.potencia_kw as number | undefined
  const payback = params?.payback_meses as number | undefined
  const kitSelecionado = params?.kit_selecionado as KitInfo | undefined
  const alternativas = (params?.alternativas ?? []) as KitInfo[]
  const economiaMensal = params?.economia_mensal_rs as number | undefined
  const economiaAnual = params?.economia_anual_rs as number | undefined

  return (
    <div className="p-6">
      <Link to="/projects" className="mb-4 flex items-center gap-1 text-sm text-gray-500 hover:text-primary">
        <ArrowLeft size={14} /> Voltar
      </Link>

      <h1 className="mb-1 text-2xl font-bold capitalize">
        {project.tipo_calculo.replace(/_/g, ' ')}
      </h1>
      <p className="mb-6 text-sm text-gray-500">
        Solicitado por <span className="font-medium">{project.solicitante_nome}</span> em{' '}
        {new Date(project.solicitado_em).toLocaleString('pt-BR')}
        {project.origem === 'ploomes' && project.negocio_nome && (
          <> · Negócio: <span className="font-medium">{project.negocio_nome}</span></>
        )}
      </p>

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Capacidade" value={capacidade != null ? `${capacidade} kWh` : '—'} />
        <StatCard label="Potência" value={potencia != null ? `${potencia} kW` : '—'} />
        <StatCard label="Payback" value={payback != null ? `${payback} meses` : '—'} />
      </div>

      {kitSelecionado && (
        <div className="mb-4 rounded-xl border-2 border-primary/30 bg-primary/5 p-4">
          <p className="mb-3 text-xs font-bold uppercase text-primary">Kit Recomendado — Menor Preço</p>
          <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div><p className="text-xs text-gray-500">Marca</p><p className="font-semibold">{kitSelecionado.marca}</p></div>
            <div><p className="text-xs text-gray-500">Bateria</p><p className="font-semibold">{kitSelecionado.bateria_modelo}</p></div>
            <div><p className="text-xs text-gray-500">Inversor</p><p className="font-semibold">{kitSelecionado.inversor_modelo}</p></div>
            <div>
              <p className="text-xs text-gray-500">Preço Total</p>
              <p className="font-bold text-green-700">R$ {kitSelecionado.preco_total.toLocaleString('pt-BR')}</p>
            </div>
          </div>
          <p className="mt-2 text-xs text-gray-500">
            {kitSelecionado.qtd_baterias}× baterias · {kitSelecionado.capacidade_total_kwh} kWh úteis · {kitSelecionado.potencia_total_kw} kW
          </p>
        </div>
      )}

      {alternativas.length > 0 && (
        <div className="mb-4">
          <p className="mb-2 text-xs font-semibold uppercase text-gray-400">Alternativas</p>
          <div className="space-y-2">
            {alternativas.map((k, i) => (
              <div key={i} className="flex items-center justify-between rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm">
                <span>{k.marca} — {k.bateria_modelo} + {k.inversor_modelo}</span>
                <span className="font-medium">R$ {k.preco_total.toLocaleString('pt-BR')}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {(economiaMensal || economiaAnual) && (
        <div className="mb-4 rounded-lg bg-green-50 px-4 py-3 text-sm text-green-800">
          {economiaMensal && <>Economia mensal: <strong>R$ {economiaMensal.toLocaleString('pt-BR')}</strong></>}
          {economiaAnual && <> · Anual: <strong>R$ {economiaAnual.toLocaleString('pt-BR')}</strong></>}
        </div>
      )}

      <div className="rounded-xl border border-gray-200 bg-white p-4">
        <p className="mb-2 text-xs font-semibold uppercase text-gray-400">Parâmetros da Requisição</p>
        <pre className="overflow-auto text-xs text-gray-600">{JSON.stringify(project.parametros, null, 2)}</pre>
      </div>
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <p className="text-xs uppercase text-gray-400">{label}</p>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
    </div>
  )
}
