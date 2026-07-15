import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiPatch, apiDelete } from '@/lib/api'
import { UserPlus, Trash2, Shield, User } from 'lucide-react'

interface AuthUser {
  id: string
  email: string
  created_at: string
  last_sign_in_at?: string
  user_metadata?: { nome?: string; role?: string }
  invited_at?: string
  confirmed_at?: string
}

const ROLE_LABELS: Record<string, string> = {
  admin: 'Admin',
  consultor: 'Consultor',
  integrador: 'Integrador',
  engineer: 'Integrador',  // alias legado
}

function formatDate(iso?: string) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

export function UsersAdminPage() {
  const qc = useQueryClient()
  const [showInvite, setShowInvite] = useState(false)
  const [inviteForm, setInviteForm] = useState({ email: '', nome: '', role: 'integrador' })
  const [inviteError, setInviteError] = useState<string | null>(null)
  const [inviteSuccess, setInviteSuccess] = useState(false)

  const { data: users = [], isLoading } = useQuery<AuthUser[]>({
    queryKey: ['admin-users'],
    queryFn: () => apiGet<AuthUser[]>('/admin/users'),
  })

  const inviteMutation = useMutation({
    mutationFn: (body: { email: string; nome: string; role: string; redirect_to: string }) =>
      apiPost('/admin/users/invite', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-users'] })
      setInviteSuccess(true)
      setInviteForm({ email: '', nome: '', role: 'engineer' })
      setTimeout(() => {
        setInviteSuccess(false)
        setShowInvite(false)
      }, 2000)
    },
    onError: (e: Error) => setInviteError(e.message),
  })

  const roleMutation = useMutation({
    mutationFn: ({ id, role }: { id: string; role: string }) =>
      apiPatch(`/admin/users/${id}/role`, { role }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiDelete(`/admin/users/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
  })

  function handleInvite(e: React.FormEvent) {
    e.preventDefault()
    setInviteError(null)
    inviteMutation.mutate({
      ...inviteForm,
      redirect_to: `${window.location.origin}/set-password`,
    })
  }

  function toggleRole(user: AuthUser) {
    const current = user.user_metadata?.role ?? 'integrador'
    const next =
      current === 'admin' ? 'integrador'
      : current === 'consultor' ? 'admin'
      : 'consultor'
    roleMutation.mutate({ id: user.id, role: next })
  }

  function confirmDelete(user: AuthUser) {
    if (confirm(`Remover o usuário ${user.email}? Esta ação não pode ser desfeita.`)) {
      deleteMutation.mutate(user.id)
    }
  }

  return (
    <div className="mx-auto max-w-5xl p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Usuários</h1>
          <p className="text-sm text-gray-500">Gerencie o acesso à plataforma.</p>
        </div>
        <button
          onClick={() => { setShowInvite(true); setInviteError(null); setInviteSuccess(false) }}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-dark"
        >
          <UserPlus size={15} />
          Convidar
        </button>
      </div>

      {/* Invite modal */}
      {showInvite && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h2 className="mb-4 text-lg font-semibold text-gray-900">Convidar usuário</h2>
            {inviteSuccess ? (
              <p className="rounded bg-green-50 px-3 py-2 text-sm text-green-700">
                Convite enviado! O usuário receberá um e-mail.
              </p>
            ) : (
              <form onSubmit={handleInvite} className="space-y-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700">Nome</label>
                  <input
                    type="text"
                    required
                    value={inviteForm.nome}
                    onChange={e => setInviteForm(f => ({ ...f, nome: e.target.value }))}
                    className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">E-mail</label>
                  <input
                    type="email"
                    required
                    value={inviteForm.email}
                    onChange={e => setInviteForm(f => ({ ...f, email: e.target.value }))}
                    className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Perfil</label>
                  <select
                    value={inviteForm.role}
                    onChange={e => setInviteForm(f => ({ ...f, role: e.target.value }))}
                    className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
                  >
                    <option value="integrador">Integrador — vê apenas kit_ftv</option>
                    <option value="consultor">Consultor — vê kit_ftv + only_whs</option>
                    <option value="admin">Admin — acesso completo</option>
                  </select>
                </div>
                {inviteError && (
                  <p className="rounded bg-red-50 px-3 py-2 text-sm text-red-600">{inviteError}</p>
                )}
                <div className="flex justify-end gap-2 pt-1">
                  <button
                    type="button"
                    onClick={() => setShowInvite(false)}
                    className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    disabled={inviteMutation.isPending}
                    className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50"
                  >
                    {inviteMutation.isPending ? 'Enviando...' : 'Enviar convite'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Table */}
      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
        {isLoading ? (
          <p className="py-12 text-center text-sm text-gray-500">Carregando...</p>
        ) : users.length === 0 ? (
          <p className="py-12 text-center text-sm text-gray-500">Nenhum usuário cadastrado.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b border-gray-100 bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Nome / E-mail</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Perfil</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Cadastrado em</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Último acesso</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {users.map(u => {
                const role = u.user_metadata?.role ?? 'engineer'
                const nome = u.user_metadata?.nome
                return (
                  <tr key={u.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      {nome && <p className="font-medium text-gray-900">{nome}</p>}
                      <p className="text-gray-500">{u.email}</p>
                      {!u.confirmed_at && (
                        <span className="mt-0.5 inline-block rounded bg-yellow-50 px-1.5 py-0.5 text-xs text-yellow-700">
                          Convite pendente
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                          role === 'admin'
                            ? 'bg-purple-100 text-purple-700'
                            : 'bg-gray-100 text-gray-600'
                        }`}
                      >
                        {role === 'admin' ? <Shield size={11} /> : <User size={11} />}
                        {ROLE_LABELS[role] ?? role}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500">{formatDate(u.created_at)}</td>
                    <td className="px-4 py-3 text-gray-500">{formatDate(u.last_sign_in_at)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => toggleRole(u)}
                          disabled={roleMutation.isPending}
                          title="Alternar papel (integrador → consultor → admin → integrador)"
                          className="rounded px-2 py-1 text-xs text-gray-600 hover:bg-gray-100 disabled:opacity-40"
                        >
                          {role === 'admin' ? '→ Integrador' : role === 'consultor' ? '→ Admin' : '→ Consultor'}
                        </button>
                        <button
                          onClick={() => confirmDelete(u)}
                          disabled={deleteMutation.isPending}
                          className="rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-40"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
