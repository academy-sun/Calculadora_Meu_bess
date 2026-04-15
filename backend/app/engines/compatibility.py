import math
from dataclasses import dataclass

from app.engines.schemas import ProductBESSRead


@dataclass
class KitBESS:
    bateria: ProductBESSRead
    inversor: ProductBESSRead
    qtd_baterias_serie: int
    qtd_strings_paralelo: int
    qtd_baterias_total: int
    capacidade_total_kwh: float
    potencia_total_kw: float
    preco_total: float


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
            capacidade_total_kwh = capacidade_por_string_kwh * strings_necessarias
            potencia_total_kw = inv.potencia_continua_kw

            if potencia_total_kw < potencia_necessaria_kw:
                continue

            preco_total = bat.preco * qtd_baterias_total + inv.preco

            kits.append(KitBESS(
                bateria=bat,
                inversor=inv,
                qtd_baterias_serie=qtd_serie,
                qtd_strings_paralelo=strings_necessarias,
                qtd_baterias_total=qtd_baterias_total,
                capacidade_total_kwh=round(capacidade_total_kwh, 2),
                potencia_total_kw=round(potencia_total_kw, 2),
                preco_total=round(preco_total, 2),
            ))

    kits.sort(key=lambda k: k.preco_total)
    return kits
