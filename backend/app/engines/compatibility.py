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


def _build_kits(
    baterias: list,
    inversores: list,
    total_e_eps_kwh: float,
    require_same_brand: bool = True,
    require_fase: str | None = None,
    min_eps_kva: float | None = None,
) -> list:
    """Inner helper: build KitBESS objects for given constraints."""
    kits = []
    for bat in baterias:
        if not bat.capacidade_kwh or not bat.preco:
            continue
        # dod_percent NULL means capacidade_kwh already represents usable energy (convention = 100%)
        dod = float(bat.dod_percent) if bat.dod_percent else 100.0
        usable_kwh = float(bat.capacidade_kwh) * (dod / 100.0)
        if usable_kwh <= 0:
            continue
        qtd_baterias = max(1, math.ceil(total_e_eps_kwh / usable_kwh))

        for inv in inversores:
            if require_same_brand and bat.marca != inv.marca:
                continue

            inv_fase = getattr(inv, 'fase', None)
            if require_fase and inv_fase and inv_fase != require_fase:
                continue

            if min_eps_kva is not None:
                eps_kva = getattr(inv, 'pot_ca_max_eps_kva', None)
                if eps_kva is not None and float(eps_kva) < min_eps_kva:
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


def find_compatible_kits(
    baterias: list,
    inversores: list,
    total_pp_kva: float,
    total_e_eps_kwh: float,
    tipo_instalacao: str,          # "monofasico" | "trifasico"
) -> list:
    """
    Return kits sorted by price. Tries progressively relaxed constraints so
    that at least the smallest available kit is always returned:

    Pass 1 – same brand, same phase, eps_kva >= total_pp_kva  (ideal)
    Pass 2 – same brand, same phase, any eps_kva              (relax power)
    Pass 3 – same brand, any phase, any eps_kva               (relax phase)
    Pass 4 – any brand, any phase, any eps_kva                (last resort)
    """
    passes = [
        dict(require_same_brand=True,  require_fase=tipo_instalacao, min_eps_kva=total_pp_kva),
        dict(require_same_brand=True,  require_fase=tipo_instalacao, min_eps_kva=None),
        dict(require_same_brand=True,  require_fase=None,            min_eps_kva=None),
        dict(require_same_brand=False, require_fase=None,            min_eps_kva=None),
    ]

    for kwargs in passes:
        kits = _build_kits(baterias, inversores, total_e_eps_kwh, **kwargs)
        if kits:
            return kits

    return []
