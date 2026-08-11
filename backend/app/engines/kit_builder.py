"""
Montagem de kits BESS híbridos (bateria + inversor) com as restrições de
engenharia da skill `dimensionamento-kit-bess-hibrido` (R1–R9).

Lê os produtos da réplica `meubess_products` via valor efetivo
(`kit_attributes.eff*`), que respeita overrides manuais sobre o dado da MeuBESS.

Restrições aplicadas aqui:
  R1  contagem máx de baterias = entradas × máx em paralelo
  R2  potência entregável por ENTRADA (corrente truncada no teto da entrada),
      com distribuição uniforme das baterias
  R3  potência de pico/nominal do inversor ≥ pico/nominal das cargas
  R4  paralelismo de inversores (escala potência) até o limite do modelo
  R5  compatibilidade inversor × bateria (lista declarada ou faixa de tensão)
  R9  nº de caixas de junção (JBW) = entradas com ≥ 2 baterias
  nº de baterias = max(por energia, por potência de partida)

R6 (carga mono em tri) e R8 (tensão de saída EPS × cargas) dependem da tensão
das cargas — aplicados quando `tensoes_carga` é fornecido; caso contrário, ficam
como pendência sinalizada (não se inventa).

Produtos sem os atributos necessários NÃO entram em kit automático: são
devolvidos em `skipped` com o motivo, para o operador completar o cadastro.
"""

import math
from dataclasses import dataclass, field

from app.engines.kit_attributes import eff, eff_bool, eff_float, eff_int


@dataclass
class KitBESS:
    inversor: object
    bateria: object
    qtd_inversores: int
    qtd_baterias: int
    distribuicao_baterias: list[int]      # baterias por entrada (todas as entradas)
    n_caixas_juncao: int
    capacidade_total_kwh: float
    pico_entregavel_kw: float
    preco_total: float
    alertas: list[str] = field(default_factory=list)
    itens: list[dict] = field(default_factory=list)


@dataclass
class SkipReason:
    produto_id: str
    titulo: str
    motivo: str
    # Separa "produto que poderia ser alternativa deste kit" de ruído de
    # catálogo: 128 baterias de outras marcas sem spec são descartadas em TODA
    # cotação, e um aviso que sempre aparece é um aviso que ninguém lê.
    marca: str = ""


# ── helpers de tensão ─────────────────────────────────────────────────────────

def _parse_eps_voltages(eps_output_voltage: str | None) -> set[str]:
    """'127/220' -> {'127','220'}; '380/220;220/127' -> {'380','220','127'}."""
    if not eps_output_voltage:
        return set()
    out: set[str] = set()
    for part in str(eps_output_voltage).replace(";", "/").split("/"):
        p = part.strip()
        if p:
            out.add(p)
    return out


def _tensoes_entre_fases(eps_output_voltage: str | None) -> set[str]:
    """Tensão ENTRE FASES de cada configuração de saída.

    '380/220' -> {'380'}; '380/220;220/127' -> {'380','220'}; '220' -> {'220'}.

    Um inversor trifásico é cadastrado como par `linha/fase`: '380/220' quer
    dizer 380 V entre fases e 220 V entre fase e neutro. Achatar o par num
    conjunto só ('380' e '220' valem igual) fazia o SIW400H T015 "atender
    220 V" e ser oferecido para carga TRIFÁSICA 220 V — que precisa de 220 V
    *entre fases* e receberia 380 V. Carga queimada.

    Só vale para carga TRIFÁSICA, que ocupa as três fases e não tem como ser
    remanejada. Carga bifásica usa dois condutores e só precisa da diferença
    de potencial correta entre eles: num 380/220 ela é ligada entre fase e
    neutro e recebe os 220 V de que precisa. Por isso bifásica não passa por
    aqui — fica no alerta de instalação (_alertas_fase_carga).

    Usa max() em vez da posição porque a ordem do par não é constante no
    cadastro ('380/220' nos trifásicos, '127/220' nos monofásicos split-phase);
    a tensão de linha é sempre a maior das duas (√3 × a de fase).
    """
    if not eps_output_voltage:
        return set()
    out: set[str] = set()
    for config in str(eps_output_voltage).split(";"):
        valores = [p.strip() for p in config.split("/") if p.strip()]
        numericos = [v for v in valores if v.replace(",", ".").replace(".", "").isdigit()]
        if numericos:
            out.add(max(numericos, key=lambda v: float(v.replace(",", "."))))
        elif valores:
            out.update(valores)
    return out


