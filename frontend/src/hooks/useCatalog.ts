import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiPut } from '@/lib/api'
import type { ProductBESS, ProductSolar, StandardLoad } from '@/types'

// ── BESS ─────────────────────────────────────────────────────────────────────

export function useBESSProducts() {
  return useQuery({
    queryKey: ['catalog', 'bess'],
    queryFn: () => apiGet<ProductBESS[]>('/catalog/bess'),
  })
}

export function useCreateBESS() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Omit<ProductBESS, 'id' | 'atualizado_em'>) =>
      apiPost<ProductBESS>('/catalog/bess', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['catalog', 'bess'] }),
  })
}

export function useUpdateBESS() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...data }: Omit<ProductBESS, 'atualizado_em'>) =>
      apiPut<ProductBESS>(`/catalog/bess/${id}`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['catalog', 'bess'] }),
  })
}

// ── Solar ─────────────────────────────────────────────────────────────────────

export function useSolarProducts() {
  return useQuery({
    queryKey: ['catalog', 'solar'],
    queryFn: () => apiGet<ProductSolar[]>('/catalog/solar'),
  })
}

export function useCreateSolar() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Omit<ProductSolar, 'id'>) =>
      apiPost<ProductSolar>('/catalog/solar', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['catalog', 'solar'] }),
  })
}

// ── Standard Loads ────────────────────────────────────────────────────────────

export function useStandardLoads() {
  return useQuery({
    queryKey: ['catalog', 'loads'],
    queryFn: () => apiGet<StandardLoad[]>('/catalog/loads'),
  })
}

export function useCreateLoad() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Omit<StandardLoad, 'id'>) =>
      apiPost<StandardLoad>('/catalog/loads', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['catalog', 'loads'] }),
  })
}

export function useUpdateLoad() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...data }: StandardLoad) =>
      apiPut<StandardLoad>(`/catalog/loads/${id}`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['catalog', 'loads'] }),
  })
}
