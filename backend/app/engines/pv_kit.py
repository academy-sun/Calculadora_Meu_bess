"""
Dimensionamento do sistema fotovoltaico (FV) e reconciliação com armazenamento (BESS).

Modos de operação (determinados pelo chamador em service.py):

  "on-grid puro"  — sem tabela de cargas: kit FV avulso (módulos + inversor string +
                    cabeamento CC + estrutura), sem bateria nem inversor híbrido.

  "combinado"     — com tabela de cargas E kWp informado: dimensiona módulos e
                    armazenamento em paralelo, tenta encaixar os módulos na entrada CC
                    do inversor híbrido já escolhido (Caminho DC). Se não couber,
                    oferece dois caminhos:
                      A) split: módulos divididos entre o híbrido + inversor string para o restante.
                      B) scaled: mais unidades ou modelo maior de híbrido até caber tudo no CC.

Princípio: nunca inventa dado. Se um produto não tem Voc/Imp, ele não é elegível.
"""

import math
from dataclasses import dataclass, field

from app.engines.kit_attributes import eff, eff_float, eff_int
from app.engines.kit_builder import (
    KitBESS,
    _attrs_inversor,
    _attrs_bateria,
    _compativel,
    _montar_kit,
    economic_undershoot_kit,
)

DIAS_MES = 30
CABO_STEP_M = 25
OVERSIZE_DC_AC = 1.5   # razão DC/AC alvo para seleção de inversor string (mesma da MeuBESS)

# Teto de matriz FV do inversor HÍBRIDO, quando o produto não traz o dado.
# Datasheets WEG, campo "Máxima Potência da Matriz [Wp]" (ou "Potência Máxima
# FV (STC)"), consistente em 2,0 × a potência CA nominal nas três linhas:
#   M050  5,0 kW → 10.000 Wp    S075  7,5 kW → 15.000 Wp
#   T015 15,0 kW → 30.000 Wp (380/220)
# Não confundir com "Máxima Potência Recomendada de Entrada PV", que é ~1,5× —
# aquele é potência CC entregue, este é Wp de placa, que é o que comparamos.
MAX_MATRIZ_DC_AC_HIBRIDO = 2.0


def _tit(p) -> str:
    return str(eff(p, "title") or getattr(p, "meubess_id", "?"))


def _preco(p) -> float:
    return eff_float(p, "price") or eff_float(p, "preco") or 0.0


# ─────────────────────────────────────────────────────────────────────────────
# 1. Resolução da potência de pico alvo
# ─────────────────────────────────────────────────────────────────────────────

def resolve_kwp_alvo(
    *,
    powerpeak_kwp: float | None,
    consumo_medio_mensal_kwh: float | None,
    hsp_media: float | None,
    taxa_desempenho: float | None,
) -> float | None:
    """kWp direto (pré-dimensionado no CRM) tem prioridade; senão derivado de
    consumo médio mensal ÷ (30 × HSP × taxa de desempenho)."""
    if powerpeak_kwp and powerpeak_kwp > 0:
        return powerpeak_kwp
    if consumo_medio_mensal_kwh and hsp_media:
        pr = taxa_desempenho if (taxa_desempenho and 0 < taxa_desempenho <= 1) else 0.8
        return consumo_medio_mensal_kwh / (DIAS_MES * hsp_media * pr)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 2. Seleção de módulo
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ModuloAttrs:
    produto: object
    voc_v: float    # Voc do módulo em V
    imp_a: float    # Imp (corrente de máxima potência) em A
    isc_a: float    # Isc (corrente de curto-circuito) em A — limita strings em paralelo
    wp: float       # Potência do módulo em W
    preco: float    # Preço unitário


def _attrs_modulo(modulo) -> ModuloAttrs | None:
    """Lê os atributos elétricos do módulo. Retorna None se incompletos."""
    voc = eff_float(modulo, "voc_max_voltage")
    imp = eff_float(modulo, "max_power_current")
    power_kw = eff_float(modulo, "power")
    if voc is None or imp is None or not power_kw or voc <= 0 or imp <= 0 or power_kw <= 0:
        return None
    # Isc: usa o valor real do datasheet; na ausência, estima ~1.06×Imp (razão típica Isc/Imp)
    isc = eff_float(modulo, "short_circuit_current_module") or round(imp * 1.06, 2)
    return ModuloAttrs(
        produto=modulo,
        voc_v=voc,
        imp_a=imp,
        isc_a=isc,
        wp=round(power_kw * 1000, 1),
        preco=_preco(modulo),
    )