def _eps_efetivo(inv, padrao_entrada: str | None) -> str | None:
    """Configuração de saída que sobra depois de fixar a ligação na rede.

    A saída das linhas K é SELECIONÁVEL ('380/220;220/127'), mas a seleção é
    uma só — é o mesmo enrolamento que se liga na rede e alimenta o EPS. Fixado
    o padrão de entrada, sobra UMA configuração, e é contra ela que a carga tem
    de ser conferida.

    Sem isso, rede e saída eram tratadas como escolhas independentes: um K017
    numa rede 127/220 (onde ele está em 220/127) passava para carga trifásica
    380 V, porque o '380/220' da outra configuração ainda estava na lista.
    """
    eps = eff(inv, "eps_output_voltage")
    tensao_rede = TENSAO_LINHA_REDE.get(padrao_entrada or "")
    if not eps or not tensao_rede or ";" not in str(eps):
        return eps
    for config in str(eps).split(";"):
        if tensao_rede in _tensoes_entre_fases(config):
            return config.strip()
    return eps


def _serve_tensoes(
    inv,
    tensoes_carga: set[str],
    tensoes_entre_fases: set[str] | None = None,
    padrao_entrada: str | None = None,
) -> tuple[bool, str | None]:
    """R8: a saída EPS do inversor atende todas as tensões de carga?

    `tensoes_entre_fases` é o subconjunto exigido por cargas que se alimentam
    entre dois condutores vivos — trifásicas e bifásicas. Essas precisam casar
    com a tensão de LINHA do inversor, não com a de fase; ver
    _tensoes_entre_fases.
    """
    eps_raw = _eps_efetivo(inv, padrao_entrada)
    eps = _parse_eps_voltages(eps_raw)
    split = bool(eff_bool(inv, "split_phase"))
    if not eps:
        return False, "tensão de saída EPS não cadastrada"
    servidas = set(eps)
    if split:
        servidas |= {"127", "220"}  # split-phase atende 127 e 220 mono
    faltando = {t for t in tensoes_carga if t not in servidas}
    if faltando:
        return False, f"saída EPS não atende carga(s) {sorted(faltando)} V"
    if tensoes_entre_fases:
        linha = _tensoes_entre_fases(eps_raw)
        faltando_linha = sorted(t for t in tensoes_entre_fases if t not in linha)
        if faltando_linha:
            return False, (
                f"saída {eps_raw} V não entrega {faltando_linha} V entre fases")
    return True, None


def compativel_com_cargas(
    inv,
    tensoes_carga: set[str] | None,
    fases_carga: set[str] | None,
    tensoes_entre_fases_carga: set[str] | None = None,
    padrao_entrada: str | None = None,
) -> tuple[bool, str | None]:
    """R8 completa (tensão + fase) para um inversor.

    Exposta porque o caminho combinado FV+armazenamento **troca** o inversor
    híbrido depois que build_kits já filtrou (o "híbrido ampliado", que sobe de
    modelo para absorver mais FV). Sem reaplicar a regra ali, uma carga
    trifásica voltava com inversor monofásico sempre que havia FV no projeto.
    """
    if tensoes_carga:
        ok, why = _serve_tensoes(inv, tensoes_carga, tensoes_entre_fases_carga,
                                 padrao_entrada)
        if not ok:
            return False, why
    if fases_carga:
        ok, why = _serve_fases(inv, fases_carga)
        if not ok:
            return False, why
    return True, None


