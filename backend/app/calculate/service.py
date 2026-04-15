from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.calculate.schemas import CalculateRequest, CalculateResponse, KitInfo, LoadItem
from app.catalog.service import list_bess
from app.engines.bess import calculate_backup, calculate_peak_shaving, calculate_arbitrage
from app.engines.compatibility import find_compatible_kits
from app.engines.schemas import (
    BackupInput, PeakShavingInput, ArbitrageInput, SolarInput,
    BackupResult, PeakShavingResult, ArbitrageResult, SolarResult,
)
from app.projects.models import Project
from app.projects.service import create_project, mark_project_done, mark_project_error


def _build_load_curve(cargas: list[LoadItem]) -> list[float]:
    """Gera curva de carga sintética (24 pontos) a partir de cargas padrão."""
    curva = [0.0] * 24
    for carga in cargas:
        potencia_total_kw = (carga.potencia_w * carga.quantidade) / 1000.0
        horas_uso = min(int(carga.horas_uso_dia), 24)
        for h in range(horas_uso):
            curva[h] += potencia_total_kw
    return curva


def _kits_to_response(kits) -> tuple[KitInfo | None, list[KitInfo]]:
    if not kits:
        return None, []
    kit_info_list = [
        KitInfo(
            marca=k.bateria.marca,
            bateria_modelo=k.bateria.modelo,
            inversor_modelo=k.inversor.modelo,
            qtd_baterias=k.qtd_baterias_total,
            capacidade_total_kwh=k.capacidade_total_kwh,
            potencia_total_kw=k.potencia_total_kw,
            preco_total=k.preco_total,
        )
        for k in kits
    ]
    return kit_info_list[0], kit_info_list[1:]