def select_module(
    modulos: list,
    kwp_alvo: float,
    *,
    prefer_marca: str | None = None,
) -> tuple[ModuloAttrs | None, int]:
    """Escolhe o módulo mais barato por Wp dentre os com dados elétricos completos.
    Quantidade = ceil(kWp alvo / Wp do módulo) — mesma fórmula da MeuBESS.
    Retorna (None, 0) se nenhum módulo tem dados válidos."""
    candidatos = [a for m in modulos if (a := _attrs_modulo(m)) is not None]
    if not candidatos:
        return None, 0

    def score(a: ModuloAttrs) -> float:
        if a.preco <= 0:
            return float("inf")
        return a.preco / a.wp   # R$/Wp — menor é melhor

    candidatos.sort(key=score)
    melhor = candidatos[0]
    qty = max(1, math.ceil(kwp_alvo * 1000 / melhor.wp))
    return melhor, qty


# ─────────────────────────────────────────────────────────────────────────────
# 3. Capacidade CC do inversor para um módulo específico
# ─────────────────────────────────────────────────────────────────────────────

def dc_capacity_modules(inv, qtd_inv: int, modulo: ModuloAttrs) -> int:
    """Quantos módulos (total) a(s) unidade(s) do inversor suportam na entrada CC.

    - Série (n_serie) = floor(voc_max / Voc_módulo): string não pode exceder a tensão máx.
    - Paralelo por MPPT = nº de entradas físicas por MPPT (qty_inputs_per_mppt). O LIMITE
      DE CORRENTE que bloqueia é a Isc do módulo vs Isc máx da entrada do inversor — se a
      Isc do módulo excede o limite, o inversor é incompatível (retorna 0). A corrente
      NOMINAL (string_current vs Imp) só causa clipping de energia, não é bloqueio.
    - Capacidade total = n_serie × entradas/MPPT × qty_mppt × qtd_inv.
    - **Teto de potência**: caber eletricamente não é o mesmo que o inversor
      processar aquela potência. Um SIW200H M075 (7,5 kW, 3 MPPT, Voc máx 600 V)
      aceita 36 módulos de 550 Wp pela tensão/corrente — 19,8 kWp, ou DC/AC de
      2,6. Sem esse teto, o motor entregava kits assim.
    """
    voc_max = eff_float(inv, "voc_max_voltage")
    qty_mppt = eff_int(inv, "qty_mppt")
    inputs_per_mppt = eff_int(inv, "qty_inputs_per_mppt") or 1
    isc_max = eff_float(inv, "short_circuit_current_inverter")
    if not voc_max or not qty_mppt:
        return 0

    n_serie = math.floor(voc_max / modulo.voc_v)
    if n_serie < 1:
        return 0

    # incompatível se a corrente de curto do módulo excede o limite da entrada (dano real)
    if isc_max and modulo.isc_a > isc_max:
        return 0

    cap_eletrica = n_serie * inputs_per_mppt * qty_mppt * qtd_inv

    # Teto de matriz FV. Preferência para o dado do produto; sem ele, a razão
    # por tipo de inversor. `max_pv_power_w` ainda NÃO existe no cadastro
    # meubess_products — é a lacuna a fechar para deixar de depender da razão.
    if modulo.wp <= 0:
        return cap_eletrica

    max_matriz_w = eff_float(inv, "max_pv_power_w")
    if not max_matriz_w:
        potencia_ca_kw = eff_float(inv, "power") or eff_float(inv, "max_output_power")
        if not potencia_ca_kw or potencia_ca_kw <= 0:
            return cap_eletrica
        # híbrido tem entrada de bateria; inversor string, não
        e_hibrido = bool(eff_int(inv, "battery_inputs"))
        razao = MAX_MATRIZ_DC_AC_HIBRIDO if e_hibrido else OVERSIZE_DC_AC
        max_matriz_w = potencia_ca_kw * 1000 * razao

    cap_matriz = math.floor(max_matriz_w * qtd_inv / modulo.wp)
    return max(0, min(cap_eletrica, cap_matriz))


