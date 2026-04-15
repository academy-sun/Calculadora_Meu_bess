import { Link } from 'react-router-dom'
import { useProjects } from '@/hooks/useProjects'
import { useAuth } from '@/hooks/useAuth'
import { PlusCircle, FolderOpen, Battery } from 'lucide-react'

export function DashboardPage() {
  const { user, isAdmin } = useAuth()
  const { data: projects } = useProjects()
  const recentes = projects?.slice(0, 5) ?? []

  const displayName =
    (user?.user_metadata?.nome as string | undefined) ??
    user?.email?.split('@')[0] ??
    'Usuário'

  return (
    <div className="p-6">
      <h1 className="mb-1 text-2xl font-bold text-gray-900">Olá, {displayName} 👋</h1>
      <p className="mb-6 text-gray-500">O que vamos dimensionar hoje?</p>

      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Link
          to="/projects/new"
          className="flex items-center gap-3 rounded-xl border-2 border-dashed border-primary/40 bg-primary/5 p-4 hover:border-primary"
        >
          <PlusCircle className="text-primary" size={24} />
          <div>
            <p className="font-semibold text-gray-900">Novo Cálculo</p>
            <p className="text-xs text-gray-500">Backup, peak shaving, solar...</p>
          </div>
        </Link>
        <Link
          to="/projects"
          className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white p-4 hover:border-primary"
        >
          <FolderOpen className="text-gray-400" size={24} />
          <div>
            <p className="font-semibold text-gray-900">{projects?.length ?? 0} Projetos</p>
            <p className="text-xs text-gray-500">Ver histórico completo</p>
          </div>
        </Link>
        {isAdmin && (
          <Link
            to="/catalog/bess"
            className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white p-4 hover:border-primary"
          >
            <Battery className="text-gray-400" size={24} />
            <div>
              <p className="font-semibold text-gray-900">Catálogos</p>
              <p className="text-xs text-gray-500">Gerir produtos BESS e Solar</p>
            </div>
          </Link>
        )}
      </div>

      {recentes.length > 0 && (
        <div>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
            Últimos projetos
          </h2>
          <div className="space-y-2">
            {recentes.map(p => (
              <Link
                key={p.id}
                to={`/projects/${p.id}`}
                className="flex items-center justify-between rounded-lg border border-gray-200 bg-white px-4 py-3 hover:border-primary"
              >
                <div>
                  <span className="font-medium text-gray-900 capitalize">
                    {p.tipo_calculo.replace(/_/g, ' ')}
                  </span>
                  <span className="ml-2 text-xs text-gray-400">— {p.solicitante_nome}</span>
                </div>
                <span className="text-xs text-gray-400">
                  {new Date(p.solicitado_em).toLocaleDateString('pt-BR')}
                </span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
