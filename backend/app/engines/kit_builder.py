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


def _serve_tensoes(inv, tensoes_carga: set[str]) -> tuple[bool, str | None]:
    """R8: a saída EPS do inversor atende todas as tensões de carga?"""
    eps = _parse_eps_voltages(eff(inv, "eps_output_voltage"))
    split = bool(eff_bool(inv, "split_phase"))
    if not eps:
        return False, "tensão de saída EPS não cadastrada"
    servidas = set(eps)
    if split:
        servidas |= {"127", "220"}  # split-phase atende 127 e 220 mono
    faltando = {t for t in tensoes_carga if t not in servidas}
    if faltando:
        return False, f"saída EPS não atende carga(s) {sorted(faltando)} V"
    return True, None


def _inversor_e_trifasico(inv) -> bool:
    eps = _parse_eps_voltages(eff(inv, "eps_output_voltage"))
    if "380" in eps:
        return True
    return (eff(inv, "phase") or "").strip().lower() == "trifasico"


def _alertas_rede(inv, fase_instalacao: str | None, padrao_entrada: str | None) -> list[str]:
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
    if padrao_entrada == "tri_127_220" and inv_tri and "380" in eps:
        alertas.append(
            "Rede trifásica 127/220 V com inversor 380/220 V — requer autotransformador "
            "de potência adequada."
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

def _attrs_inversor(inv) -> tuple[dict, str | None]:
    """Lê os atributos do inversor; retorna (attrs, motivo_se_incompleto)."""
    a = {
        "peak_power_kw":   eff_float(inv, "peak_power_kw"),
        "eps_nominal_kw":  eff_float(inv, "max_eps_power") or eff_float(inv, "max_output_power") or eff_float(inv, "power"),
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

    for inv in inversores:
        ia, motivo = _attrs_inversor(inv)
        if motivo:
            skipped.append(SkipReason(_id(inv), _tit(inv), motivo))
            continue

        # R8 — tensão de saída EPS × cargas (quando informado)
        if tensoes_carga:
            ok, why = _serve_tensoes(inv, tensoes_carga)
            if not ok:
                skipped.append(SkipReason(_id(inv), _tit(inv), why))
                continue

        # R7 — alertas de compatibilidade com a rede da unidade (não bloqueia)
        alertas_rede = _alertas_rede(inv, fase_instalacao, padrao_entrada)

        # R3/R4 — potência: escala nº de inversores por pico e nominal
        qtd_inv = max(
            math.ceil(pp_kva / ia["peak_power_kw"]),
            math.ceil(pn_kva / ia["eps_nominal_kw"]),
            1,
        )
        if qtd_inv > ia["max_paralelo"]:
            skipped.append(SkipReason(_id(inv), _tit(inv),
                f"potência exige {qtd_inv} inversores (máx paralelo {ia['max_paralelo']})"))
            continue

        n_entradas = ia["battery_inputs"] * qtd_inv

        for bat in baterias:
            ba, motivo_b = _attrs_bateria(bat)
            if motivo_b:
                skipped.append(SkipReason(_id(bat), _tit(bat), motivo_b))
                continue
            if require_same_brand and (eff(inv, "marca") or "") != (eff(bat, "marca") or ""):
                continue
            ok, why = _compativel(inv, bat)
            if not ok:
                continue  # incompatível: não é erro de cadastro, só não casa

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
                skipped.append(SkipReason(_id(inv), _tit(inv),
                    f"nem o banco cheio entrega o pico {pp_kva:.1f} kVA (com {_tit(bat)})"))
                continue

            n = max(n_energia, n_pot)
            if n > cap_bat:
                skipped.append(SkipReason(_id(inv), _tit(inv),
                    f"energia exige {n} baterias (máx {cap_bat} neste arranjo)"))
                continue

            alertas: list[str] = list(alertas_rede)
            # R6 — carga mono em inversor tri (advisory; precisa da maior carga mono)
            if fase_instalacao == "trifasico" and tensoes_carga:
                alertas.append("verifique cargas monofásicas ≤ 1/3 da potência (alerta)")

            kits.append(_montar_kit(inv, bat, qtd_inv, n, ia, ba, n_entradas, alertas, _tit, jbw_produtos))

    kits.sort(key=lambda k: k.preco_total)
    return kits, skipped