# ─────────────────────────────────────────────────────────────────────────────
# 4. Acessórios FV: cabeamento CC, MC4 e estrutura (fórmulas MeuBESS)
# ─────────────────────────────────────────────────────────────────────────────

def _cabo_da_cor(cabos: list, cor: str):
    """Cabo daquela cor, o mais barato. Cai no mais barato geral se não houver.

    O catálogo tem os dois produtos — 'CABO SOLAR 6MM PRETO' e '... VERMELHO' —
    mas o kit escolhia UM e o repetia com um sufixo de cor no nome. A linha
    vermelha da proposta saía com o produto preto: nome e código errados, e um
    dos dois cabos nunca era comprado do item certo. O sufixo some junto, que
    era a origem da confusão.
    """
    da_cor = [c for c in cabos if cor.lower() in str(_tit(c)).lower()]
    return min(da_cor or cabos, key=_preco)


def _cabo_mc4_items(qty_modulos: int, cabos: list, mc4s: list) -> list[dict]:
    """
    Cabos CC: metros = ceil((módulos×2) / 25) × 25, em duas cores (preto + vermelho).
    MC4: 1 + ceil(módulos/10).
    Mesma fórmula usada pela MeuBESS (AccessoriesCalc).
    """
    itens: list[dict] = []
    metros = math.ceil((qty_modulos * 2) / CABO_STEP_M) * CABO_STEP_M if qty_modulos > 0 else 0

    cabos_v = [c for c in cabos if _preco(c) > 0]
    if cabos_v and metros > 0:
        for cor in ("Preto", "Vermelho"):
            cabo = _cabo_da_cor(cabos_v, cor)
            itens.append({
                "meubess_id": str(getattr(cabo, "meubess_id", "") or ""),
                "nome": _tit(cabo), "tipo": "acessorio", "qtd": metros,
                "preco_unitario": round(_preco(cabo), 2),
                "preco_total": round(_preco(cabo) * metros, 2),
            })

    qty_mc4 = 1 + math.ceil(qty_modulos / 10) if qty_modulos > 0 else 0
    mc4s_v = [m for m in mc4s if _preco(m) > 0]
    if mc4s_v and qty_mc4 > 0:
        mc4 = min(mc4s_v, key=_preco)
        itens.append({
            "meubess_id": str(getattr(mc4, "meubess_id", "") or ""),
            "nome": _tit(mc4), "tipo": "acessorio", "qtd": qty_mc4,
            "preco_unitario": round(_preco(mc4), 2),
            "preco_total": round(_preco(mc4) * qty_mc4, 2),
        })
    return itens


def _structure_item(fixing_type: str | None, qty_modulos: int, estruturas: list) -> dict | None:
    """Escolhe a estrutura do tipo informado que minimiza custo total
    (preço × ceil(módulos / capacidade)) — evita usar uma estrutura de 180 módulos
    numa instalação residencial pequena."""
    if not fixing_type or qty_modulos == 0:
        return None
    candidatas = [
        e for e in estruturas
        if eff(e, "fixing_type") == fixing_type
        and (eff_int(e, "fixing_capacity") or 0) > 0
        and _preco(e) > 0
    ]
    if not candidatas:
        return None

    def custo(e):
        cap = eff_int(e, "fixing_capacity")
        return _preco(e) * math.ceil(qty_modulos / cap)

    melhor = min(candidatas, key=custo)
    cap = eff_int(melhor, "fixing_capacity")
    qty = math.ceil(qty_modulos / cap)
    return {
        "meubess_id": str(getattr(melhor, "meubess_id", "") or ""),
        "nome": _tit(melhor), "tipo": "acessorio", "qtd": qty,
        "preco_unitario": round(_preco(melhor), 2),
        "preco_total": round(_preco(melhor) * qty, 2),
    }


