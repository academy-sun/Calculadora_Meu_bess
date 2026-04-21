import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class KitBESS:
    bateria: object       # ProductBESSRead
    inversor: object      # ProductBESSRead
    qtd_baterias: int
    qtd_inversores: int
    capacidade_total_kwh: float
    potencia_total_kw: float
    preco_total: float
    economia_mensal: Optional[float] = None
    payback_anos: Optional[float] = None


def find_compatible_kits(
    baterias: list,
    inversores: list,
    total_pp_kva: float,
    total_e_eps_kwh: float,
    tipo_instalacao: str,          # "monofasico" | "trifasico"
) -> list:
    """
    For each (bateria, inversor) pair of the same brand:
    1. Filter by fase == tipo_instalacao
    2. Filter by pot_ca_max_eps_kva >= total_pp_kva
    3. Calculate battery qty = ceil(E_EPS / (cap × DoD/100))
    4. Sort by total price ascending.
    """
    kits = []

    for bat in baterias:
        if not bat.capacidade_kwh or not bat.dod_percent or not bat.preco:
            continue
        usable_kwh = float(bat.capacidade_kwh) * (float(bat.dod_percent) / 100.0)
        if usable_kwh <= 0:
            continue
        qtd_baterias = math.ceil(total_e_eps_kwh / usable_kwh)

        for inv in inversores:
            if bat.marca != inv.marca:
                continue

            inv_fase = getattr(inv, 'fase', None)
            if inv_fase and inv_fase != tipo_instalacao:
                continue

            eps_kva = getattr(inv, 'pot_ca_max_eps_kva', None)
            if eps_kva is not None and float(eps_kva) < total_pp_kva:
                continue

            pot_kw = float(inv.potencia_continua_kw) if inv.potencia_continua_kw else 0.0
            preco_total = float(bat.preco) * qtd_baterias + float(inv.preco)

            kits.append(KitBESS(
                bateria=bat,
                inversor=inv,
                qtd_baterias=qtd_baterias,
                qtd_inversores=1,
                capacidade_total_kwh=round(usable_kwh * qtd_baterias, 2),
                potencia_total_kw=round(pot_kw, 2),
                preco_total=round(preco_total, 2),
            ))

    kits.sort(key=lambda k: k.preco_total)
    return kits
