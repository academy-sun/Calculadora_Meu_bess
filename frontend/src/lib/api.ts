import { supabase } from './supabase'

const API_URL = (import.meta.env.VITE_API_URL as string) || '/api'

/**
 * Chave de API em uso.
 *
 * Vem do build (VITE_API_KEY_PLOOMES) para a calculadora interna, mas o embed
 * do Ploomes a SUBSTITUI em tempo de execução com a chave que o script do
 * campo enviar (ver definirApiKey / PloomesEmbedPage).
 *
 * O motivo é que o bundle é público: se as chaves de admin e de usuário final
 * estivessem as duas no build, bastaria ler o JavaScript para pegar a de
 * admin e obter o payload completo. Vindo do campo, cada uma existe só onde o
 * Ploomes permite — e é o Ploomes que esconde o campo de admin dos demais.
 */
let apiKeyAtual = (import.meta.env.VITE_API_KEY_PLOOMES as string) || ''

export function definirApiKey(chave: string): void {
  if (chave) apiKeyAtual = chave
}

async function getAuthHeaders(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return headers
}

export async function apiGet<T>(path: string, useApiKey = false): Promise<T> {
  const headers = await getAuthHeaders()
  if (useApiKey) headers['X-API-Key'] = apiKeyAtual
  const res = await fetch(`${API_URL}${path}`, { headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as { detail?: string }
    throw new Error(err.detail ?? `GET ${path} falhou: ${res.status}`)
  }
  return res.json() as Promise<T>
}

export async function apiPost<T>(path: string, body: unknown, useApiKey = false): Promise<T> {
  const headers = await getAuthHeaders()
  if (useApiKey) headers['X-API-Key'] = apiKeyAtual
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as { detail?: string }
    throw new Error(err.detail ?? `POST ${path} falhou: ${res.status}`)
  }
  return res.json() as Promise<T>
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const headers = await getAuthHeaders()
  const res = await fetch(`${API_URL}${path}`, {
    method: 'PUT',
    headers,
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`PUT ${path} falhou: ${res.status}`)
  return res.json() as Promise<T>
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const headers = await getAuthHeaders()
  const res = await fetch(`${API_URL}${path}`, {
    method: 'PATCH',
    headers,
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as { detail?: string }
    throw new Error(err.detail ?? `PATCH ${path} falhou: ${res.status}`)
  }
  return res.json() as Promise<T>
}

export async function apiDelete(path: string): Promise<void> {
  const headers = await getAuthHeaders()
  const res = await fetch(`${API_URL}${path}`, {
    method: 'DELETE',
    headers,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as { detail?: string }
    throw new Error(err.detail ?? `DELETE ${path} falhou: ${res.status}`)
  }
}

export async function apiBulkDelete<T>(path: string, body: unknown): Promise<T> {
  const headers = await getAuthHeaders()
  const res = await fetch(`${API_URL}${path}`, {
    method: 'DELETE',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: string }).detail ?? `Erro ${res.status}`)
  }
  return res.json() as Promise<T>
}
