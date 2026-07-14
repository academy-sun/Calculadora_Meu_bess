import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '@/lib/supabase'
import { useAuth } from '@/hooks/useAuth'

export function SetPasswordPage() {
  const { session, loading } = useAuth()
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!loading && !session) {
      navigate('/login', { replace: true })
    }
  }, [loading, session, navigate])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (password !== confirm) {
      setError('As senhas não conferem.')
      return
    }
    if (password.length < 8) {
      setError('A senha precisa ter pelo menos 8 caracteres.')
      return
    }
    setSubmitting(true)
    setError(null)
    const { error } = await supabase.auth.updateUser({ password })
    if (error) {
      setError(error.message)
    } else {
      setSuccess(true)
      setTimeout(() => navigate('/', { replace: true }), 1500)
    }
    setSubmitting(false)
  }

  if (loading) return null

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="w-full max-w-md rounded-xl bg-white p-8 shadow">
        <h1 className="mb-1 text-2xl font-bold text-gray-900">Definir senha</h1>
        <p className="mb-6 text-sm text-gray-500">Crie uma senha para acessar a plataforma.</p>

        {success ? (
          <p className="rounded bg-green-50 px-3 py-2 text-sm text-green-700">
            Senha definida com sucesso! Redirecionando...
          </p>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Nova senha</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                minLength={8}
                className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Confirmar senha</label>
              <input
                type="password"
                value={confirm}
                onChange={e => setConfirm(e.target.value)}
                required
                className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
              />
            </div>
            {error && <p className="rounded bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}
            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50"
            >
              {submitting ? 'Salvando...' : 'Definir senha'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
