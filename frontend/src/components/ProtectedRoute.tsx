import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'

export function ProtectedRoute() {
  const { session, loading } = useAuth()
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-gray-400">
        Carregando...
      </div>
    )
  }
  if (!session) return <Navigate to="/login" replace />
  return <Outlet />
}