async def run_calculation(db: AsyncSession, req: CalculateRequest) -> CalculateResponse:
    solicitado_em = req.origem_info.solicitado_em

    project = await create_project(db, {
        "tipo_calculo": req.tipo_calculo,
        "estado": "calculando",
        "parametros": req.model_dump(exclude={"origem_info"}),
        "origem": req.origem_info.origem,
        "negocio_id": req.origem_info.negocio_id,
        "negocio_nome": req.origem_info.negocio_nome,
        "solicitante_id": req.origem_info.solicitante_id,
        "solicitante_nome": req.origem_info.solicitante_nome,
        "solicitado_em": solicitado_em,
    })

    try:
        if req.curva_carga_kw:
            curva = req.curva_carga_kw
        elif req.cargas:
            curva = _build_load_curve(req.cargas)
        else:
            curva = []

        todos_bess = await list_bess(db, disponivel_only=True)
        baterias = [p for p in todos_bess if p.tipo == "bateria"]
        inversores = [p for p in todos_bess if p.tipo == "inversor_hibrido"]

        capacidade_kwh = 0.0
        potencia_kw = 0.0
        economia_mensal = None
        economia_anual = None

        if req.tipo_calculo == "backup":
            dod = baterias[0].dod_percent if baterias else 90.0
            result: BackupResult = calculate_backup(
                BackupInput(
                    potencia_critica_kw=req.potencia_critica_kw,
                    autonomia_horas=req.autonomia_horas,
                    tensao_instalacao_v=req.tensao_instalacao_v,
                ),
                dod_percent=dod,
            )
            capacidade_kwh = result.capacidade_necessaria_kwh
            potencia_kw = result.potencia_necessaria_kw

        elif req.tipo_calculo == "peak_shaving":
            result: PeakShavingResult = calculate_peak_shaving(PeakShavingInput(
                curva_carga_kw=curva,
                demanda_alvo_kw=req.demanda_alvo_kw,
                tarifa_demanda_rs_kw=req.tarifa_demanda_rs_kw,
            ))
            capacidade_kwh = result.capacidade_necessaria_kwh
            potencia_kw = result.potencia_necessaria_kw
            economia_mensal = result.economia_mensal_estimada_rs

        elif req.tipo_calculo == "arbitragem":
            result: ArbitrageResult = calculate_arbitrage(ArbitrageInput(
                curva_carga_kw=curva,
                horario_ponta_inicio=req.horario_ponta_inicio,
                horario_ponta_fim=req.horario_ponta_fim,
                tarifa_ponta_rs_kwh=req.tarifa_ponta_rs_kwh,
                tarifa_fora_ponta_rs_kwh=req.tarifa_fora_ponta_rs_kwh,
            ))
            capacidade_kwh = result.capacidade_otima_kwh
            potencia_kw = capacidade_kwh / 4
            economia_anual = result.economia_anual_estimada_rs

        elif req.tipo_calculo in ("solar", "solar_storage"):
            from app.engines.solar import calculate_solar
            solar_result: SolarResult = calculate_solar(SolarInput(
                consumo_medio_mensal_kwh=sum(curva) / (len(curva) / 24) if curva else 0,
                irradiacao_kwh_m2_dia=req.irradiacao_kwh_m2_dia,
                area_disponivel_m2=req.area_disponivel_m2,
            ))
            if req.tipo_calculo == "solar_storage":
                geracao_diaria = solar_result.geracao_anual_estimada_kwh / 365
                capacidade_kwh = round(geracao_diaria * 0.30, 2)
                potencia_kw = solar_result.potencia_inversor_kw
            else:
                capacidade_kwh = solar_result.potencia_pico_kwp
                potencia_kw = solar_result.potencia_inversor_kw
                baterias = []
                inversores = []

        kits = find_compatible_kits(
            baterias=baterias,
            inversores=inversores,
            capacidade_necessaria_kwh=capacidade_kwh,
            potencia_necessaria_kw=potencia_kw,
        )

        kit_selecionado, alternativas = _kits_to_response(kits)

        if kit_selecionado:
            if economia_mensal:
                payback = kit_selecionado.preco_total / economia_mensal
            elif economia_anual:
                payback = (kit_selecionado.preco_total / economia_anual) * 12
            else:
                payback = None
        else:
            payback = None

        payback_meses = round(payback, 1) if payback else None
        calculado_em = datetime.now(timezone.utc)

        # Atualizar parâmetros com os RESULTADOS para persistência e exibição no front
        results_data = {
            "capacidade_kwh": capacidade_kwh,
            "potencia_kw": potencia_kw,
            "payback_meses": payback_meses,
            "kit_selecionado": kit_selecionado.model_dump() if kit_selecionado else None,
            "alternativas": [k.model_dump() for k in alternativas],
            "economia_mensal_rs": economia_mensal,
            "economia_anual_rs": economia_anual,
        }
        
        # Merge results into parameters
        current_params = project.parametros or {}
        project.parametros = {**current_params, **results_data}
        
        await mark_project_done(db, project, calculado_em)

        # Integração com Ploomes (Sync Automático)
        if req.origem_info.origem == "ploomes" and req.origem_info.negocio_id:
            from app.shared.ploomes import create_ploomes_interaction
            
            # Montar mensagem de resumo
            resumo = (
                f"📊 Dimensionamento BESS concluído ({req.tipo_calculo.upper()})\n"
                f"- Capacidade: {capacidade_kwh} kWh\n"
                f"- Potência: {potencia_kw} kW\n"
            )
            if kit_selecionado:
                resumo += f"- Kit Sugerido: {kit_selecionado.marca} {kit_selecionado.bateria_modelo}\n"
                resumo += f"- Investimento: R$ {kit_selecionado.preco_total:,.2f}\n"
            
            if payback_meses:
                resumo += f"- Payback estimado: {payback_meses} meses\n"
            
            resumo += f"\n👉 Ver detalhes: https://calculadora-meu-bess.vercel.app/projects/{project.id}"
            
            # Executar em background (não travar a resposta da API)
            import asyncio
            asyncio.create_task(create_ploomes_interaction(req.origem_info.negocio_id, resumo))

        return CalculateResponse(
            projeto_id=str(project.id),
            tipo_calculo=req.tipo_calculo,
            origem=req.origem_info.origem,
            negocio_id=req.origem_info.negocio_id,
            solicitado_em=solicitado_em,
            calculado_em=calculado_em,
            capacidade_kwh=capacidade_kwh,
            potencia_kw=potencia_kw,
            kit_selecionado=kit_selecionado,
            economia_mensal_rs=economia_mensal,
            economia_anual_rs=economia_anual,
            payback_meses=payback_meses,
            alternativas=alternativas,
        )

    except Exception as e:
        await mark_project_error(db, project)
        raise e
