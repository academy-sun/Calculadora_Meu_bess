import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost } from '@/lib/api'
import type { Project, CalculateResponse } from '@/types'

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