def pv_accessory_itens(
    qty_modulos: int,
    modulo: ModuloAttrs,
    fixing_type: str | None,
    cabos: list,
    mc4s: list,
    estruturas: list,
) -> list[dict]:
    """Retorna [módulo item, cabos×2, mc4, estrutura] para a montagem FV."""
    itens: list[dict] = [{
        "meubess_id": str(getattr(modulo.produto, "meubess_id", "") or ""),
        "nome": _tit(modulo.produto), "tipo": "modulo_fv", "qtd": qty_modulos,
        "potencia_wp": modulo.wp,
        "preco_unitario": round(modulo.preco, 2),
        "preco_total": round(modulo.preco * qty_modulos, 2),
    }]
    itens += _cabo_mc4_items(qty_modulos, cabos, mc4s)
    est = _structure_item(fixing_type, qty_modulos, estruturas)
    if est:
        itens.append(est)
    return itens


def _preco_itens(itens: list[dict]) -> float:
    return sum(i["preco_total"] for i in itens)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Seleção de inversor string (Caminho A)
# ─────────────────────────────────────────────────────────────────────────────

def _pick_string_inverter(
    kwp_pv: float,
    qty_modules: int,
    modulo: ModuloAttrs,
    inversores_string: list,
    conexoes: dict[str, str] | None,
):
    """(inversor, quantidade) escolhidos — critério compartilhado por
    _select_string_inverter_for (que monta o item) e pelo detalhamento do kit
    on-grid, para os dois nunca divergirem. Retorna None se nenhum serve.

    `conexoes` mapeia fase do inversor → tensões de conexão disponíveis na rede
    (ver CONEXOES_REDE em calculate/service.py). Uma rede trifásica 220/380
    aceita tanto um inversor trifásico em 380 V (entre fases) quanto
    monofásicos em 220 V (fase-neutro) — antes o filtro era um par
    (tensão, fase) único e descartava a segunda opção, que muitas vezes é a
    mais barata.
    """
    if kwp_pv <= 0 or qty_modules <= 0:
        return None

    alvo_ca_kw = kwp_pv / OVERSIZE_DC_AC
    candidatos = []

    for inv in inversores_string:
        inv_voltage = str(eff(inv, "voltage") or "")
        inv_phase = str(eff(inv, "phase") or "")
        if conexoes and inv_phase:
            tensoes_ok = conexoes.get(inv_phase)
            if not tensoes_ok:
                continue  # esse tipo de inversor não se liga nessa rede
            if inv_voltage and inv_voltage not in tensoes_ok:
                continue

        power_kw = eff_float(inv, "power")
        preco_un = _preco(inv)
        if not power_kw or power_kw <= 0 or preco_un <= 0:
            continue

        # determina quantidade mínima que cobre os módulos eletricamente E a potência CA
        qty = max(1, math.ceil(alvo_ca_kw / power_kw))
        while qty <= 8:
            if dc_capacity_modules(inv, qty, modulo) >= qty_modules:
                break
            qty += 1
        else:
            continue  # nem com 8 unidades cobre eletricamente

        total_preco = preco_un * qty
        candidatos.append((total_preco, inv, qty))

    if not candidatos:
        return None

    _, inv_best, qty_best = min(candidatos, key=lambda c: c[0])
    return inv_best, qty_best


def _select_string_inverter_for(
    kwp_pv: float,
    qty_modules: int,
    modulo: ModuloAttrs,
    inversores_string: list,
    conexoes: dict[str, str] | None,
) -> list[dict] | None:
    """Item do(s) inversor(es) string mais barato(s) que cobrem `kwp_pv` kWp,
    validando eletricamente (capacidade CC ≥ qty_modules) e usando oversizing
    DC/AC = 1.5 como alvo (mesma convenção da MeuBESS)."""
    if kwp_pv <= 0 or qty_modules <= 0:
        return []
    escolha = _pick_string_inverter(kwp_pv, qty_modules, modulo, inversores_string, conexoes)
    if escolha is None:
        return None
    inv_best, qty_best = escolha
    power_kw = eff_float(inv_best, "power") or 0.0
    item = {
        "meubess_id": str(getattr(inv_best, "meubess_id", "") or ""),
        "nome": _tit(inv_best), "tipo": "inversor_string", "qtd": qty_best,
        "preco_unitario": round(_preco(inv_best), 2),
        "preco_total": round(_preco(inv_best) * qty_best, 2),
        "potencia_inversao_kw": round(power_kw, 2),
    }
    return [item]


# ─────────────────────────────────────────────────────────────────────────────
# 6. Escalonamento do híbrido (Caminho B)
# ─────────────────────────────────────────────────────────────────────────────