def _norm_fase(v) -> str:
    """'Trifásico' / 'TRIFASICO' → 'trifasico'."""
    import unicodedata
    s = unicodedata.normalize("NFD", str(v or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.strip().lower()


def _serve_fases(inv, fases_carga: set[str]) -> tuple[bool, str | None]:
    """R8, lado FASE: carga trifásica exige inversor trifásico.

    A checagem de tensão sozinha deixava passar justamente o caso mais comum do
    catálogo — as 29 cargas trifásicas cadastradas são todas 220 V, e um
    inversor MONOfásico 220 V "atende 220 V". Atender a tensão não é ter as três
    fases.
    """
    if "trifasico" in fases_carga and not _inversor_e_trifasico(inv):
        return False, "carga trifásica exige inversor trifásico"
    return True, None


def _alertas_fase_carga(inv, fases_carga: set[str]) -> list[str]:
    """Carga bifásica (2 condutores vivos) numa saída monofásica simples.

    Não bloqueia: uma carga "bifásica 220 V" no padrão 127/220 é, do ponto de
    vista do inversor, uma carga de 220 V entre dois terminais — o que uma saída
    mono 220 V entrega. Mas a decisão depende da instalação, então fica
    registrado em vez de silencioso.
    """
    if "bifasico" not in fases_carga:
        return []
    if _inversor_e_trifasico(inv) or bool(eff_bool(inv, "split_phase")):
        return []
    return ["Carga bifásica atendida por saída monofásica — confirmar se a carga "
            "aceita alimentação entre fase e neutro na tensão nominal."]


def _inversor_e_trifasico(inv) -> bool:
    eps = _parse_eps_voltages(eff(inv, "eps_output_voltage"))
    if "380" in eps:
        return True
    return (eff(inv, "phase") or "").strip().lower() == "trifasico"


#: Tensão ENTRE FASES de cada padrão de entrada trifásico. É a tensão que um
#: inversor trifásico precisa conseguir operar para se ligar direto na rede.
TENSAO_LINHA_REDE = {"tri_127_220": "220", "tri_220_380": "380"}

#: Tensões de conexão disponíveis em cada padrão de entrada, por tipo de
#: inversor. Ausência da chave significa que aquele tipo não se conecta
#: naquela rede — um trifásico não tem onde se ligar num padrão monofásico.
#:
#: O inversor MONOFÁSICO tem duas opções numa rede trifásica: fase-neutro
#: (tensão de fase) ou entre duas fases (tensão de linha). Numa rede 127/220
#: ele se liga em 127 V ou em 220 V; as duas são conexões reais e o catálogo
#: tem modelos das duas. Numa rede monofásica só existe uma tensão, e é por
#: isso que um inversor de saída 220 V não se conecta num padrão de 127 V.
CONEXOES_REDE: dict[str, dict[str, set[str]]] = {
    "mono_127":    {"monofasico": {"127"}},
    "mono_220":    {"monofasico": {"220"}},
    "tri_127_220": {"monofasico": {"127", "220"}, "trifasico": {"220"}},
    "tri_220_380": {"monofasico": {"220", "380"}, "trifasico": {"380"}},
}

#: Tensões que EXISTEM na instalação, para conferir as cargas declaradas.
#: É a união fase-neutro + entre fases de cada padrão.
#:
#: Um padrão monofásico tem UMA tensão. Se a tensão de fase é 220 V, não há
#: 127 V na instalação — mesmo critério que o engenheiro aplicou à rede
#: 220/380, confirmado por ele para a rede monofásica 220 V também.
TENSOES_REDE_DISPONIVEIS: dict[str, set[str]] = {
    "mono_127":    {"127"},
    "mono_220":    {"220"},
    "tri_127_220": {"127", "220"},
    "tri_220_380": {"220", "380"},
}


def carga_existe_na_rede(
    padrao_entrada: str | None,
    tensao_carga: str | None,
    fase_carga: str | None,
) -> str | None:
    """A carga declarada pode existir nessa instalação? Motivo se não puder.

    Validação de ENTRADA, anterior a qualquer escolha de equipamento. Sem ela o
    motor aceitava combinações que não existem no mundo — carga 220 V num
    padrão monofásico 127 V, carga trifásica num padrão monofásico — e ia até o
    fim montando kit para elas. Um kit correto para um cenário impossível é um
    erro que ninguém percebe.

    Regras, na ordem em que um projetista confere:
      1. carga trifásica exige rede trifásica;
      2. carga trifásica exige a tensão ENTRE FASES da rede (uma rede 220/380
         entrega 380 V entre fases, então não alimenta carga trifásica 220 V);
      3. carga mono ou bifásica exige que sua tensão exista na rede, seja
         fase-neutro ou entre fases.
    """
    if not padrao_entrada or not tensao_carga:
        return None   # sem o dado não se inventa restrição
    disponiveis = TENSOES_REDE_DISPONIVEIS.get(padrao_entrada)
    if not disponiveis:
        return None
    rede_tri = padrao_entrada.startswith("tri")
    rotulo = "/".join(sorted(disponiveis, key=float))

    if fase_carga == "trifasico":
        if not rede_tri:
            return (f"carga trifásica em padrão de entrada monofásico "
                    f"{rotulo} V — a instalação não tem três fases")
        linha = TENSAO_LINHA_REDE.get(padrao_entrada)
        if linha and tensao_carga != linha:
            return (f"carga trifásica {tensao_carga} V em rede que entrega "
                    f"{linha} V entre fases")
        return None

    if tensao_carga not in disponiveis:
        return (f"carga {tensao_carga} V em padrão de entrada {rotulo} V — "
                f"essa tensão não existe na instalação")
    return None


def _tensoes_rede_inversor(inv) -> set[str]:
    """Tensões de linha em que um inversor TRIFÁSICO consegue operar.

    Vem da saída EPS — que nas linhas K é SELECIONÁVEL ('380/220;220/127' são
    duas configurações do mesmo enrolamento, e a seleção vale para os dois
    lados — somada à tensão de conexão do cadastro. Um T015 dá {'380'}; um
    K017 dá {'380','220'}, e é por isso que o K serve as duas redes trifásicas
    e o T não.
    """
    tensoes = set(_tensoes_entre_fases(eff(inv, "eps_output_voltage")))
    v = str(eff(inv, "voltage") or "").strip()
    if v:
        tensoes.add(v)
    return tensoes


def _tensao_conexao_monofasico(inv) -> str:
    """Tensão em que um inversor MONOFÁSICO se liga na rede.

    É o campo `voltage` do cadastro, e só ele. NÃO se deriva da saída EPS: um
    SIW200H S075 é split-phase e entrega 127 V no EPS, mas se conecta na rede
    em 220 V — o 127 V é gerado pelo inversor, não é por onde ele é alimentado.

    Usar a saída EPS aqui fazia o motor aceitar os split-phase num padrão de
    entrada monofásico de 127 V, onde nenhum inversor monofásico do catálogo
    tem como ser ligado (todos se conectam em 220 V).
    """
    return str(eff(inv, "voltage") or "").strip()


def _bloqueio_rede(inv, padrao_entrada: str | None) -> str | None:
    """R7 BLOQUEANTE: inversor que não se conecta à rede da unidade.

    Duas checagens, uma por tipo de inversor:

    - TRIFÁSICO: precisa operar na tensão entre fases da rede. Um SIW400H T015
      (380 V) numa rede 127/220 só funciona com autotransformador — era alerta,
      virou bloqueio por decisão comercial. O K017/K008 tem saída selecionável
      (380/220 ou 220/127), opera nas duas redes trifásicas, e continua passando.

    - MONOFÁSICO: precisa operar na tensão fase-neutro da rede. Um SIW200H M050
      (saída 220 V) não se liga num padrão monofásico 127 V. Isso não era
      verificado: o motor só olhava a tensão da CARGA, então numa rede de 127 V
      ele oferecia inversores de 220 V que não têm como ser alimentados.
    """
    if not padrao_entrada:
        return None
    conexoes = CONEXOES_REDE.get(padrao_entrada)
    if not conexoes:
        return None

    e_tri = _inversor_e_trifasico(inv)
    da_rede = conexoes.get("trifasico" if e_tri else "monofasico")
    tensoes_inv = _tensoes_rede_inversor(inv)
    if not tensoes_inv:
        return None

    if e_tri:
        if not da_rede:
            # Rede monofásica não tem três fases para ligar. Era alerta, e
            # alerta deixava um SIW400H K008 de R$ 24 mil ganhar a cotação de
            # uma residência 127 V — mesma razão que fez o caso do
            # autotransformador virar bloqueio.
            disponivel = "/".join(sorted(conexoes.get("monofasico") or {"?"}))
            return (f"inversor trifásico em padrão de entrada monofásico "
                    f"{disponivel} V — exige mudança do padrão junto à "
                    f"concessionária")
        if not (da_rede & tensoes_inv):
            return (f"inversor trifásico {'/'.join(sorted(tensoes_inv))} V não opera "
                    f"em rede {'/'.join(sorted(da_rede))} V entre fases "
                    f"(exigiria autotransformador)")
        return None

    # Monofásico: vale a tensão de CONEXÃO, não a da saída EPS. Ser split-phase
    # não ajuda aqui — o 127 V dele é gerado na saída, não é por onde entra.
    conexao = _tensao_conexao_monofasico(inv)
    if da_rede and conexao and conexao not in da_rede:
        return (f"inversor monofásico se conecta em {conexao} V, e o padrão de "
                f"entrada é {'/'.join(sorted(da_rede))} V")
    return None


def _alertas_rede(
    inv,
    fase_instalacao: str | None,
    padrao_entrada: str | None,
    qtd_inversores: int = 1,
) -> list[str]:
    """
    R7 — compatibilidade do inversor com a rede da unidade (apenas ALERTA).
    `padrao_entrada` ∈ {mono_127, mono_220, tri_127_220, tri_220_380} (opcional).
    """
    alertas: list[str] = []
    inv_tri = _inversor_e_trifasico(inv)
    eps = _parse_eps_voltages(eff(inv, "eps_output_voltage"))

    unidade_mono = (padrao_entrada or "").startswith("mono") or fase_instalacao == "monofasico"
    if inv_tri and unidade_mono:
        alertas.append(
            "Inversor trifásico em unidade monofásica — requer aumento de carga / "
            "mudança do padrão de entrada junto à concessionária."
        )
    # O caso "inversor 380 V em rede 127/220" saiu daqui e virou bloqueio
    # (_bloqueio_rede): a plataforma é usada por vendedores sem formação
    # técnica, e um alerta que exige autotransformador passa batido.
    #
    # Monofásico em rede trifásica é conexão válida (fase-neutro) e costuma ser
    # mais barata que um trifásico equivalente — mas carrega uma fase por
    # inversor. Com 1 ou 2 unidades a geração fica desequilibrada entre as três.
    if (padrao_entrada or "").startswith("tri") and not inv_tri and qtd_inversores % 3 != 0:
        alertas.append(
            f"{qtd_inversores}× inversor monofásico em rede trifásica — conexão "
            f"fase-neutro, com geração desequilibrada entre as fases. Confirmar "
            f"o limite de desequilíbrio da concessionária."
        )
    return alertas


# ── distribuição de baterias / potência DC (R2) ───────────────────────────────

def _distribuir(n_bat: int, n_entradas: int) -> list[int]:
    """Distribui n baterias o mais uniformemente possível entre as entradas."""
    base, extra = divmod(n_bat, n_entradas)
    return [base + (1 if i < extra else 0) for i in range(n_entradas)]


def _pico_dc_kw(dist: list[int], i_input_a: float, corrente_bat_a: float, tensao_v: float) -> float:
    """Potência DC de pico entregável: corrente por entrada truncada no teto."""
    total_a = sum(min(n * corrente_bat_a, i_input_a) for n in dist if n > 0)
    return total_a * tensao_v / 1000.0


# ── compatibilidade inversor × bateria (R5) ───────────────────────────────────

def _compativel(inv, bat) -> tuple[bool, str | None]:
    lista = eff(bat, "compatible_inverters")
    titulo_inv = (eff(inv, "title") or "").upper()
    if lista:
        # match por família declarada no datasheet (ex.: "SIW200H; SIW400H")
        familias = [s.strip().upper() for s in str(lista).replace(";", ",").split(",") if s.strip()]
        if any(fam and fam in titulo_inv for fam in familias):
            return True, None
        # lista existe mas não casou → incompatível
        return False, "inversor fora da lista de compatíveis da bateria"
    # sem lista: exige faixa de tensão da bateria ⊂ faixa aceita pelo inversor
    bmin, bmax = eff_float(bat, "operating_voltage_min_v"), eff_float(bat, "operating_voltage_max_v")
    imin, imax = eff_float(inv, "battery_voltage_min_v"), eff_float(inv, "battery_voltage_max_v")
    if None in (bmin, bmax, imin, imax):
        return False, "faixa de tensão de bateria/inversor não cadastrada"
    if bmin >= imin and bmax <= imax:
        return True, None
    return False, "faixa de tensão da bateria fora da janela do inversor"


# ── núcleo ────────────────────────────────────────────────────────────────────

def _potencias_da_configuracao(inv, padrao_entrada: str | None) -> dict:
    """Potência nominal e de pico NA CONFIGURAÇÃO em que o inversor vai operar.

    A linha K tem duas potências, não uma: o SIW400H K008 T015 entrega 8,6 kW
    ligado em 220/127 e 15 kW em 380/220 — é o mesmo equipamento reconfigurado,
    e o próprio título do produto carrega os dois modelos. O motor usava só a
    menor, o que subdimensionava a linha K em rede 380 V e às vezes escalava
    para dois inversores sem necessidade.

    O dado vem de `potencia_por_configuracao` em overrides_tecnicos, chaveado
    pela tensão entre fases. Sem esse override (todos os outros modelos, que
    têm configuração única), devolve vazio e o chamador usa os campos normais.
    """
    tabela = eff(inv, "potencia_por_configuracao")
    tensao = TENSAO_LINHA_REDE.get(padrao_entrada or "")
    if not isinstance(tabela, dict) or not tensao:
        return {}
    return tabela.get(tensao) or {}


def _attrs_inversor(inv, padrao_entrada: str | None = None) -> tuple[dict, str | None]:
    """Lê os atributos do inversor; retorna (attrs, motivo_se_incompleto)."""
    cfg = _potencias_da_configuracao(inv, padrao_entrada)
    a = {
        "peak_power_kw":   cfg.get("peak_power_kw") or eff_float(inv, "peak_power_kw"),
        "eps_nominal_kw":  cfg.get("max_eps_power") or eff_float(inv, "max_eps_power") or eff_float(inv, "max_output_power") or eff_float(inv, "power"),
        "battery_inputs":  eff_int(inv, "battery_inputs"),
        "i_input_a":       eff_float(inv, "battery_input_max_current_a"),
        "max_paralelo":    eff_int(inv, "max_parallel_units") or 1,
        "preco":           eff_float(inv, "price") or eff_float(inv, "preco") or 0.0,
    }
    faltando = [k for k in ("peak_power_kw", "eps_nominal_kw", "battery_inputs", "i_input_a") if not a[k]]
    if faltando:
        return a, f"faltam dados do inversor: {', '.join(faltando)}"
    return a, None


def _attrs_bateria(bat) -> tuple[dict, str | None]:
    a = {
        "usable_kwh":     eff_float(bat, "usable_capacity_kwh"),
        "max_paralelo":   eff_int(bat, "max_parallel_batteries"),
        "i_cont_a":       eff_float(bat, "max_continuous_current_a"),
        "i_pico_a":       eff_float(bat, "peak_discharge_current_a") or eff_float(bat, "max_continuous_current_a"),
        "tensao_v":       eff_float(bat, "nominal_voltage_v"),
        "preco":          eff_float(bat, "price") or eff_float(bat, "preco") or 0.0,
    }
    faltando = [k for k in ("usable_kwh", "max_paralelo", "i_cont_a", "tensao_v") if not a[k]]
    if faltando:
        return a, f"faltam dados da bateria: {', '.join(faltando)}"
    return a, None


def _jbw_preco(jbw_produtos: list | None, marca: str) -> tuple[float, str, bool]:
    """Preço real da caixa de junção no catálogo (mesma marca, senão a mais barata
    disponível). Retorna (preco, nome, encontrado) — encontrado=False sinaliza que
    não há JBW cadastrada e o preço 0.0 é um placeholder, não um valor real."""
    if not jbw_produtos:
        return 0.0, "Caixa de junção (JBW)", False
    mesma_marca = [j for j in jbw_produtos if (eff(j, "marca") or "") == marca]
    candidatos = mesma_marca or jbw_produtos
    melhor = min(candidatos, key=lambda j: eff_float(j, "price") or eff_float(j, "preco") or float("inf"))
    preco = eff_float(melhor, "price") or eff_float(melhor, "preco") or 0.0
    return preco, str(eff(melhor, "title") or "Caixa de junção (JBW)"), preco > 0


def _montar_kit(inv, bat, qtd_inv, n, ia, ba, n_entradas, alertas, titulo_fn, jbw_produtos: list | None = None) -> KitBESS:
    """Monta o KitBESS (itens, distribuição, preço, pico) para uma combinação já
    validada de inversor/bateria/quantidades — reutilizado tanto pela montagem normal
    (n suficiente) quanto pela variante econômica (n menor que o suficiente, ver
    economic_undershoot_kit)."""
    dist = _distribuir(n, n_entradas)
    pico_dc = _pico_dc_kw(dist, ia["i_input_a"], ba["i_pico_a"], ba["tensao_v"])
    pico_inv_total = ia["peak_power_kw"] * qtd_inv
    n_jbw = sum(1 for x in dist if x >= 2)

    itens = [
        {"nome": titulo_fn(inv), "tipo": "inversor", "qtd": qtd_inv,
         "preco_unitario": round(ia["preco"], 2), "preco_total": round(ia["preco"] * qtd_inv, 2),
         "potencia_inversao_kw": round(ia["eps_nominal_kw"], 2),
         "potencia_pico_kw": round(ia["peak_power_kw"], 2),
         "corrente_entrada_a": round(ia["i_input_a"], 2),
         "entradas_bateria": ia["battery_inputs"]},
        {"nome": titulo_fn(bat), "tipo": "bateria", "qtd": n,
         "preco_unitario": round(ba["preco"], 2), "preco_total": round(ba["preco"] * n, 2),
         "energia_unit_kwh": round(ba["usable_kwh"], 2),
         "corrente_pico_a": round(ba["i_pico_a"], 2),
         "tensao_v": round(ba["tensao_v"], 2)},
    ]
    preco_jbw_total = 0.0
    if n_jbw > 0:
        marca = str(eff(inv, "marca") or eff(bat, "marca") or "")
        preco_jbw, nome_jbw, jbw_encontrada = _jbw_preco(jbw_produtos, marca)
        preco_jbw_total = preco_jbw * n_jbw
        itens.append({"nome": nome_jbw, "tipo": "acessorio", "qtd": n_jbw,
                      "preco_unitario": round(preco_jbw, 2), "preco_total": round(preco_jbw_total, 2)})
        if not jbw_encontrada:
            alertas = [*alertas, "Caixa de junção (JBW) sem preço cadastrado no catálogo — orçamento incompleto"]

    return KitBESS(
        inversor=inv,
        bateria=bat,
        qtd_inversores=qtd_inv,
        qtd_baterias=n,
        distribuicao_baterias=dist,
        n_caixas_juncao=n_jbw,
        capacidade_total_kwh=round(ba["usable_kwh"] * n, 2),
        pico_entregavel_kw=round(min(pico_dc, pico_inv_total), 2),
        preco_total=round(ba["preco"] * n + ia["preco"] * qtd_inv + preco_jbw_total, 2),
        alertas=alertas,
        itens=itens,
    )


def economic_undershoot_kit(kits: list[KitBESS], e_bat_kwh: float, jbw_produtos: list | None = None) -> KitBESS | None:
    """
    A montagem normal sempre escolhe o MENOR n de baterias que já é suficiente
    (n_energia = ceil(e_bat_kwh / usable_kwh)) — logo, por construção, todo kit em
    `kits` tem cobertura de energia ≥ 100%. Não existe naturalmente uma opção abaixo
    disso na lista.

    Esta função gera essa opção de propósito: para cada par inversor×bateria já
    validado em `kits`, testa quantidades MENORES que o mínimo suficiente (n_under <
    qtd_baterias) e devolve a mais barata cuja cobertura mais se aproxima de 100%
    sem atingir — a "alternativa mais econômica" pedida pelo usuário.
    """
    if not kits or not e_bat_kwh or e_bat_kwh <= 0:
        return None

    def _tit(p):
        return eff(p, "title") or str(getattr(p, "meubess_id", "?"))

    melhor: KitBESS | None = None
    melhor_cobertura = -1.0
    for k in kits:
        ia, motivo = _attrs_inversor(k.inversor)
        if motivo:
            continue
        ba, motivo_b = _attrs_bateria(k.bateria)
        if motivo_b:
            continue
        n_entradas = ia["battery_inputs"] * k.qtd_inversores

        for n in range(1, k.qtd_baterias):
            cobertura = (ba["usable_kwh"] * n) / e_bat_kwh
            if cobertura >= 1.0:
                continue
            preco = ba["preco"] * n + ia["preco"] * k.qtd_inversores
            melhor_preco = melhor.preco_total if melhor else None
            mais_proximo = cobertura > melhor_cobertura + 1e-9
            empate_mais_barato = (
                abs(cobertura - melhor_cobertura) <= 1e-9
                and melhor_preco is not None and preco < melhor_preco
            )
            if mais_proximo or empate_mais_barato:
                melhor = _montar_kit(k.inversor, k.bateria, k.qtd_inversores, n, ia, ba, n_entradas, list(k.alertas), _tit, jbw_produtos)
                melhor_cobertura = cobertura

    return melhor


def build_kits(
    inversores: list,
    baterias: list,
    *,
    pn_kva: float,
    pp_kva: float,
    e_bat_kwh: float,
    fase_instalacao: str | None = None,
    tensoes_carga: set[str] | None = None,
    fases_carga: set[str] | None = None,
    tensoes_entre_fases_carga: set[str] | None = None,
    padrao_entrada: str | None = None,
    require_same_brand: bool = True,
    jbw_produtos: list | None = None,
) -> tuple[list[KitBESS], list[SkipReason]]:
    """
    Monta kits viáveis ordenados por preço. `skipped` lista produtos descartados
    por falta de dado ou incompatibilidade (com o motivo).
    """
    kits: list[KitBESS] = []
    skipped: list[SkipReason] = []

    def _id(p):
        return str(getattr(p, "meubess_id", "?"))

    def _tit(p):
        return eff(p, "title") or _id(p)

    def _skip(p, motivo):
        return SkipReason(_id(p), _tit(p), motivo, str(eff(p, "marca") or ""))

    for inv in inversores:
        # padrao_entrada define em qual configuração a linha K vai operar, e
        # com isso qual das duas potências dela vale aqui.
        ia, motivo = _attrs_inversor(inv, padrao_entrada)
        if motivo:
            skipped.append(_skip(inv, motivo))
            continue

        # R7 — inversor × rede da unidade (bloqueante desde a decisão comercial
        # de não confiar em alerta para o caso do autotransformador)
        motivo_rede = _bloqueio_rede(inv, padrao_entrada)
        if motivo_rede:
            skipped.append(_skip(inv, motivo_rede))
            continue

        # R8 — tensão de saída EPS × cargas (quando informado)
        if tensoes_carga:
            ok, why = _serve_tensoes(inv, tensoes_carga, tensoes_entre_fases_carga,
                                     padrao_entrada)
            if not ok:
                skipped.append(_skip(inv, why))
                continue

        # R8 — fase das cargas × saída do inversor (bloqueante)
        if fases_carga:
            ok, why = _serve_fases(inv, fases_carga)
            if not ok:
                skipped.append(_skip(inv, why))
                continue

        # R7 — alertas de compatibilidade com a rede da unidade (não bloqueia)
        alertas_rede = _alertas_rede(inv, fase_instalacao, padrao_entrada)
        alertas_rede += _alertas_fase_carga(inv, fases_carga or set())

        # R3/R4 — potência: escala nº de inversores por pico e nominal
        qtd_inv = max(
            math.ceil(pp_kva / ia["peak_power_kw"]),
            math.ceil(pn_kva / ia["eps_nominal_kw"]),
            1,
        )
        if qtd_inv > ia["max_paralelo"]:
            skipped.append(_skip(inv,
                f"potência exige {qtd_inv} inversores (máx paralelo {ia['max_paralelo']})"))
            continue

        n_entradas = ia["battery_inputs"] * qtd_inv

        for bat in baterias:
            ba, motivo_b = _attrs_bateria(bat)
            if motivo_b:
                skipped.append(_skip(bat, motivo_b))
                continue
            if require_same_brand and (eff(inv, "marca") or "") != (eff(bat, "marca") or ""):
                continue
            ok, why = _compativel(inv, bat)
            if not ok:
                # R5 rejeitava em silêncio: o par sumia sem explicação, e ficar
                # sem kit "sem motivo" foi o que tornou os erros de campo tão
                # difíceis de diagnosticar. Não casar é resultado legítimo, mas
                # tem que ser dizível.
                skipped.append(_skip(
                    inv, f"{why or 'incompatível'} (com {_tit(bat)})"))
                continue

            cap_bat = ba["max_paralelo"] * n_entradas
            n_energia = max(1, math.ceil(e_bat_kwh / ba["usable_kwh"]))

            # n por potência de partida (R2): menor n cujo pico entregável ≥ Pp
            pico_inv_total = ia["peak_power_kw"] * qtd_inv
            n_pot = None
            for n in range(1, cap_bat + 1):
                dist = _distribuir(n, n_entradas)
                pico_dc = _pico_dc_kw(dist, ia["i_input_a"], ba["i_pico_a"], ba["tensao_v"])
                if min(pico_dc, pico_inv_total) >= pp_kva:
                    n_pot = n
                    break
            if n_pot is None:
                skipped.append(_skip(inv,
                    f"nem o banco cheio entrega o pico {pp_kva:.1f} kVA (com {_tit(bat)})"))
                continue

            n = max(n_energia, n_pot)
            if n > cap_bat:
                skipped.append(_skip(inv,
                    f"energia exige {n} baterias (máx {cap_bat} neste arranjo)"))
                continue

            alertas: list[str] = list(alertas_rede)
            # R6 — carga mono em inversor tri (advisory).
            # Só faz sentido quando EXISTE carga monofásica: antes disparava em
            # qualquer projeto trifásico, inclusive com 100% de cargas tri, e
            # alerta que aparece sem motivo é alerta que se aprende a ignorar.
            tem_carga_mono = bool(fases_carga) and any(
                f in ("monofasico", "bifasico") for f in fases_carga)
            if fase_instalacao == "trifasico" and tem_carga_mono:
                alertas.append("verifique cargas monofásicas ≤ 1/3 da potência (alerta)")

            kits.append(_montar_kit(inv, bat, qtd_inv, n, ia, ba, n_entradas, alertas, _tit, jbw_produtos))

    # Ordenação final. O preço decide, mas empate é comum: no catálogo WEG a
    # CB100 custa exatamente o dobro da CB050, então 4×CB050 e 2×CB100 dão o
    # mesmo total. Antes o desempate era a ordem de iteração da lista —
    # arbitrário e não explicável para um engenheiro. Critérios, nesta ordem:
    #   1. menor preço
    #   2. maior pico entregável (folga de partida de graça, pelo mesmo valor)
    #   3. menos componentes (menos conexões, menos espaço, menos mão de obra)
    kits.sort(key=lambda k: (k.preco_total, -k.pico_entregavel_kw,
                             k.qtd_baterias + k.qtd_inversores))
    return kits, skipped
