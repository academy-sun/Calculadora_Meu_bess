from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.calculate.schemas import (
    BackupLoadRow, BackupRowResult,
    CalculateRequest, CalculateResponse, KitInfo, LoadItem,
    SolarDimensionamento,
)
from app.catalog.service import list_kit_products, get_bess_comercial, list_products
from app.engines.bess import calculate_backup, calculate_peak_shaving, calculate_arbitrage_v2
from app.engines.kit_attributes import eff, eff_float
from app.engines.kit_builder import build_kits
from app.engines.schemas import (
    BackupInput, LoadRow,
    ArbitrageInputV2,
    PeakShavingInput, SolarInput,
    PeakShavingResult, SolarResult,
    SolarStringsInput,
)
from app.engines.solar_strings import size_solar_strings
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
            marca=str(eff(k.inversor, "marca") or eff(k.bateria, "marca") or "—"),
            bateria_modelo=str(eff(k.bateria, "title") or ""),
            inversor_modelo=str(eff(k.inversor, "title") or ""),
            qtd_baterias=k.qtd_baterias,
            qtd_inversores=k.qtd_inversores,
            capacidade_total_kwh=k.capacidade_total_kwh,
            potencia_total_kw=k.pico_entregavel_kw,
            preco_total=k.preco_total,
            distribuicao_baterias=k.distribuicao_baterias,
            n_caixas_juncao=k.n_caixas_juncao,
            pico_entregavel_kw=k.pico_entregavel_kw,
            alertas=k.alertas or None,
            itens=k.itens or None,
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

        # Fonte de kit/módulos: réplica meubess_products (tipo efetivo coalesce(manual,auto))
        inversores, baterias = await list_kit_products(db)
        modulos_fv = await list_products(db, tipo="modulo_fv", active=True)

        capacidade_kwh = 0.0
        potencia_kw = 0.0
        energia_necessaria_kwh = None
        economia_mensal = None
        economia_anual = None
        kit_selecionado = None
        alternativas = []
        payback_meses = None

        # Backup-specific extras
        backup_rows = None
        backup_result = None
        solar_dim_result = None

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

            # Autonomia agora em DIAS: a tabela de cargas já traz o uso diário (tdia_h),
            # então E_EPS já é a energia de 1 dia. Multiplicamos pelos dias desejados.
            autonomia_dias = req.autonomia_dias or 1.0

            backup_result = calculate_backup(BackupInput(
                cargas=cargas_engine,
                tipo_instalacao=req.tipo_instalacao or "monofasico",
                dod_percent=req.dod_percent or 90.0,
                autonomia_h=autonomia_dias * 24.0,
                eficiencia_roundtrip=req.eficiencia_roundtrip or 90.0,
            ))

            # E_BAT = energia diária das cargas (total_e_eps) × dias de autonomia
            energy_backup_kwh = round(backup_result.total_e_eps * autonomia_dias, 3)
            capacidade_kwh = energy_backup_kwh
            energia_necessaria_kwh = energy_backup_kwh
            potencia_kw = backup_result.total_pp

            tensoes_carga = {c.tensao for c in req.cargas_backup if c.tensao} or None
            kits, _skipped = build_kits(
                inversores, baterias,
                pn_kva=backup_result.total_pn,
                pp_kva=backup_result.total_pp,
                e_bat_kwh=energy_backup_kwh,
                fase_instalacao=req.tipo_instalacao or "monofasico",
                tensoes_carga=tensoes_carga,
                padrao_entrada=req.padrao_entrada,
            )
            kit_selecionado, alternativas = _kits_to_response(kits)

            # ── Solar dimensioning (optional) ────────────────────────────────
            solar_dim_result = None
            if (
                req.consumo_medio_mensal_kwh
                and req.hsp_media
                and kits
            ):
                best_kit = kits[0]  # already sorted by price ascending
                solar_dim_result = size_solar_strings(
                    inversor=best_kit.inversor,
                    modulos=modulos_fv,
                    solar_input=SolarStringsInput(
                        consumo_medio_mensal_kwh=req.consumo_medio_mensal_kwh,
                        hsp_media=req.hsp_media,
                    ),
                )

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

        elif req.tipo_calculo == "backup_direto":
            if req.total_pp_kva is None or req.total_e_eps_kwh is None:
                raise ValueError(
                    "total_pp_kva e total_e_eps_kwh são obrigatórios para backup_direto"
                )
            if req.total_e_eps_kwh <= 0:
                raise ValueError("total_e_eps_kwh deve ser maior que zero")

            capacidade_kwh = req.total_e_eps_kwh
            potencia_kw    = req.total_pp_kva

            kits, _skipped = build_kits(
                inversores, baterias,
                pn_kva=0.0,  # Pn não informado em backup_direto; pico (Pp) é o que filtra
                pp_kva=req.total_pp_kva,
                e_bat_kwh=req.total_e_eps_kwh,
                fase_instalacao=req.tipo_instalacao or "monofasico",
            )
            kit_selecionado, alternativas = _kits_to_response(kits)

        elif req.tipo_calculo == "peak_shaving":
            result: PeakShavingResult = calculate_peak_shaving(PeakShavingInput(
                curva_carga_kw=curva,
                demanda_alvo_kw=req.demanda_alvo_kw,
                tarifa_demanda_rs_kw=req.tarifa_demanda_rs_kw,
            ))
            capacidade_kwh = result.capacidade_necessaria_kwh
            potencia_kw = result.potencia_necessaria_kw
            economia_mensal = result.economia_mensal_estimada_rs

            kits, _skipped = build_kits(
                inversores, baterias,
                pn_kva=0.0, pp_kva=potencia_kw,
                e_bat_kwh=capacidade_kwh, fase_instalacao="monofasico",
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

            com_cap  = eff_float(bess_com, "usable_capacity_kwh") or 0.0
            com_dod  = eff_float(bess_com, "dod_percent") or 0.0
            com_preco = eff_float(bess_com, "preco") or 0.0

            arb_result = calculate_arbitrage_v2(ArbitrageInputV2(
                consumo_ponta_kwh=req.consumo_ponta_kwh,
                demanda_ponta_kw=req.demanda_ponta_kw,
                tarifa_ponta_kwh=req.tarifa_ponta_rs_kwh or 0.0,
                tarifa_fora_ponta_kwh=req.tarifa_fora_ponta_rs_kwh or 0.0,
                bess_capacidade_kwh=com_cap,
                bess_dod=com_dod,
                bess_preco=com_preco,
            ))

            capacidade_kwh = round(
                arb_result.qty_bess * com_cap * (com_dod / 100.0), 2
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

            kits, _skipped = build_kits(
                inversores, baterias,
                pn_kva=0.0, pp_kva=potencia_kw,
                e_bat_kwh=capacidade_kwh, fase_instalacao="monofasico",
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
            energia_necessaria_kwh=energia_necessaria_kwh,
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
            solar_dimensionamento=(
                SolarDimensionamento(
                    modulo_marca=solar_dim_result.modulo_marca,
                    modulo_modelo=solar_dim_result.modulo_modelo,
                    modulo_wp=solar_dim_result.modulo_wp,
                    qty_modulos=solar_dim_result.qty_modulos,
                    n_serie=solar_dim_result.n_serie,
                    n_paralelo=solar_dim_result.n_paralelo,
                    mppt_qty=solar_dim_result.mppt_qty,
                    kwp_instalado=solar_dim_result.kwp_instalado,
                    cobertura_pct=solar_dim_result.cobertura_pct,
                    preco_modulos_total=solar_dim_result.preco_modulos_total,
                )
                if solar_dim_result else None
            ),
        )

    except Exception as e:
        await mark_project_error(db, project)
        raise e
