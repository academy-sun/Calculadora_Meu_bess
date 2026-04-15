// ── Catálogo ──────────────────────────────────────────────────────────────────

export interface ProductBESS {
  id: string
  marca: string
  modelo: string
  sku: string
  tipo: 'bateria' | 'inversor_hibrido'
  fase?: 'monofasico' | 'trifasico'
  tensao_nominal_v?: number
  tensao_min_dc_v?: number
  tensao_max_dc_v?: number
  corrente_max_carga_a?: number
  corrente_max_descarga_a?: number
  corrente_max_dc_a?: number
  capacidade_kwh?: number
  dod_percent?: number
  potencia_continua_kw?: number
  preco: number
  disponivel: boolean
  atualizado_em: string
}

export interface ProductSolar {
  id: string
  marca: string
  modelo: string
  sku: string
  tipo: 'modulo_fv' | 'inversor_solar'
  potencia_pico_wp?: number
  eficiencia_pct?: number
  potencia_nominal_kw?: number
  mppt_min_v?: number
  mppt_max_v?: number
  fase?: 'monofasico' | 'trifasico'
  preco: number
  disponivel: boolean
}

export interface StandardLoad {
  id: string
  nome: string
  categoria: string
  potencia_w: number
  fator_potencia: number
  tensao: string
  fase: 'monofasico' | 'trifasico'
  ativo: boolean
}

// ── Projetos ──────────────────────────────────────────────────────────────────

export type TipoCalculo = 'backup' | 'peak_shaving' | 'arbitragem' | 'solar' | 'solar_storage'

export interface Project {
  id: string
  tipo_calculo: TipoCalculo
  estado: 'calculando' | 'concluido' | 'erro'
  versao: number
  origem: 'ploomes' | 'interno'
  negocio_id?: string
  negocio_nome?: string
  solicitante_id: string
  solicitante_nome: string
  solicitado_em: string
  calculado_em?: string
  parametros?: Record<string, unknown>
}

// ── Cálculo ───────────────────────────────────────────────────────────────────

export interface LoadItem {
  nome: string
  potencia_w: number
  quantidade: number
  horas_uso_dia: number
}

export interface KitInfo {
  marca: string
  bateria_modelo: string
  inversor_modelo: string
  qtd_baterias: number
  capacidade_total_kwh: number
  potencia_total_kw: number
  preco_total: number
}

export interface CalculateResponse {
  projeto_id: string
  tipo_calculo: TipoCalculo
  origem: string
  negocio_id?: string
  solicitado_em: string
  calculado_em: string
  capacidade_kwh: number
  potencia_kw: number
  kit_selecionado?: KitInfo
  economia_mensal_rs?: number
  economia_anual_rs?: number
  payback_meses?: number
  alternativas: KitInfo[]
}
