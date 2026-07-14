import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { supabase } from '@/lib/supabase'
import { useAuth } from '@/hooks/useAuth'

export function LoginPage() {
  const { session } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [resetSent, setResetSent] = useState(false)
  const [resetLoading, setResetLoading] = useState(false)

  if (session) return <Navigate to="/" replace />

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) setError(error.message)
    setLoading(false)
  }

  async function handleForgotPassword() {
    if (!email) {
      setError('Preencha o e-mail acima antes de solicitar a recuperação de senha.')
      return
    }
    setResetLoading(true)
    setError(null)
    await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/set-password`,
    })
    setResetSent(true)
    setResetLoading(false)
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="w-full max-w-md rounded-xl bg-white p-8 shadow">
        <h1 className="mb-1 text-2xl font-bold text-gray-900">MeuBess</h1>
        <p className="mb-6 text-sm text-gray-500">Calculadora de Dimensionamento BESS</p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">E-mail</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Senha</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
            />
          </div>
          {error && <p className="rounded bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}
          {resetSent && (
            <p className="rounded bg-green-50 px-3 py-2 text-sm text-green-700">
              Link enviado! Verifique seu e-mail.
            </p>
          )}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50"
          >
            {loading ? 'Entrando...' : 'Entrar'}
          </button>
          <button
            type="button"
            onClick={handleForgotPassword}
            disabled={resetLoading}
            className="w-full text-center text-xs text-gray-500 hover:text-gray-700 disabled:opacity-50"
          >
            {resetLoading ? 'Enviando...' : 'Esqueceu a senha?'}
          </button>
        </form>
      </div>
    </div>
  )
}
