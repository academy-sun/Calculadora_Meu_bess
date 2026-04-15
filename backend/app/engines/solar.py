import math

from app.engines.schemas import SolarInput, SolarResult

EFICIENCIA_SISTEMA = 0.80
POTENCIA_MODULO_WP = 550.0
AREA_MODULO_M2 = 2.2


def calculate_solar(data: SolarInput) -> SolarResult:
    """
    Dimensiona sistema FV com base no consumo mensal e irradiação local.
    """
    dias_mes = 30
    geracao_diaria_necessaria_kwh = data.consumo_medio_mensal_kwh / dias_mes
    potencia_pico_kwp = geracao_diaria_necessaria_kwh / (
        data.irradiacao_kwh_m2_dia * EFICIENCIA_SISTEMA
    )

    modulos_por_potencia = math.ceil(
        (potencia_pico_kwp * 1000) / POTENCIA_MODULO_WP
    )
    modulos_por_area = math.floor(data.area_disponivel_m2 / AREA_MODULO_M2)
    quantidade_modulos = min(modulos_por_potencia, modulos_por_area)
    potencia_pico_kwp_real = (quantidade_modulos * POTENCIA_MODULO_WP) / 1000

    geracao_anual_kwh = (
        potencia_pico_kwp_real
        * data.irradiacao_kwh_m2_dia
        * 365
        * EFICIENCIA_SISTEMA
    )

    potencia_inversor_kw = round(potencia_pico_kwp_real * 0.9, 1)

    return SolarResult(
        potencia_pico_kwp=round(potencia_pico_kwp_real, 2),
        quantidade_modulos=quantidade_modulos,
        potencia_inversor_kw=potencia_inversor_kw,
        geracao_anual_estimada_kwh=round(geracao_anual_kwh, 0),
    )
