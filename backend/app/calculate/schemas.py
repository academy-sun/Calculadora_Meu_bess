from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel


class OrigemInfo(BaseModel):
    origem: Literal["ploomes", "interno"]
    negocio_id: Optional[str] = None
    negocio_nome: Optional[str] = None
    solicitante_id: str
    solicitante_nome: str
    solicitado_em: datetime


# ── Backup load row ───────────────────────────────────────────────────────────

class BackupLoadRow(BaseModel):
    """One row from the backup load table (pre-filled from catalog, user-editable)."""
    nome: str
    qtd: int = 1
    pnom_w: float
    fp: float = 1.0
    fd: float = 1.0
    ip_in: float = 1.0
    tdia_h: float = 4.0
    tensao: Optional[str] = None  # "127" | "220" | "380" — usada no R8 (saída EPS)
    # "monofasico" | "bifasico" | "trifasico" — R8 (lado fase). Sem isso, uma
    # carga trifásica 220 V passa por qualquer inversor que atenda 220 V.
    fase: Optional[str] = None


class BackupRowResult(BaseModel):
    nome: str
    pn_kva: float
    dmn_kva: float
    pp_kva: float
    dmp_kva: float
    e_eps_kwh: float


# ── Legacy load item (kept for peak shaving) ─────────────────────────────────

class LoadItem(BaseModel):
    nome: str
    potencia_w: float
    quantidade: int = 1
    horas_uso_dia: float


# ── Request ───────────────────────────────────────────────────────────────────

class CalculateRequest(BaseModel):
    origem_info: OrigemInfo
    tipo_calculo: Literal["backup", "backup_direto", "peak_shaving", "arbitragem", "solar", "solar_storage"]
    # Perfil do usuário — controla quais produtos entram no kit (espelho da alçada MeuBESS)
    # integrador → kit_ftv; consultor → +only_whs; admin → +only_admins (default)
    perfil_usuario: Literal["integrador", "consultor", "admin"] = "admin"

    # Frete: tipo obrigatório no frontend; backend aceita None para não calcular
    # (integração Ploomes envia sem tipo_frete → sem frete)
    tipo_frete: Optional[Literal["cif", "fob"]] = None
    uf_entrega: Optional[str] = None  # obrigatório quando tipo_frete="cif"

    # ── Backup ────────────────────────────────────────────────────────────────
    cargas_backup: Optional[list[BackupLoadRow]] = None
    tipo_instalacao: Optional[Literal["monofasico", "trifasico"]] = None
    padrao_entrada: Optional[Literal["mono_127", "mono_220", "tri_127_220", "tri_220_380"]] = None
    autonomia_horas: Optional[float] = None      # legado
    autonomia_dias: Optional[float] = None        # dias de autonomia (multiplica a energia diária)
    dod_percent: Optional[float] = None

    # ── Sistema fotovoltaico (on-grid + armazenamento) ────────────────────────
    powerpeak_kwp: Optional[float] = None          # kWp pré-dimensionado (ex: vindo do CRM)
    taxa_desempenho: Optional[float] = None        # performance ratio (0.0–1.0); default 0.8
    fixing_type: Optional[str] = None             # tipo de estrutura (ex: "tile_ceramic", "ground_pratyc")
    eficiencia_roundtrip: Optional[float] = None
    tensao_instalacao_v: Optional[float] = None

    # ── Backup Direto (totais pré-calculados pelo Ploomes) ────────────────────
    total_pp_kva:    Optional[float] = None  # Potência de pico total (kVA)
    total_e_eps_kwh: Optional[float] = None  # Energia necessária já escalada (kWh)

    # ── Solar (opcional, dentro do backup) ───────────────────────────────────
    consumo_medio_mensal_kwh: Optional[float] = None
    hsp_media: Optional[float] = None

    # ── Arbitragem ────────────────────────────────────────────────────────────
    consumo_ponta_kwh: Optional[list[float]] = None   # 12 values
    demanda_ponta_kw: Optional[list[float]] = None    # 12 values
    tarifa_ponta_rs_kwh: Optional[float] = None
    tarifa_fora_ponta_rs_kwh: Optional[float] = None

    # ── Peak Shaving ──────────────────────────────────────────────────────────
    curva_carga_kw: Optional[list[float]] = None
    cargas: Optional[list[LoadItem]] = None
    demanda_alvo_kw: Optional[float] = None
    tarifa_demanda_rs_kw: Optional[float] = None

    # ── Solar ─────────────────────────────────────────────────────────────────
    irradiacao_kwh_m2_dia: Optional[float] = None
    area_disponivel_m2: Optional[float] = None


# ── Kit info ──────────────────────────────────────────────────────────────────

class KitItem(BaseModel):
    #: Id do produto na réplica. Sem ele o servidor não consegue
    #: reprecificar um kit editado na tela — e no perfil restrito o preço
    #: não trafega, então recalcular no cliente não é opção.
    #: Vazio em item que não veio do catálogo (placeholder de JBW sem preço).
    meubess_id: str = ""
    nome: str
    tipo: str
    qtd: int
    preco_unitario: float
    preco_total: float
    # bateria (por unidade)
    energia_unit_kwh: Optional[float] = None
    corrente_pico_a: Optional[float] = None
    tensao_v: Optional[float] = None
    # inversor (por unidade)
    potencia_inversao_kw: Optional[float] = None   # potência nominal de saída/EPS
    potencia_pico_kw: Optional[float] = None       # potência de pico (partida)
    corrente_entrada_a: Optional[float] = None     # corrente máx por entrada de bateria
    entradas_bateria: Optional[int] = None


