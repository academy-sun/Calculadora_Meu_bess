import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from '@/lib/api'
import type {
  MeuBESSProduct, ProductBESS, ProductFilters, ProductSolar, ProductUpdate, StandardLoad,
} from '@/types'

// ── Réplica MeuBESS (tabela única meubess_products) ──────────────────────────

function buildQuery(filters: ProductFilters): string {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') params.set(k, String(v))
  })
  const qs = params.toString()
  return qs ? `?${qs}` : ''
}

export function useProducts(filters: ProductFilters = {}) {
  return useQuery({
    queryKey: ['catalog', 'products', filters],
    queryFn: () => apiGet<MeuBESSProduct[]>(`/catalog/products${buildQuery(filters)}`),
  })
}

export function useUpdateProduct() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ meubess_id, ...data }: ProductUpdate & { meubess_id: string }) =>
      apiPatch<MeuBESSProduct>(`/catalog/products/${meubess_id}`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['catalog', 'products'] }),
  })
}

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

export function useDeleteBESS() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiDelete(`/catalog/bess/${id}`),
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

export function useUpdateSolar() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...data }: ProductSolar) =>
      apiPut<ProductSolar>(`/catalog/solar/${id}`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['catalog', 'solar'] }),
  })
}

export function useDeleteSolar() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiDelete(`/catalog/solar/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['catalog', 'solar'] }),
  })
}

// ── Sync from supplier platform ──────────────────────────────────────────────

export interface SyncedProduct {
  id: string
  tipo_auto: string
  confianca?: string
  needs_review?: boolean
  marca?: string
  title?: string
}

export interface SyncError {
  id: string
  error: string
}

export interface SyncResult {
  synced: SyncedProduct[]
  errors: SyncError[]
  total_synced: number
  total_errors: number
  por_tipo?: Record<string, number>
  needs_review_count?: number
}

export function useSyncCatalog() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiPost<SyncResult>('/catalog/sync', {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['catalog', 'products'] })
    },
  })
}

// ── Standard Loads ────────────────────────────────────────────────────────────

export function useStandardLoads(useApiKey = false) {
  return useQuery({
    queryKey: ['catalog', 'loads'],
    queryFn: () => apiGet<StandardLoad[]>('/catalog/loads', useApiKey),
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

export function useDeleteLoad() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiDelete(`/catalog/loads/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['catalog', 'loads'] }),
  })
}
