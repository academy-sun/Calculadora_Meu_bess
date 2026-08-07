// Fase de uma CARGA. Bifásico entrou em 06/08/2026; a fase da instalação
// (`tipo_instalacao`) continua sendo só mono/tri.
export type FaseCarga = 'monofasico' | 'bifasico' | 'trifasico'

/** Por que o kit é este — produtos avaliados e deixados de fora, com o motivo. */
export interface ProdutoDescartado {
  produto_id: string
  titulo: string
  motivo: string
  marca?: string
  /** 'dado_ausente' = faltou informação para decidir, não é incompatibilidade. */
  tipo: 'dado_ausente' | 'incompativel'
}

export interface Diagnostico {
  avisos: string[]
  descartados: ProdutoDescartado[]
}

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
  mppt_v_min?: number
  mppt_v_max?: number
  mppt_i_max_a?: number
  mppt_qty?: number
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
  voc_v?: number
  vmp_v?: number
  isc_a?: number
  imp_a?: number
  potencia_nominal_kw?: number
  mppt_min_v?: number
  mppt_max_v?: number
  fase?: 'monofasico' | 'trifasico'
  preco: number
  disponivel: boolean
}

// Réplica fiel do catálogo MeuBESS (tabela única meubess_products)
export type TipoProduto =
  | 'bateria' | 'inversor_hibrido' | 'inversor_string'
  | 'modulo_fv' | 'acessorio' | 'indefinido'

export interface MeuBESSProduct {
  meubess_id: string

  // identidade / comercial
  enterprise_id?: string
  title?: string
  original_title?: string
  description?: string
  sku?: string
  suplier_cod?: string
  marca?: string
  brand_id?: string
  brand_title?: string
  supplier_id?: string
  supplier_title?: string
  app?: string
  active?: boolean
  view?: string
  section?: string
  type?: string
  groups?: string
  availability?: string

  // categoria
  category_id?: string
  category_title?: string
  category_section?: string

  // elétricos / técnicos
  power?: number
  voltage?: string
  phase?: string
  breaker?: string
  battery_inputs?: number
  max_eps_power?: number
  max_output_power?: number
  qty_mppt?: number
  qty_inputs_per_mppt?: number
  voc_max_voltage?: number
  mppt_min_voltage?: number
  output_voltage?: number
  string_current?: number
  short_circuit_current_inverter?: number
  short_circuit_current_module?: number
  max_power_current?: number

  // preço / fiscal / dimensão
  price?: number
  price_sale?: number
  price_sale_until?: string
  ncm?: string
  unt_measure?: string
  unt_multiples?: string
  weight?: number
  width?: number
  height?: number
  length?: number
  volumes?: number
  fixing_type?: string
  fixing_capacity?: number

  // mídia
  images?: unknown

  // dimensionamento (datasheet)
  peak_power_kw?: number
  peak_power_duration_s?: number
  battery_input_max_current_a?: number
  battery_voltage_min_v?: number
  battery_voltage_max_v?: number
  eps_output_voltage?: string
  split_phase?: boolean
  max_parallel_units?: number
  usable_capacity_kwh?: number
  nominal_capacity_kwh?: number
  dod_percent?: number
  max_parallel_batteries?: number
  max_continuous_current_a?: number
  peak_discharge_current_a?: number
  nominal_voltage_v?: number
  operating_voltage_min_v?: number
  operating_voltage_max_v?: number
  chemistry?: string
  compatible_inverters?: string

  // classificação / validação
  tipo_auto?: TipoProduto
  classificacao_confianca?: 'alta' | 'media' | 'baixa'
  needs_review: boolean
  tipo_manual?: TipoProduto
  overrides_tecnicos?: Record<string, unknown>
  validado_por?: string
  validado_em?: string

  // origem / compliance
  origem: string
  first_seen_at: string
  last_synced_at: string
}

export type PerfilUsuario = 'integrador' | 'consultor' | 'admin'

export type TipoFrete = 'cif' | 'fob'

export interface FreteInfo {
  tipo: TipoFrete
  uf: string | null
  valor: number
  percentual: number
  valor_minimo: number
}

export interface ProductFilters {
  tipo?: string
  marca?: string
  app?: string
  needs_review?: boolean
  titulo?: string
  potencia_min?: number
  potencia_max?: number
  active?: boolean
  synced_from?: string
  synced_to?: string
  seen_from?: string
  seen_to?: string
}

export interface ProductUpdate {
  tipo_manual?: TipoProduto
  overrides_tecnicos?: Record<string, unknown>
  validado_por?: string
  marcar_validado?: boolean
  // campos de dimensionamento (colunas dedicadas, enviados diretamente)
  [key: string]: unknown
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
  fase: FaseCarga
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
  tensao?: string
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
  // dimensionamento (motor kit_builder R1–R9)
  distribuicao_baterias?: number[]
  n_caixas_juncao?: number
  pico_entregavel_kw?: number
  alertas?: string[]
  itens?: KitItem[]
  rotulo?: string
  rotulo_caminho?: string
  kwp_instalado?: number
}

export interface KitItem {
  nome: string
  tipo: string
  qtd: number
  preco_unitario: number
  preco_total: number
  // bateria (por unidade)
  energia_unit_kwh?: number
  corrente_pico_a?: number
  tensao_v?: number
  // inversor (por unidade)
  potencia_inversao_kw?: number
  potencia_pico_kw?: number
  corrente_entrada_a?: number
  entradas_bateria?: number
}

export interface SolarDimensionamento {
  modulo_marca: string
  modulo_modelo: string
  modulo_wp: number
  qty_modulos: number
  n_serie: number
  n_paralelo: number
  mppt_qty: number
  kwp_instalado: number
  cobertura_pct: number
  preco_modulos_total: number
}

export interface CalculateResponse {
  projeto_id?: string   // só existe depois que a cotação é salva (POST /projects)
  tipo_calculo: TipoCalculo
  origem: string
  negocio_id?: string
  solicitado_em: string
  calculado_em: string
  capacidade_kwh: number
  potencia_kw: number
  energia_necessaria_kwh?: number

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
  solar_dimensionamento?: SolarDimensionamento | null
  kwp_alvo?: number
  frete?: FreteInfo | null
  diagnostico?: Diagnostico | null
}

// ── Salvar cotação (persistência sob demanda) ──────────────────────────────────

export interface SaveQuoteRequest {
  titulo: string
  calculo: Record<string, unknown>   // o mesmo payload enviado para /calculate
  resultado: CalculateResponse        // resultado com kit_selecionado = kit escolhido (editado)
}
