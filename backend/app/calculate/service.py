from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.calculate.schemas import (
    BackupLoadRow, BackupRowResult,
    CalculateRequest, CalculateResponse, KitInfo, LoadItem,
)
from app.catalog.service import list_bess, get_bess_comercial
from app.engines.bess import calculate_backup, calculate_peak_shaving, calculate_arbitrage_v2
from app.engines.compatibility import find_compatible_kits
from app.engines.schemas import (
    BackupInput, LoadRow,
    ArbitrageInputV2,
    PeakShavingInput, SolarInput,
    PeakShavingResult, SolarResult,
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
            qtd_baterias=k.qtd_baterias,
            qtd_inversores=k.qtd_inversores,
            capacidade_total_kwh=k.capacidade_total_kwh,
            potencia_total_kw=k.potencia_total_kw,
            preco_total=k.preco_total,
            economia_mensal_rs=k.economia_mensal,
            payback_anos=k.payback_anos,
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
        kit_selecionado = None
        alternativas = []
        payback_meses = None

        # Backup-specific extras
        backup_rows = None
        backup_result = None

        # Arbitragem-specific extras
        arb_result = None

        if req.tipo_calculo == "backup":
            if not req.cargas_backup:
                raise ValueError("cargas_backup é obrigatório para backup")

            cargas_engine = [
                LoadRow(
                    qtd=c.qtd,
                    pnom_w=c.pnom_w,
                    fp=c.fp,
                    fd=c.fd,
                    ip_in=c.ip_in,
                    tdia_h=c.tdia_h,
                )
                for c in req.cargas_backup
            ]

            backup_result = calculate_backup(BackupInput(
                cargas=cargas_engine,
                tipo_instalacao=req.tipo_instalacao or "monofasico",
                dod_percent=req.dod_percent or 90.0,
                autonomia_h=req.autonomia_horas or 4.0,
                eficiencia_roundtrip=req.eficiencia_roundtrip or 90.0,
            ))

            capacidade_kwh = backup_result.total_e_eps
            potencia_kw = backup_result.total_pp

            kits = find_compatible_kits(
                baterias=baterias,
                inversores=inversores,
                total_pp_kva=backup_result.total_pp,
                total_e_eps_kwh=backup_result.total_e_eps,
                tipo_instalacao=req.tipo_instalacao or "monofasico",
            )
            kit_selecionado, alternativas = _kits_to_response(kits)

            # Build per-row results for frontend table
            backup_rows = [
                BackupRowResult(
                    nome=req.cargas_backup[i].nome,
                    pn_kva=r.pn_kva,
                    dmn_kva=r.dmn_kva,
                    pp_kva=r.pp_kva,
                    dmp_kva=r.dmp_kva,
                    e_eps_kwh=r.e_eps_kwh,
                )
                for i, r in enumerate(backup_result.rows)
            ]

            if kit_selecionado:
                payback_meses = None  # payback for backup not calculated here

        elif req.tipo_calculo == "peak_shaving":
            result: PeakShavingResult = calculate_peak_shaving(PeakShavingInput(
                curva_carga_kw=curva,
                demanda_alvo_kw=req.demanda_alvo_kw,
                tarifa_demanda_rs_kw=req.tarifa_demanda_rs_kw,
            ))
            capacidade_kwh = result.capacidade_necessaria_kwh
            potencia_kw = result.potencia_necessaria_kw
            economia_mensal = result.economia_mensal_estimada_rs

            kits = find_compatible_kits(
                baterias=baterias,
                inversores=inversores,
                total_pp_kva=potencia_kw,
                total_e_eps_kwh=capacidade_kwh,
                tipo_instalacao="monofasico",
            )
            kit_selecionado, alternativas = _kits_to_response(kits)

            if kit_selecionado and economia_mensal:
                payback = kit_selecionado.preco_total / economia_mensal
                payback_meses = round(payback, 1)

        elif req.tipo_calculo == "arbitragem":
            if not req.consumo_ponta_kwh or not req.demanda_ponta_kw:
                raise ValueError("consumo_ponta_kwh e demanda_ponta_kw são obrigatórios")

            bess_com = await get_bess_comercial(db)
            if not bess_com:
                raise ValueError("Produto BESS Comercial não encontrado no catálogo")

            arb_result = calculate_arbitrage_v2(ArbitrageInputV2(
                consumo_ponta_kwh=req.consumo_ponta_kwh,
                demanda_ponta_kw=req.demanda_ponta_kw,
                tarifa_ponta_kwh=req.tarifa_ponta_rs_kwh or 0.0,
                tarifa_fora_ponta_kwh=req.tarifa_fora_ponta_rs_kwh or 0.0,
                bess_capacidade_kwh=float(bess_com.capacidade_kwh),
                bess_dod=float(bess_com.dod_percent),
                bess_preco=float(bess_com.preco),
            ))

            capacidade_kwh = round(
                arb_result.qty_bess * float(bess_com.capacidade_kwh) * (float(bess_com.dod_percent) / 100.0), 2
            )
            potencia_kw = 0.0
            economia_mensal = arb_result.economia_mensal
            payback_meses = arb_result.payback_meses
            # No hardware kit for arbitragem — custo is in arb_result.custo_total
            kit_selecionado = None
            alternativas = []

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
                total_pp_kva=potencia_kw,
                total_e_eps_kwh=capacidade_kwh,
                tipo_instalacao="monofasico",
            )
            kit_selecionado, alternativas = _kits_to_response(kits)

        calculado_em = datetime.now(timezone.utc)

        results_data = {
            "capacidade_kwh": capacidade_kwh,
            "potencia_kw": potencia_kw,
            "payback_meses": payback_meses,
            "kit_selecionado": kit_selecionado.model_dump() if kit_selecionado else None,
            "alternativas": [k.model_dump() for k in alternativas],
            "economia_mensal_rs": economia_mensal,
            "economia_anual_rs": economia_anual,
        }

        current_params = project.parametros or {}
        project.parametros = {**current_params, **results_data}

        await mark_project_done(db, project, calculado_em)

        # Integração com Ploomes (Sync Automático)
        if req.origem_info.origem == "ploomes" and req.origem_info.negocio_id:
            from app.shared.ploomes import create_ploomes_interaction

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
            backup_rows=backup_rows,
            total_pn_kva=backup_result.total_pn if backup_result else None,
            total_dmn_kva=backup_result.total_dmn if backup_result else None,
            total_pp_kva=backup_result.total_pp if backup_result else None,
            total_dmp_kva=backup_result.total_dmp if backup_result else None,
            qty_bess=arb_result.qty_bess if arb_result else None,
            qty_consumo=arb_result.qty_consumo if arb_result else None,
            qty_potencia=arb_result.qty_potencia if arb_result else None,
            avg_consumo_ponta=arb_result.avg_consumo_ponta if arb_result else None,
            max_demanda_ponta=arb_result.max_demanda_ponta if arb_result else None,
            kit_selecionado=kit_selecionado,
            economia_mensal_rs=economia_mensal,
            economia_anual_rs=economia_anual,
            payback_meses=payback_meses,
            alternativas=alternativas,
        )

    except Exception as e:
        await mark_project_error(db, project)
        raise e
