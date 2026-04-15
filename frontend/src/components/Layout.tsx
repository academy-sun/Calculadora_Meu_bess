import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import {
  LayoutDashboard,
  FolderOpen,
  PlusCircle,
  Battery,
  Sun,
  Zap,
  LogOut,
} from 'lucide-react'

interface NavItemProps {
  to: string
  icon: React.ElementType
  label: string
}

function NavItem({ to, icon: Icon, label }: NavItemProps) {
  return (
    <NavLink
      to={to}
      end={to === '/'}
      className={({ isActive }) =>
        `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
          isActive
            ? 'bg-white/10 text-white'
            : 'text-slate-300 hover:bg-white/5 hover:text-white'
        }`
      }
    >
      <Icon size={16} />
      {label}
    </NavLink>
  )
}

export function Layout() {
  const { user, isAdmin, signOut } = useAuth()
  const navigate = useNavigate()

  async function handleSignOut() {
    await signOut()
    navigate('/login')
  }

  const displayName =
    (user?.user_metadata?.nome as string | undefined) ??
    user?.email?.split('@')[0] ??
    'Usuário'

  return (
    <div className="flex h-screen bg-gray-100">
      {/* Sidebar */}
      <aside className="flex w-56 flex-shrink-0 flex-col bg-sidebar px-3 py-4">
        <div className="mb-6 px-3">
          <h1 className="text-lg font-bold text-white">MeuBess</h1>
          <p className="text-xs text-slate-400">Dimensionamento BESS</p>
        </div>

        <nav className="flex flex-1 flex-col gap-1">
          <NavItem to="/" icon={LayoutDashboard} label="Dashboard" />
          <NavItem to="/projects" icon={FolderOpen} label="Projetos" />
          <NavItem to="/projects/new" icon={PlusCircle} label="Novo Cálculo" />

          {isAdmin && (
            <>
              <div className="my-2 border-t border-white/10" />
              <p className="px-3 py-1 text-xs font-semibold uppercase tracking-wider text-slate-500">
                Catálogos
              </p>
              <NavItem to="/catalog/bess" icon={Battery} label="BESS" />
              <NavItem to="/catalog/solar" icon={Sun} label="Solar" />
              <NavItem to="/catalog/loads" icon={Zap} label="Cargas Padrão" />
            </>
          )}
        </nav>

        <div className="border-t border-white/10 pt-3">
          <div className="px-3 py-2">
            <p className="truncate text-xs text-white">{displayName}</p>
            <p className="text-xs text-slate-400">{isAdmin ? 'Admin' : 'Engenheiro'}</p>
          </div>
          <button
            onClick={handleSignOut}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-300 hover:bg-white/5 hover:text-white"
          >
            <LogOut size={14} />
            Sair
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
