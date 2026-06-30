import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiBulkDelete } from '@/lib/api'
import type { Project, CalculateResponse, SaveQuoteRequest } from '@/types'

export function useProjects(params?: { origem?: string; negocio_id?: string }) {
  const query = new URLSearchParams()
  if (params?.origem) query.set('origem', params.origem)
  if (params?.negocio_id) query.set('negocio_id', params.negocio_id)
  const qs = query.toString() ? `?${query.toString()}` : ''

  return useQuery({
    queryKey: ['projects', params],
    queryFn: () => apiGet<Project[]>(`/projects${qs}`),
  })
}

export function useProject(id: string) {
  return useQuery({
    queryKey: ['projects', id],
    queryFn: () => apiGet<Project>(`/projects/${id}`),
    enabled: !!id,
  })
}

export function useCalculate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: unknown) =>
      apiPost<CalculateResponse>('/calculate', payload, true),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}

export function useSaveQuote() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: SaveQuoteRequest) => apiPost<Project>('/projects', payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}

interface BulkDeleteResponse {
  deleted: string[]
  forbidden: string[]
}

export function useDeleteProjects() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (ids: string[]) =>
      apiBulkDelete<BulkDeleteResponse>('/projects', { ids }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}