class KitInfo(BaseModel):
    marca: str
    bateria_modelo: str
    inversor_modelo: str
    qtd_baterias: int
    qtd_inversores: int = 1
    capacidade_total_kwh: float
    potencia_total_kw: float
    preco_total: float
    #: Frete DESTE kit e o total com ele. O frete CIF é percentual sobre o
    #: valor do kit, então cada alternativa tem o seu — comparar alternativas
    #: pelo preço sem frete leva à conclusão errada quando a diferença de
    #: preço entre elas é da ordem do frete.
    frete_valor: Optional[float] = None
    total_com_frete: Optional[float] = None
    #: Fração da energia exigida que este kit cobre (1.0 = 100%). A alternativa
    #: "mais econômica" é sub-dimensionada de propósito; sem este número não há
    #: como avisar quem está aplicando o kit na proposta.
    cobertura_energia: Optional[float] = None
    economia_mensal_rs: Optional[float] = None
    payback_anos: Optional[float] = None
    # dimensionamento (motor kit_builder R1–R9)
    distribuicao_baterias: Optional[list[int]] = None
    n_caixas_juncao: Optional[int] = None
    pico_entregavel_kw: Optional[float] = None
    alertas: Optional[list[str]] = None
    itens: Optional[list[KitItem]] = None
    rotulo: Optional[str] = None   # "Kit sugerido" | "Alternativa — outra composição" | "Alternativa — mais econômica"
    rotulo_caminho: Optional[str] = None   # "dc" | "split" | "scaled" (só em kits combinados FV+BESS)
    kwp_instalado: Optional[float] = None  # kWp FV instalado no kit (para card de resultado)


class SolarDimensionamento(BaseModel):
    modulo_marca: str
    modulo_modelo: str
    modulo_wp: float
    qty_modulos: int
    n_serie: int
    n_paralelo: int
    mppt_qty: int
    kwp_instalado: float
    cobertura_pct: float
    preco_modulos_total: float


# ── Response ─────────────────────────────────────────────────────────────────

class ProdutoDescartado(BaseModel):
    """Produto que o motor avaliou e deixou de fora, com o porquê."""
    produto_id: str
    titulo: str
    motivo: str
    marca: str = ""
    # "dado_ausente" = o produto pode até servir, faltou informação para decidir.
    # "incompativel" = foi avaliado e não atende. Misturar os dois esconde
    # buraco de cadastro atrás de aparência de incompatibilidade técnica.
    tipo: Literal["dado_ausente", "incompativel"]


class Diagnostico(BaseModel):
    """Por que o kit é este. Existe para o consultor conferir ANTES de
    apresentar ao cliente — o motor já sabia disso tudo e não contava."""
    #: Avisos que QUALQUER usuário precisa ver: preço possivelmente defasado,
    #: regra que não pôde ser verificada por falta de dado da carga. Falam da
    #: cotação em si, não do catálogo — sobrevivem ao filtro de perfil.
    avisos: list[str] = []
    #: Avisos de higiene interna: quantos produtos estão com cadastro
    #: incompleto e quais. Úteis para nós, ruído (e exposição do catálogo)
    #: para o usuário final. Separados de `avisos` porque o filtro de perfil
    #: precisa distinguir os dois — texto não é critério de filtro confiável.
    avisos_internos: list[str] = []
    descartados: list[ProdutoDescartado] = []


class CalculateResponse(BaseModel):
    projeto_id: Optional[str] = None   # só existe depois que a cotação é salva (POST /projects)
    #: Qual versão desta resposta foi entregue — "completo" ou "restrito".
    #: A tela renderiza pelo que o servidor DIZ ter mandado, não pela ausência
    #: de campos: inferir "não veio preço, então é restrito" quebra silencioso
    #: no dia em que um preço legítimo vier zerado.
    perfil: str = "completo"
    tipo_calculo: str
    origem: str
    negocio_id: Optional[str]
    solicitado_em: datetime
    calculado_em: datetime

    capacidade_kwh: float
    potencia_kw: float
    energia_necessaria_kwh: Optional[float] = None   # E_BAT exigida (cargas × dias)
    kwp_alvo: Optional[float] = None                 # kWp FV calculado/informado (para o card de resultado)

    # Backup-specific
    backup_rows: Optional[list[BackupRowResult]] = None
    total_pn_kva: Optional[float] = None
    total_dmn_kva: Optional[float] = None
    total_pp_kva: Optional[float] = None
    total_dmp_kva: Optional[float] = None

    # Arbitragem-specific
    qty_bess: Optional[int] = None
    qty_consumo: Optional[int] = None
    qty_potencia: Optional[int] = None
    avg_consumo_ponta: Optional[float] = None
    max_demanda_ponta: Optional[float] = None

    kit_selecionado: Optional[KitInfo] = None
    economia_mensal_rs: Optional[float] = None
    economia_anual_rs: Optional[float] = None
    payback_meses: Optional[float] = None
    alternativas: list[KitInfo] = []

    solar_dimensionamento: Optional[SolarDimensionamento] = None

    frete: Optional[dict] = None   # FreteInfo: {uf, valor, percentual, valor_minimo}
    diagnostico: Optional[Diagnostico] = None


# ── Salvar cotação (persistência sob demanda, só quando o usuário escolhe um kit) ──

class SaveQuoteRequest(BaseModel):
    titulo: str
    calculo: CalculateRequest      # request original (cargas, autonomia_dias, etc.) — usado em "Editar cotação"
    resultado: CalculateResponse   # resultado computado, com kit_selecionado = o kit escolhido (já editado pelo usuário)
