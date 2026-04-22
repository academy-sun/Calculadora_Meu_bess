// ── Catálogo ──────────────────────────────────────────────────────────────────

export interface ProductBESS {
  id: string
  marca: string
  modelo: string
  sku: string
  tipo: 'bateria' | 'inversor_hibrido' | 'bess_comercial'
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
  pot_ca_max_eps_kva?: number
  max_baterias?: number
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
  tdia_horas?: number
  fator_demanda?: number
  ip_in?: number
  tensao: string
  fase: 'monofasico' | 'trifasico'
  ativo: boolean
}

// ── Projetos ──────────────────────────────────────────────────────────────────

export type TipoCalculo = 'backup' | 'arbitragem'

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

export interface BackupLoadRow {
  nome: string
  qtd: number
  pnom_w: number
  fp: number
  fd: number
  ip_in: number
  tdia_h: number
}

export interface BackupRowResult {
  nome: string
  pn_kva: number
  dmn_kva: number
  pp_kva: number
  dmp_kva: number
  e_eps_kwh: number
}

export interface KitInfo {
  marca: string
  bateria_modelo: string
  inversor_modelo: string
  qtd_baterias: number
  qtd_inversores?: number
  capacidade_total_kwh: number
  potencia_total_kw: number
  preco_total: number
  economia_mensal_rs?: number
  payback_anos?: number
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

  // Backup
  backup_rows?: BackupRowResult[]
  total_pn_kva?: number
  total_dmn_kva?: number
  total_pp_kva?: number
  total_dmp_kva?: number

  // Arbitragem
  qty_bess?: number
  qty_consumo?: number
  qty_potencia?: number
  avg_consumo_ponta?: number
  max_demanda_ponta?: number

  kit_selecionado?: KitInfo
  economia_mensal_rs?: number
  economia_anual_rs?: number
  payback_meses?: number
  alternativas: KitInfo[]
}
