import { Link } from 'react-router-dom'
import { useProjects } from '@/hooks/useProjects'
import { PlusCircle } from 'lucide-react'

const TIPO_LABEL: Record<string, string> = {
  backup: 'Backup',
  peak_shaving: 'Peak Shaving',
  arbitragem: 'Arbitragem',
  solar: 'Solar',
  solar_storage: 'Solar + Storage',
}

const ESTADO_COLOR: Record<string, string> = {
  concluido: 'bg-green-100 text-green-700',
  calculando: 'bg-yellow-100 text-yellow-700',
  erro: 'bg-red-100 text-red-700',
}

export function ProjectsPage() {
  const { data: projects, isLoading, error } = useProjects()

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Projetos</h1>
        <Link
          to="/projects/new"
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-dark"
        >
          <PlusCircle size={16} /> Novo Cálculo
        </Link>
      </div>

      {isLoading && <p className="text-gray-500">Carregando...</p>}
      {error && <p className="text-red-600">Erro ao carregar projetos.</p>}

      {projects && (
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs font-semibold uppercase text-gray-500">
              <tr>
                <th className="px-4 py-3 text-left">Tipo</th>
                <th className="px-4 py-3 text-left">Solicitante</th>
                <th className="px-4 py-3 text-left">Origem</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">Data</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {projects.map(p => (
                <tr key={p.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium">
                    {TIPO_LABEL[p.tipo_calculo] ?? p.tipo_calculo}
                  </td>
                  <td className="px-4 py-3 text-gray-600">{p.solicitante_nome}</td>
                  <td className="px-4 py-3">
                    <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs capitalize">
                      {p.origem}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${ESTADO_COLOR[p.estado] ?? ''}`}>
                      {p.estado}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {new Date(p.solicitado_em).toLocaleDateString('pt-BR')}
                  </td>
                  <td className="px-4 py-3">
                    <Link to={`/projects/${p.id}`} className="text-primary hover:underline">
                      Ver
                    </Link>
                  </td>
                </tr>
              ))}
              {projects.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                    Nenhum projeto ainda.{' '}
                    <Link to="/projects/new" className="text-primary">Criar o primeiro</Link>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