def _scale_hybrid(
    base: KitBESS,
    qty_modulos_alvo: int,
    modulo: ModuloAttrs,
    inversores_hibridos: list,
    jbw_produtos: list | None = None,
) -> KitBESS | None:
    """Caminho B: aumenta potência do híbrido (mais unidades do mesmo modelo OU
    troca para outro modelo maior da mesma marca) até a entrada CC comportar todos os
    módulos, mantendo a mesma bateria/quantidade do kit base."""
    marca = str(eff(base.inversor, "marca") or "")
    ba, motivo_b = _attrs_bateria(base.bateria)
    if motivo_b:
        return None

    candidatos: list[KitBESS] = []

    # opção 1: mais unidades do MESMO modelo
    ia, motivo = _attrs_inversor(base.inversor)
    if not motivo:
        max_par = ia["max_paralelo"]
        for qtd_inv in range(base.qtd_inversores + 1, max_par + 1):
            if dc_capacity_modules(base.inversor, qtd_inv, modulo) >= qty_modulos_alvo:
                n_ent = ia["battery_inputs"] * qtd_inv
                cap = ba["max_paralelo"] * n_ent
                if base.qtd_baterias > cap:
                    continue  # baterias originais não cabem com esse inversor qtd
                kit = _montar_kit(
                    base.inversor, base.bateria, qtd_inv, base.qtd_baterias,
                    ia, ba, n_ent, list(base.alertas), _tit, jbw_produtos,
                )
                candidatos.append(kit)
                break  # menor qtd que já resolve

    # opção 2: outro modelo híbrido da mesma marca (1 unidade)
    for inv in inversores_hibridos:
        if str(eff(inv, "marca") or "") != marca:
            continue
        if inv is base.inversor:
            continue
        ok, _ = _compativel(inv, base.bateria)
        if not ok:
            continue
        ia2, motivo2 = _attrs_inversor(inv)
        if motivo2:
            continue
        if dc_capacity_modules(inv, 1, modulo) >= qty_modulos_alvo:
            n_ent = ia2["battery_inputs"]
            cap = ba["max_paralelo"] * n_ent
            if base.qtd_baterias > cap:
                continue
            kit = _montar_kit(
                inv, base.bateria, 1, base.qtd_baterias,
                ia2, ba, n_ent, list(base.alertas), _tit, jbw_produtos,
            )
            candidatos.append(kit)

    if not candidatos:
        return None
    return min(candidatos, key=lambda k: k.preco_total)


# ─────────────────────────────────────────────────────────────────────────────
# 7. Kit on-grid puro (sem armazenamento)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class OngridPVDetail:
    """O que foi de fato escolhido no kit on-grid — base para o solar_dimensionamento."""
    modulo: ModuloAttrs
    qty_modulos: int
    inversor: object
    qtd_inversores: int


def ongrid_string_layout(detalhe: OngridPVDetail) -> tuple[int, int, int] | None:
    """(n_serie, n_paralelo, mppt_qty) do kit on-grid.

    Deriva da mesma restrição usada em dc_capacity_modules para aceitar o
    inversor — série limitada pela tensão máxima, paralelo distribuído entre os
    MPPTs disponíveis. Retorna None se o inversor não expõe os dados.
    """
    voc_max = eff_float(detalhe.inversor, "voc_max_voltage")
    qty_mppt = eff_int(detalhe.inversor, "qty_mppt")
    if not voc_max or not qty_mppt or detalhe.modulo.voc_v <= 0:
        return None

    n_serie = math.floor(voc_max / detalhe.modulo.voc_v)
    if n_serie < 1:
        return None

    mppt_total = qty_mppt * max(1, detalhe.qtd_inversores)
    n_paralelo = math.ceil(detalhe.qty_modulos / (n_serie * mppt_total))
    return n_serie, max(1, n_paralelo), mppt_total


