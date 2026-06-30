import { useParams, Link, useNavigate } from 'react-router-dom'
import { useProject } from '@/hooks/useProjects'
import { ArrowLeft, Pencil } from 'lucide-react'
import { KitResult } from '@/components/KitResult'
import type { KitInfo, KitItem, SolarDimensionamento } from '@/types'

export function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
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

  const pm = project.parametros as Record<string, unknown> | undefined
  const titulo = (pm?.titulo as string | undefined) ?? 'Cotação sem título'
  const kitSelecionado = pm?.kit_selecionado as KitInfo | undefined
  const energiaNecessariaKwh = pm?.energia_necessaria_kwh as number | undefined
  const solar = pm?.solar_dimensionamento as SolarDimensionamento | null | undefined
  const economiaMensal = pm?.economia_mensal_rs as number | undefined
  const economiaAnual = pm?.economia_anual_rs as number | undefined

  // itens estáticos — visualização de cotação salva, edição acontece via "Editar cotação"
  const itens: KitItem[] = kitSelecionado?.itens ?? []

  return (
    <div className="p-6 max-w-5xl">
      <div className="mb-4 flex items-center justify-between">
        <Link to="/projects" className="flex items-center gap-1 text-sm text-gray-500 hover:text-primary">
          <ArrowLeft size={14} /> Voltar
        </Link>
        <button onClick={() => navigate(`/?editId=${project.id}`)}
          className="flex items-center gap-1.5 rounded-lg border-2 border-primary px-3 py-1.5 text-sm font-medium text-primary hover:bg-primary/5">
          <Pencil size={14} /> Editar cotação
        </button>
      </div>

      <h1 className="mb-1 font-display text-2xl font-bold">{titulo}</h1>
      <p className="mb-6 text-sm text-gray-500">
        Solicitado por <span className="font-medium">{project.solicitante_nome}</span> em{' '}
        {new Date(project.solicitado_em).toLocaleString('pt-BR')}
        {project.origem === 'ploomes' && project.negocio_nome && (
          <> · Negócio: <span className="font-medium">{project.negocio_nome}</span></>
        )}
      </p>

      {(economiaMensal || economiaAnual) && (
        <div className="mb-4 rounded-lg bg-green-50 px-4 py-3 text-sm text-green-800">
          {economiaMensal && <>Economia mensal: <strong>R$ {economiaMensal.toLocaleString('pt-BR')}</strong></>}
          {economiaAnual && <> · Anual: <strong>R$ {economiaAnual.toLocaleString('pt-BR')}</strong></>}
        </div>
      )}

      {kitSelecionado ? (
        <KitResult
          kit={kitSelecionado}
          itens={itens}
          onItensChange={() => {}}
          titulo="Kit escolhido"
          energiaNecessariaKwh={energiaNecessariaKwh}
          solar={solar}
          editable={false}
        />
      ) : (
        <div className="mt-6 rounded-2xl border border-dashed border-gray-200 bg-white/60 px-6 py-12 text-center text-gray-400">
          Esta cotação não tem um kit associado.
        </div>
      )}
    </div>
  )
}
