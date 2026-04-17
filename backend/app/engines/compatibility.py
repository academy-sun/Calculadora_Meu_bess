import math
from dataclasses import dataclass, field
from typing import Optional

from app.engines.schemas import ProductBESSRead


@dataclass
class KitBESS:
    bateria: ProductBESSRead
    inversor: ProductBESSRead
    qtd_baterias_serie: int
    qtd_strings_paralelo: int
    qtd_baterias_total: int
    qtd_inversores: int                        # NEW
    capacidade_total_kwh: float
    potencia_total_kw: float
    preco_total: float
    economia_mensal: Optional[float] = None    # NEW — usado na arbitragem
    payback_anos: Optional[float] = None       # NEW — usado na arbitragem


def find_compatible_kits(
    baterias: list[ProductBESSRead],
    inversores: list[ProductBESSRead],
    capacidade_necessaria_kwh: float,
    potencia_necessaria_kw: float,
) -> list[KitBESS]:
    """
    Para cada par (bateria, inversor) da MESMA marca:
    1. Calcula configuração de strings por parâmetros elétricos
    2. Verifica se atende capacidade e potência
    3. Retorna lista de kits válidos ordenados por menor preço total
    """
    kits: list[KitBESS] = []

    for bat in baterias:
        for inv in inversores:
            if bat.marca != inv.marca:
                continue

            required = [
                bat.tensao_nominal_v, bat.corrente_max_descarga_a,
                bat.capacidade_kwh, bat.dod_percent,
                inv.tensao_min_dc_v, inv.tensao_max_dc_v,
                inv.corrente_max_dc_a, inv.potencia_continua_kw,
            ]
            if not all(v is not None for v in required):
                continue

            serie_min = math.ceil(inv.tensao_min_dc_v / bat.tensao_nominal_v)
            serie_max = math.floor(inv.tensao_max_dc_v / bat.tensao_nominal_v)

            if serie_min > serie_max or serie_min < 1:
                continue

            qtd_serie = serie_min
            paralelo_max = math.floor(inv.corrente_max_dc_a / bat.corrente_max_descarga_a)
            if paralelo_max < 1:
                continue

            capacidade_por_string_kwh = (
                bat.capacidade_kwh * (bat.dod_percent / 100.0) * qtd_serie
            )
            strings_necessarias = math.ceil(
                capacidade_necessaria_kwh / capacidade_por_string_kwh
            )

            if strings_necessarias > paralelo_max:
                continue

            qtd_baterias_total = qtd_serie * strings_necessarias

            # Respeitar limite de catálogo: max_baterias por inversor
            max_bat = getattr(inv, 'max_baterias', None)
            if max_bat is not None and max_bat > 0:
                n_inv = math.ceil(qtd_baterias_total / max_bat)
            else:
                n_inv = 1   # sem restrição de catálogo: 1 inversor

            if n_inv > 4:
                continue    # precisaria de mais de 4 inversores — inviável

            capacidade_total_kwh = capacidade_por_string_kwh * strings_necessarias
            potencia_total_kw = inv.potencia_continua_kw

            if potencia_total_kw < potencia_necessaria_kw:
                continue

            preco_total = bat.preco * qtd_baterias_total + inv.preco * n_inv

            kits.append(KitBESS(
                bateria=bat,
                inversor=inv,
                qtd_baterias_serie=qtd_serie,
                qtd_strings_paralelo=strings_necessarias,
                qtd_baterias_total=qtd_baterias_total,
                qtd_inversores=n_inv,
                capacidade_total_kwh=round(capacidade_total_kwh, 2),
                potencia_total_kw=round(potencia_total_kw, 2),
                preco_total=round(preco_total, 2),
            ))

    kits.sort(key=lambda k: k.preco_total)
    return kits


def find_arbitrage_kits(
    baterias: list,
    inversores: list,
    data,           # ArbitrageInput
) -> list[KitBESS]:
    """
    Para cada par (bateria, inversor) de mesma marca, itera de 1 até
    max_baterias × 4 unidades (até 4 inversores em paralelo) e calcula
    economia + payback para cada quantidade.
    Retorna todos os kits válidos (economia > 0) ordenados por payback crescente.
    """
    from app.engines.bess import calculate_arbitrage_economy

    kits: list[KitBESS] = []

    for bat in baterias:
        if not bat.capacidade_kwh or not bat.preco:
            continue

        for inv in inversores:
            if bat.marca != inv.marca:
                continue
            if not inv.preco:
                continue

            max_bat_inv = getattr(inv, 'max_baterias', None) or 8  # default conservador
            max_total = max_bat_inv * 4  # até 4 inversores

            for n_baterias in range(1, max_total + 1):
                n_inv = math.ceil(n_baterias / max_bat_inv)
                if n_inv > 4:
                    break

                eco = calculate_arbitrage_economy(data, n_baterias, float(bat.capacidade_kwh))

                if eco.economia_total_mensal <= 0:
                    continue

                custo_kit = float(bat.preco) * n_baterias + float(inv.preco) * n_inv
                payback_anos = custo_kit / (eco.economia_total_mensal * 12)
                cap_total = n_baterias * float(bat.capacidade_kwh) * (data.dod_percent / 100.0)
                pot_total = (float(inv.potencia_continua_kw) * n_inv
                             if inv.potencia_continua_kw else 0.0)

                kits.append(KitBESS(
                    bateria=bat,
                    inversor=inv,
                    qtd_baterias_serie=1,
                    qtd_strings_paralelo=n_baterias,
                    qtd_baterias_total=n_baterias,
                    qtd_inversores=n_inv,
                    capacidade_total_kwh=round(cap_total, 2),
                    potencia_total_kw=round(pot_total, 2),
                    preco_total=round(custo_kit, 2),
                    economia_mensal=eco.economia_total_mensal,
                    payback_anos=round(payback_anos, 2),
                ))

    kits.sort(key=lambda k: k.payback_anos if k.payback_anos is not None else float('inf'))
    return kits