def build_ongrid_kit_detalhado(
    kwp_alvo: float,
    modulos: list,
    fixing_type: str | None,
    cabos: list,
    mc4s: list,
    estruturas: list,
    inversores_string: list,
    conexoes: dict[str, str] | None,
) -> tuple[list[dict] | None, OngridPVDetail | None]:
    """Kit puramente on-grid: módulos + inversor string + acessórios.

    Devolve (itens, detalhe). O detalhe carrega módulo/inversor escolhidos para
    que o chamador monte o dimensionamento FV sem repetir a seleção.
    """
    mod, qty = select_module(modulos, kwp_alvo)
    if mod is None:
        return None, None

    inv_itens = _select_string_inverter_for(kwp_alvo, qty, mod, inversores_string, conexoes)
    if inv_itens is None:
        return None, None

    escolha = _pick_string_inverter(kwp_alvo, qty, mod, inversores_string, conexoes)
    detalhe = (
        OngridPVDetail(modulo=mod, qty_modulos=qty, inversor=escolha[0], qtd_inversores=escolha[1])
        if escolha else None
    )

    itens = pv_accessory_itens(qty, mod, fixing_type, cabos, mc4s, estruturas)
    itens += inv_itens
    return itens, detalhe


def build_ongrid_kit(
    kwp_alvo: float,
    modulos: list,
    fixing_type: str | None,
    cabos: list,
    mc4s: list,
    estruturas: list,
    inversores_string: list,
    conexoes: dict[str, str] | None,
) -> list[dict] | None:
    """Só os itens do kit on-grid. Ver build_ongrid_kit_detalhado."""
    itens, _ = build_ongrid_kit_detalhado(
        kwp_alvo, modulos, fixing_type, cabos, mc4s, estruturas,
        inversores_string, conexoes,
    )
    return itens


# ─────────────────────────────────────────────────────────────────────────────
# 8. Opção combinada (PV + armazenamento) a partir de 1 KitBESS base
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CombinedOption:
    kit_storage: KitBESS
    pv_itens: list[dict]
    rotulo_caminho: str   # "dc" | "split" | "scaled"

    @property
    def preco_total(self) -> float:
        return self.kit_storage.preco_total + _preco_itens(self.pv_itens)

    def to_merged_kit(self) -> KitBESS:
        """Mescla itens FV na lista de itens do kit de armazenamento."""
        merged_itens = list(self.kit_storage.itens or []) + self.pv_itens
        return KitBESS(
            inversor=self.kit_storage.inversor,
            bateria=self.kit_storage.bateria,
            qtd_inversores=self.kit_storage.qtd_inversores,
            qtd_baterias=self.kit_storage.qtd_baterias,
            distribuicao_baterias=self.kit_storage.distribuicao_baterias,
            n_caixas_juncao=self.kit_storage.n_caixas_juncao,
            capacidade_total_kwh=self.kit_storage.capacidade_total_kwh,
            pico_entregavel_kw=self.kit_storage.pico_entregavel_kw,
            preco_total=round(self.preco_total, 2),
            alertas=list(self.kit_storage.alertas or []),
            itens=merged_itens,
        )


def _build_options_for_base(
    base: KitBESS,
    qty_modulos: int,
    modulo: ModuloAttrs,
    kwp_alvo: float,
    fixing_type: str | None,
    cabos: list,
    mc4s: list,
    estruturas: list,
    inversores_string: list,
    conexoes: dict[str, str] | None,
    inversores_hibridos: list,
    jbw_produtos: list | None = None,
) -> list[CombinedOption]:
    """Para um KitBESS base, retorna as opções de combinação PV ordenadas por preço."""
    pv_acc = pv_accessory_itens(qty_modulos, modulo, fixing_type, cabos, mc4s, estruturas)

    dc_qty = dc_capacity_modules(base.inversor, base.qtd_inversores, modulo)
    if dc_qty >= qty_modulos:
        return [CombinedOption(kit_storage=base, pv_itens=pv_acc, rotulo_caminho="dc")]

    opcoes: list[CombinedOption] = []

    # Caminho A: módulos excedentes vão para inversor string (AC-acoplado)
    modules_on_hybrid = dc_qty
    modules_remaining = qty_modulos - modules_on_hybrid
    kwp_remaining = modules_remaining * modulo.wp / 1000
    inv_string_itens = _select_string_inverter_for(
        kwp_remaining, modules_remaining, modulo, inversores_string, conexoes,
    )
    if inv_string_itens is not None:
        pv_split = pv_acc + inv_string_itens
        opcoes.append(CombinedOption(kit_storage=base, pv_itens=pv_split, rotulo_caminho="split"))

    # Caminho B: escala o inversor híbrido para absorver todos os módulos no DC
    kit_scaled = _scale_hybrid(base, qty_modulos, modulo, inversores_hibridos, jbw_produtos)
    if kit_scaled:
        opcoes.append(CombinedOption(kit_storage=kit_scaled, pv_itens=pv_acc, rotulo_caminho="scaled"))

    opcoes.sort(key=lambda o: o.preco_total)
    return opcoes


