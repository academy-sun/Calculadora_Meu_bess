import { supabase } from './supabase'

const API_URL = (import.meta.env.VITE_API_URL as string) || '/api'

/**
 * Chave de API em uso. Começa VAZIA, de propósito.
 *
 * Só os embeds do Ploomes têm chave, e ela chega em tempo de execução, do
 * script do campo (ver definirApiKey / PloomesEmbedPage). A calculadora
 * interna não usa nenhuma: ela exige login e o JWT do Supabase já vai em
 * toda requisição, logo abaixo em getAuthHeaders.
 *
 * Antes o valor inicial vinha de VITE_API_KEY_PLOOMES. Variável VITE_* é
 * compilada DENTRO do JavaScript, e o bundle é servido a qualquer um — era
 * uma credencial de perfil completo publicada junto com o site. Pior: o
 * valor configurado era a própria User-Key do Ploomes, que dá acesso à API
 * do CRM. Nenhuma chave no build significa nada para vazar por aqui.
 */
let apiKeyAtual = ''

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

/**
 * Mensagem legível do erro da API.
 *
 * O FastAPI devolve `detail` como STRING nos erros que a gente levanta, mas
 * como LISTA de {loc, msg} quando é o Pydantic recusando o corpo. Jogar a
 * lista dentro de new Error() virava "[object Object]" na tela — foi
 * exatamente o que escondeu um 422 de campo inválido no embed de um cliente,
 * e custou um ciclo inteiro de teste para descobrir o que já vinha escrito
 * na resposta.
 */
function mensagemDeErro(err: unknown, padrao: string): string {
  const detail = (err as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail)) {
    const partes = detail.map(d => {
      const campo = Array.isArray(d?.loc) ? d.loc.filter((x: unknown) => x !== 'body').join('.') : ''
      const msg = d?.msg ?? JSON.stringify(d)
      return campo ? `${campo}: ${msg}` : String(msg)
    })
    if (partes.length) return partes.join(' · ')
  }
  return padrao
}

export async function apiGet<T>(path: string, useApiKey = false): Promise<T> {
  const headers = await getAuthHeaders()
  if (useApiKey) headers['X-API-Key'] = apiKeyAtual
  const res = await fetch(`${API_URL}${path}`, { headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as { detail?: unknown }
    throw new Error(mensagemDeErro(err, `GET ${path} falhou: ${res.status}`))
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
    const err = await res.json().catch(() => ({})) as { detail?: unknown }
    throw new Error(mensagemDeErro(err, `POST ${path} falhou: ${res.status}`))
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
    const err = await res.json().catch(() => ({})) as { detail?: unknown }
    throw new Error(mensagemDeErro(err, `PATCH ${path} falhou: ${res.status}`))
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
    const err = await res.json().catch(() => ({})) as { detail?: unknown }
    throw new Error(mensagemDeErro(err, `DELETE ${path} falhou: ${res.status}`))
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
    throw new Error(mensagemDeErro(err, `Erro ${res.status}`))
  }
  return res.json() as Promise<T>
}