# ─────────────────────────────────────────────────────────────────────────────
# 9. Orquestrador principal — retorna sugerido + até 2 alternativas
# ─────────────────────────────────────────────────────────────────────────────

MAX_CANDIDATOS_ARMAZENAMENTO = 20


def build_combined_pv_storage(
    *,
    kits_storage: list[KitBESS],
    e_bat_kwh: float,
    kwp_alvo: float,
    modulos: list,
    fixing_type: str | None,
    cabos: list,
    mc4s: list,
    estruturas: list,
    inversores_string: list,
    inversores_hibridos: list,
    conexoes: dict[str, str] | None,
    jbw_produtos: list | None = None,
) -> tuple[CombinedOption | None, list[CombinedOption]]:
    """
    Dimensiona kit combinado FV + armazenamento. Retorna (sugerido, [alt1, alt2]).

    Lógica de seleção:
    - Avalia os N pares de armazenamento mais baratos (não só o mais barato isolado,
      kits_storage[0]) porque o par mais barato PARA BACKUP pode ter um híbrido cuja
      janela de tensão/MPPT não aceita os módulos FV escolhidos. Nesse caso o
      "caminho split" força um inversor string quase do tamanho do sistema inteiro
      (ex.: híbrido de 6kW que não recebe nenhum módulo + string de ~6kW cobrindo
      100% do FV, para um alvo de 8,5 kWp — dois inversores redundantes). Ao
      considerar mais candidatos, o sugerido passa a ser a combinação
      (armazenamento × caminho FV) de MENOR CUSTO TOTAL dentre todos, o que
      naturalmente prefere um híbrido cuja entrada CC realmente aproveita parte do
      FV (reduzindo — ou eliminando — o inversor string) sempre que isso for mais
      barato do que pagar por dois inversores de porte pleno.
    - sugerido = combinação mais barata dentre os N candidatos avaliados.
    - alt1 = a próxima opção mais barata que usa um caminho OU par de armazenamento
      diferente do sugerido (evita repetir a mesma composição).
    - alt2 = opção mais econômica considerando REDUÇÃO de cobertura de energia
      (economic_undershoot_kit sobre TODOS os pares de armazenamento, mesmo kWp
      alvo de FV) — independente de qual par foi escolhido como sugerido.
    """
    if not kits_storage:
        return None, []

    mod, qty_modulos = select_module(modulos, kwp_alvo)
    if mod is None:
        return None, []

    candidatos = kits_storage[:MAX_CANDIDATOS_ARMAZENAMENTO]
    todas_opcoes: list[CombinedOption] = []
    for base in candidatos:
        todas_opcoes += _build_options_for_base(
            base, qty_modulos, mod, kwp_alvo, fixing_type,
            cabos, mc4s, estruturas, inversores_string, conexoes, inversores_hibridos, jbw_produtos,
        )
    if not todas_opcoes:
        return None, []

    todas_opcoes.sort(key=lambda o: o.preco_total)
    sugerido = todas_opcoes[0]

    alternativas: list[CombinedOption] = []
    for opt in todas_opcoes[1:]:
        composicao_diferente = (
            opt.rotulo_caminho != sugerido.rotulo_caminho
            or opt.kit_storage is not sugerido.kit_storage
        )
        if composicao_diferente:
            alternativas.append(opt)
            break

    # alt2 — econômica: reduz baterias, mantém mesmo kWp FV
    eco_base = economic_undershoot_kit(kits_storage, e_bat_kwh, jbw_produtos)
    if eco_base:
        eco_opcoes = _build_options_for_base(
            eco_base, qty_modulos, mod, kwp_alvo, fixing_type,
            cabos, mc4s, estruturas, inversores_string, conexoes, inversores_hibridos, jbw_produtos,
        )
        if eco_opcoes:
            alternativas.append(eco_opcoes[0])

    return sugerido, alternativas[:2]
