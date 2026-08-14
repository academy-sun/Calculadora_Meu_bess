import unicodedata
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.calculate.schemas import (
    BackupLoadRow, BackupRowResult,
    CalculateRequest, CalculateResponse, Diagnostico, KitInfo, LoadItem,
    ProdutoDescartado, SolarDimensionamento,
)
from app.catalog.service import list_kit_products, list_pv_products, get_bess_comercial, list_products
from app.engines.bess import calculate_backup, calculate_peak_shaving, calculate_arbitrage_v2
from app.engines.kit_attributes import eff, eff_float
from app.engines.kit_builder import (
    CONEXOES_REDE, _alertas_rede, _bloqueio_rede, build_kits,
    carga_existe_na_rede, compativel_com_cargas, economic_undershoot_kit,
)
from app.engines.pv_kit import (
    build_combined_pv_storage, build_ongrid_kit_detalhado, ongrid_string_layout,
    resolve_kwp_alvo, select_module,
)
from app.engines.schemas import (
    BackupInput, LoadRow,
    ArbitrageInputV2,
    PeakShavingInput, SolarInput,
    PeakShavingResult, SolarResult,
    SolarStringsInput,
)
from app.engines.shipping import calcular_frete, calcular_frete_fob
from app.engines.solar_strings import size_solar_strings


def _build_load_curve(cargas: list[LoadItem]) -> list[float]:
    """Gera curva de carga sintética (24 pontos) a partir de cargas padrão."""
    curva = [0.0] * 24
    for carga in cargas:
        potencia_total_kw = (carga.potencia_w * carga.quantidade) / 1000.0
        horas_uso = min(int(carga.horas_uso_dia), 24)
        for h in range(horas_uso):
            curva[h] += potencia_total_kw
    return curva


def _kit_to_info(
    k,
    rotulo: str | None = None,
    rotulo_caminho: str | None = None,
    kwp_instalado: float | None = None,
) -> KitInfo:
    return KitInfo(
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
        rotulo=rotulo,
        rotulo_caminho=rotulo_caminho,
        kwp_instalado=kwp_instalado,
    )


def _option_to_info(
    option,
    rotulo: str,
    kwp_instalado: float,
) -> KitInfo:
    """Converte um CombinedOption em KitInfo fundindo os itens PV + BESS."""
    merged = option.to_merged_kit()
    return _kit_to_info(
        merged,
        rotulo=rotulo,
        rotulo_caminho=option.rotulo_caminho,
        kwp_instalado=round(kwp_instalado, 3),
    )


# Motivos de descarte que denunciam CADASTRO incompleto, nao incompatibilidade
# tecnica. Tratar os dois como a mesma coisa foi o que escondeu, por semanas,
# 8 inversores hibridos sem dados de entrada FV.
_MARCAS_DADO_AUSENTE = ("faltam dados", "não cadastrada", "nao cadastrada")


def _classificar_descarte(motivo: str) -> str:
    m = (motivo or "").lower()
    return "dado_ausente" if any(t in m for t in _MARCAS_DADO_AUSENTE) else "incompativel"


#: Horas desde o último sync a partir das quais a cotação avisa. O sync roda de
#: hora em hora; 3 h significa três ciclos perdidos, o que não é oscilação —
#: é defeito. Abaixo disso o aviso apareceria à toa e ninguém leria o painel.
_CATALOGO_VELHO_H = 3.0

#: Idade a partir da qual um produto individual conta como congelado. Bem mais
#: folgado que o do catálogo: aqui a causa não é o sync ter parado, é o produto
#: ter saído da listagem da plataforma. 48 h evita alarme por uma listagem que
#: oscilou entre um ciclo e outro.
_PRODUTO_CONGELADO_H = 48.0


def _horas_desde(marca) -> float:
    agora = datetime.now(timezone.utc)
    if marca.tzinfo is None:            # coluna gravada sem timezone
        marca = marca.replace(tzinfo=timezone.utc)
    return (agora - marca).total_seconds() / 3600.0


def _idade_do_catalogo(produtos: list) -> float | None:
    """Horas desde a sincronização MAIS RECENTE entre os produtos consultados.

    Mede se o sync como um todo parou. Sai da própria lista já carregada, sem
    consulta extra ao banco.
    """
    marcas = [p.last_synced_at for p in produtos if getattr(p, "last_synced_at", None)]
    return _horas_desde(max(marcas)) if marcas else None


def _produtos_congelados(produtos: list) -> list[tuple[str, float]]:
    """Produtos individuais que pararam de vir no sync, com a idade de cada um.

    Diferente de _idade_do_catalogo: aqui olha o mais ANTIGO, um por um. O sync
    atualiza só o que a plataforma lista, e um produto que sai da listagem
    congela com o último preço — sem erro, sem log, e continua cotável.

    Medido em produção: o SIW400H T030 ficou 55 dias com o preço de 17/06
    enquanto os outros 679 atualizavam de hora em hora. A idade do catálogo
    ficava fresca o tempo todo, porque ela olha o mais recente.
    """
    velhos = []
    for p in produtos:
        marca = getattr(p, "last_synced_at", None)
        if not marca:
            continue
        horas = _horas_desde(marca)
        if horas > _PRODUTO_CONGELADO_H:
            velhos.append((str(eff(p, "title") or "?"), horas))
    return sorted(velhos, key=lambda x: -x[1])


def _montar_diagnostico(
    skipped,
    req: CalculateRequest,
    inversores: list,
    tem_pv: bool,
    marca_kit: str = "",
) -> Diagnostico:
    """Traduz o que o motor descartou em algo que o consultor consegue ler."""
    descartados = [
        ProdutoDescartado(
            produto_id=str(s.produto_id),
            titulo=str(s.titulo),
            motivo=str(s.motivo),
            tipo=_classificar_descarte(s.motivo),
            marca=str(getattr(s, "marca", "") or ""),
        )
        for s in (skipped or [])
    ]

    avisos: list[str] = []
    avisos_internos: list[str] = []
    cargas = req.cargas_backup or []

    # Preço defasado é o erro mais caro que esta ferramenta pode cometer, e o
    # mais silencioso: se o sync horário parar (plataforma fora do ar, chave
    # revogada, agendador morto), nada muda na tela — a cotação continua saindo,
    # com o preço de ontem. Quem olha o log é a exceção; quem olha a proposta é
    # todo mundo. Então o aviso vai na proposta.
    idade = _idade_do_catalogo(inversores)
    if idade is not None and idade > _CATALOGO_VELHO_H:
        avisos.append(
            f"Catálogo sincronizado há {idade:.0f} h (o normal é 1 h) — os "
            f"preços podem estar desatualizados. Confira na plataforma MeuBESS "
            f"antes de enviar a proposta."
        )

    # Caso diferente do anterior, e invisível para ele: o sync roda bem, o
    # catálogo está fresco, mas UM produto saiu da listagem da plataforma e
    # congelou com o último preço — continuando cotável. Interno porque a ação
    # é nossa (tirar do catálogo ou reativar na plataforma), não do consultor.
    for titulo, horas in _produtos_congelados(inversores):
        avisos_internos.append(
            f"'{titulo}' não vem no sync há {horas / 24:.0f} dia(s) — preço "
            f"congelado enquanto o resto do catálogo atualiza de hora em hora."
        )

    # Regra que NAO rodou e silenciosa por natureza: sem o dado de entrada, o
    # motor nao valida e nada aparece. E preciso dizer que nao validou.
    if cargas and not any(c.tensao for c in cargas):
        avisos.append(
            "Cargas sem tensão informada — a compatibilidade da saída EPS do "
            "inversor NÃO foi verificada."
        )
    if cargas and not any(c.fase for c in cargas):
        avisos.append(
            "Cargas sem fase informada — a regra de fase (carga trifásica exige "
            "inversor trifásico) NÃO foi verificada."
        )

    # NÃO vira aviso o volume de produtos sem cadastro completo. Medido em
    # produção: 128 descartes por dado ausente em toda cotação, e mesmo
    # filtrando pela marca do kit sobram 110 — são "Cabine de Baterias" e
    # afins, classificados como `bateria` na réplica sem serem módulos
    # candidatos. Isso é higiene de catálogo, não alarme de cotação; um alerta
    # que aparece sempre faz o consultor ignorar o painel inteiro, inclusive os
    # avisos que importam. A contagem fica no painel, sob demanda.

    # Inversor sem dados de entrada FV nao "recusa" modulos: o motor apenas nao
    # sabe quantos cabem, e o efeito pratico e empurrar todo o FV para um
    # inversor string, geralmente superdimensionado.
    if tem_pv:
        sem_fv = [
            str(eff(i, "title") or "?")
            for i in inversores
            if not eff_float(i, "voc_max_voltage") or not eff(i, "qty_mppt")
        ]
        if sem_fv:
            # Interno: nomeia produtos do catálogo e denuncia buraco de
            # cadastro nosso. Não vai para o usuário final.
            avisos_internos.append(
                f"{len(sem_fv)} inversor(es) híbrido(s) sem dados de entrada FV "
                f"cadastrados foram tratados como incapazes de receber módulos: "
                f"{', '.join(sem_fv[:3])}{'…' if len(sem_fv) > 3 else ''}."
            )

    return Diagnostico(avisos=avisos, avisos_internos=avisos_internos,
                       descartados=descartados)


def _normalizar_fase(v: str | None) -> str:
    """'Trifásico' → 'trifasico'. O catálogo grava com acento e caixa variada."""
    s = unicodedata.normalize("NFD", str(v or ""))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").strip().lower()


def _solar_dim_ongrid(detalhe, kwp_alvo: float) -> SolarDimensionamento | None:
    """Dimensionamento FV do kit on-grid puro.

    Monta a partir do que o kit realmente leva (módulo e quantidade escolhidos),
    não de um redimensionamento paralelo — assim a ficha nunca diverge dos itens
    cotados. n_serie/n_paralelo vêm da mesma restrição elétrica que aprovou o
    inversor. Retorna None quando o inversor não expõe os dados de MPPT.
    """
    if detalhe is None:
        return None
    layout = ongrid_string_layout(detalhe)
    if layout is None:
        return None
    n_serie, n_paralelo, mppt_qty = layout

    mod = detalhe.modulo
    kwp_instalado = round(mod.wp * detalhe.qty_modulos / 1000, 3)
    cobertura = round(min(kwp_instalado / kwp_alvo * 100, 999.9), 1) if kwp_alvo > 0 else 0.0

    return SolarDimensionamento(
        modulo_marca=str(eff(mod.produto, "marca") or "—"),
        modulo_modelo=str(eff(mod.produto, "title") or ""),
        modulo_wp=mod.wp,
        qty_modulos=detalhe.qty_modulos,
        n_serie=n_serie,
        n_paralelo=n_paralelo,
        mppt_qty=mppt_qty,
        kwp_instalado=kwp_instalado,
        cobertura_pct=cobertura,
        preco_modulos_total=round(mod.preco * detalhe.qty_modulos, 2),
    )


def _conexoes_rede(padrao_entrada: str | None) -> dict[str, str]:
    """{fase do inversor: tensão de conexão} para o padrão de entrada.

    Ausência da chave significa "esse tipo de inversor não se conecta nessa
    rede" — um trifásico não tem onde se ligar num padrão monofásico.
    """
    return CONEXOES_REDE.get(padrao_entrada or "", {"monofasico": {"220"}})


def _resolver_frete(req: CalculateRequest, kit: KitInfo | None) -> dict | None:
    """Frete do kit escolhido.

    Compartilhado pelo retorno antecipado do on-grid puro (sem cargas) e pelo
    fluxo principal. Antes só o fluxo principal calculava, então kit on-grid
    saía sempre sem frete — inclusive com CIF e UF preenchidos.
    """
    if not kit:
        return None
    if req.tipo_frete == "fob":
        return calcular_frete_fob(kit.preco_total)
    if req.tipo_frete == "cif" and req.uf_entrega:
        return calcular_frete(req.uf_entrega, kit.preco_total)
    return None


def _frete_do_kit(req: CalculateRequest, preco_kit: float) -> float | None:
    """Valor do frete para um preço de kit. None quando não há frete a cobrar."""
    if req.tipo_frete == "fob":
        info = calcular_frete_fob(preco_kit)
    elif req.tipo_frete == "cif" and req.uf_entrega:
        info = calcular_frete(req.uf_entrega, preco_kit)
    else:
        return None
    return (info or {}).get("valor")


def _aplicar_frete_e_cobertura(
    req: CalculateRequest,
    kits: list[KitInfo | None],
    energia_exigida_kwh: float | None,
) -> None:
    """Preenche frete, total e cobertura de CADA kit, no lugar.

    Ponto único de propósito. O frete era calculado só para o kit escolhido,
    então as alternativas apareciam sem ele — e como o CIF é percentual sobre
    o valor do kit, comparar alternativas sem frete inverte a conclusão quando
    a diferença entre elas é da ordem do próprio frete.
    """
    for kit in kits:
        if kit is None:
            continue
        kit.frete_valor = _frete_do_kit(req, kit.preco_total)
        kit.total_com_frete = round(kit.preco_total + (kit.frete_valor or 0.0), 2)
        if energia_exigida_kwh and energia_exigida_kwh > 0:
            kit.cobertura_energia = round(
                kit.capacidade_total_kwh / energia_exigida_kwh, 4)


def _select_kits(kits, e_bat_kwh: float, jbw_produtos: list | None = None) -> tuple[KitInfo | None, list[KitInfo]]:
    """
    Seleciona até 3 opções de kit a partir da lista (já ordenada por preço crescente,
    um kit por par inversor×bateria compatível, vindo de build_kits):

    - Sugerido: o mais barato (mesma regra de sempre).
    - Alternativa — outra composição: próximo kit mais barato com par inversor/bateria
      diferente do sugerido (já garantido, pois cada kit é um par distinto).
    - Alternativa — mais econômica: variante com MENOS baterias que o mínimo suficiente
      (todo kit em `kits` já cobre 100% da energia por construção — ver
      economic_undershoot_kit), a mais barata que mais se aproxima de 100% sem atingir.
    """
    if not kits:
        return None, []

    sugerido = kits[0]
    alt_composicao = kits[1] if len(kits) > 1 else None
    alt_economica = economic_undershoot_kit(kits, e_bat_kwh, jbw_produtos)

    alternativas = []
    if alt_composicao:
        alternativas.append(_kit_to_info(alt_composicao, "Alternativa — outra composição"))
    if alt_economica:
        alternativas.append(_kit_to_info(alt_economica, "Alternativa — mais econômica"))

    return _kit_to_info(sugerido, "Kit sugerido"), alternativas


async def run_calculation(db: AsyncSession, req: CalculateRequest) -> CalculateResponse:
    """
    Calcula e devolve a resposta — NÃO persiste nada. A busca de kits é só uma prévia;
    o Project só é criado quando o usuário escolhe um kit (ver POST /projects em
    app.projects.router, que consome SaveQuoteRequest com este mesmo CalculateResponse).
    """
    solicitado_em = req.origem_info.solicitado_em

    if req.curva_carga_kw:
        curva = req.curva_carga_kw
    elif req.cargas:
        curva = _build_load_curve(req.cargas)
    else:
        curva = []

    # Fonte de kit/módulos: réplica meubess_products (tipo efetivo coalesce(manual,auto))
    perfil = req.perfil_usuario
    inversores, baterias, jbw_produtos = await list_kit_products(db, perfil=perfil)
    pv = await list_pv_products(db, perfil=perfil)   # módulos, inversores string, acessórios FV

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
    kwp_alvo_calculado = None

    # Arbitragem-specific extras
    arb_result = None

    # Motivos de descarte do motor. Antes eram jogados fora em `_skipped` —
    # o kit errado da demo estava explicado aqui e ninguem via.
    skipped_total: list = []

    if req.tipo_calculo == "backup":
        # Resolve kWp alvo do FV (informado ou derivado de consumo+HSP+PR)
        kwp_alvo_calculado = resolve_kwp_alvo(
            powerpeak_kwp=req.powerpeak_kwp,
            consumo_medio_mensal_kwh=req.consumo_medio_mensal_kwh,
            hsp_media=req.hsp_media,
            taxa_desempenho=req.taxa_desempenho,
        )

        tem_cargas = bool(req.cargas_backup)
        tem_pv = kwp_alvo_calculado is not None

        # ── 1.1: sem cargas → kit on-grid puro (sem bateria) ─────────────
        if not tem_cargas:
            if not tem_pv:
                raise ValueError("cargas_backup é obrigatório para backup (sem FV) "
                                 "ou informe powerpeak_kwp / consumo_medio_mensal_kwh + hsp_media para kit on-grid")
            ongrid_itens, ongrid_detalhe = build_ongrid_kit_detalhado(
                kwp_alvo=kwp_alvo_calculado,
                modulos=pv["modulos"],
                fixing_type=req.fixing_type,
                cabos=pv["cabos"],
                mc4s=pv["mc4s"],
                estruturas=pv["estruturas"],
                inversores_string=pv["inversores_string"],
                conexoes=_conexoes_rede(req.padrao_entrada),
            )
            if ongrid_itens:
                preco_total_ongrid = sum(i["preco_total"] for i in ongrid_itens)
                kwp_real = round(
                    (ongrid_detalhe.modulo.wp * ongrid_detalhe.qty_modulos / 1000)
                    if ongrid_detalhe else kwp_alvo_calculado,
                    3,
                )
                # R7 no on-grid puro. Os alertas de rede só eram emitidos dentro
                # de build_kits, que este caminho não chama — kit sem bateria
                # saía sempre com o aviso genérico e mais nada, mesmo quando a
                # conexão exigia ressalva.
                alertas_ongrid = ["Kit on-grid puro — sem armazenamento"]
                if ongrid_detalhe and ongrid_detalhe.inversor is not None:
                    alertas_ongrid += _alertas_rede(
                        ongrid_detalhe.inversor,
                        req.tipo_instalacao,
                        req.padrao_entrada,
                        qtd_inversores=ongrid_detalhe.qtd_inversores or 1,
                    )

                # KitBESS-like estrutura fake sem bateria para _kit_to_info
                from app.engines.kit_builder import KitBESS
                kit_ongrid_fake = KitBESS(
                    inversor=type("_Inv", (), {"meubess_id": "ongrid", "title": "Sistema FV On-Grid",
                                               "marca": ""})(),
                    bateria=type("_Bat", (), {"meubess_id": "none", "title": "—", "marca": ""})(),
                    qtd_inversores=1, qtd_baterias=0,
                    distribuicao_baterias=[], n_caixas_juncao=0,
                    capacidade_total_kwh=0.0,
                    pico_entregavel_kw=0.0,
                    preco_total=preco_total_ongrid,
                    alertas=alertas_ongrid,
                    itens=ongrid_itens,
                )
                kit_selecionado = _kit_to_info(
                    kit_ongrid_fake, "Kit sugerido", "dc", kwp_real,
                )
                potencia_kw = 0.0
                capacidade_kwh = 0.0
            # On-grid puro não tem energia de backup exigida: sem cobertura a
            # calcular, só frete e total.
            _aplicar_frete_e_cobertura(req, [kit_selecionado], None)
            # sem backup_rows pois não há cargas
            return CalculateResponse(  # type: ignore[return-value]
                projeto_id=None,
                tipo_calculo=req.tipo_calculo,
                origem=req.origem_info.origem,
                negocio_id=req.origem_info.negocio_id,
                solicitado_em=req.origem_info.solicitado_em,
                calculado_em=datetime.now(timezone.utc),
                capacidade_kwh=capacidade_kwh,
                potencia_kw=potencia_kw,
                kwp_alvo=round(kwp_alvo_calculado, 3),
                kit_selecionado=kit_selecionado,
                alternativas=[],
                frete=_resolver_frete(req, kit_selecionado),
                diagnostico=_montar_diagnostico(
                    skipped_total, req, inversores, True,
                    kit_selecionado.marca if kit_selecionado else "",
                ),
                solar_dimensionamento=_solar_dim_ongrid(ongrid_detalhe, kwp_alvo_calculado),
            )

        # ── Cargas × padrão de entrada: o cenário existe? ─────────────────
        # Antes de escolher qualquer equipamento. Um kit tecnicamente correto
        # para um cenário que não existe na instalação é o pior tipo de erro:
        # passa por todas as regras e ninguém percebe.
        impossiveis = []
        for c in req.cargas_backup:
            motivo = carga_existe_na_rede(
                req.padrao_entrada, c.tensao, _normalizar_fase(c.fase))
            if motivo:
                impossiveis.append(f"{c.nome}: {motivo}")
        if impossiveis:
            diag = _montar_diagnostico([], req, inversores, tem_pv)
            diag.avisos = [
                "Cenário incompatível com o padrão de entrada declarado — "
                "nenhum kit foi dimensionado. Corrija a tensão/fase das cargas "
                "ou o padrão de entrada.",
                *impossiveis,
            ] + diag.avisos
            # A resposta é PLANA (origem, negocio_id, solicitado_em...), não
            # aninhada em origem_info como o request. Passar o objeto inteiro
            # fazia o Pydantic recusar a resposta com 6 campos faltando, e o
            # cliente recebia 500 — ou seja, a validação de cenário impossível
            # nunca chegou a ser vista: ela derrubava a requisição em vez de
            # explicar o problema.
            return CalculateResponse(  # type: ignore[return-value]
                projeto_id=None,
                tipo_calculo=req.tipo_calculo,
                origem=req.origem_info.origem,
                negocio_id=req.origem_info.negocio_id,
                solicitado_em=req.origem_info.solicitado_em,
                calculado_em=datetime.now(timezone.utc),
                capacidade_kwh=0.0,
                potencia_kw=0.0,
                kit_selecionado=None,
                alternativas=[],
                frete=None,
                diagnostico=diag,
            )

        # ── Com tabela de cargas: dimensiona armazenamento ────────────────
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

        autonomia_dias = req.autonomia_dias or 1.0
        backup_result = calculate_backup(BackupInput(
            cargas=cargas_engine,
            tipo_instalacao=req.tipo_instalacao or "monofasico",
            dod_percent=req.dod_percent or 90.0,
            autonomia_h=autonomia_dias * 24.0,
            eficiencia_roundtrip=req.eficiencia_roundtrip or 90.0,
        ))

        energy_backup_kwh = round(backup_result.total_e_eps * autonomia_dias, 3)
        capacidade_kwh = energy_backup_kwh
        energia_necessaria_kwh = energy_backup_kwh
        potencia_kw = backup_result.total_pp

        tensoes_carga = {c.tensao for c in req.cargas_backup if c.tensao} or None
        fases_carga = {_normalizar_fase(c.fase) for c in req.cargas_backup if c.fase} or None
        # Tensão exigida ENTRE FASES. Só carga TRIFÁSICA entra aqui: ela ocupa
        # as três fases e precisa da tensão de linha exata, que não dá para
        # remanejar — um 380/220 nunca entrega 220 V entre fases.
        #
        # Bifásica NÃO entra: ela usa dois condutores e só precisa da diferença
        # de potencial certa entre eles. Num 380/220, ligada entre fase e
        # neutro, recebe os 220 V que precisa. Continua sendo decisão de
        # instalação, e por isso segue como alerta (_alertas_fase_carga).
        tensoes_entre_fases_carga = {
            c.tensao for c in req.cargas_backup
            if c.tensao and _normalizar_fase(c.fase) == "trifasico"
        } or None
        kits, _skipped_i = build_kits(
            inversores, baterias,
            pn_kva=backup_result.total_pn,
            pp_kva=backup_result.total_pp,
            e_bat_kwh=energy_backup_kwh,
            fase_instalacao=req.tipo_instalacao or "monofasico",
            tensoes_carga=tensoes_carga,
            fases_carga=fases_carga,
            tensoes_entre_fases_carga=tensoes_entre_fases_carga,
            padrao_entrada=req.padrao_entrada,
            jbw_produtos=jbw_produtos,
        )
        skipped_total += _skipped_i

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

        # ── 2: combina PV (quando kWp informado) OU armazenamento puro ───
        if tem_pv and kits:
            # O caminho combinado pode SUBSTITUIR o híbrido (caminho "scaled")
            # por um maior que absorva todo o FV. Sem filtrar antes, essa troca
            # ignora a R8 e devolve inversor monofásico para carga trifásica —
            # e ignora a R7, reintroduzindo o 380 V numa rede 127/220 que
            # build_kits já tinha barrado.
            hibridos_compativeis = [
                i for i in inversores
                if compativel_com_cargas(
                    i, tensoes_carga, fases_carga, tensoes_entre_fases_carga,
                    req.padrao_entrada)[0]
                and not _bloqueio_rede(i, req.padrao_entrada)
            ]
            sugerido_opt, alt_opts = build_combined_pv_storage(
                kits_storage=kits,
                e_bat_kwh=energy_backup_kwh,
                kwp_alvo=kwp_alvo_calculado,
                modulos=pv["modulos"],
                fixing_type=req.fixing_type,
                cabos=pv["cabos"],
                mc4s=pv["mc4s"],
                estruturas=pv["estruturas"],
                inversores_string=pv["inversores_string"],
                inversores_hibridos=hibridos_compativeis,
                conexoes=_conexoes_rede(req.padrao_entrada),
                jbw_produtos=jbw_produtos,
            )
            if sugerido_opt:
                mod_ref, qty_ref = select_module(pv["modulos"], kwp_alvo_calculado)
                kwp_real = round((mod_ref.wp * qty_ref / 1000) if mod_ref else kwp_alvo_calculado, 3)

                ROTULOS_COMBINADO = {
                    "dc": "Kit sugerido — FV + armazenamento (DC acoplado)",
                    "split": "Kit sugerido — FV com inversor string + armazenamento",
                    "scaled": "Kit sugerido — Híbrido ampliado + FV integrado",
                }
                ROTULOS_ALT = {
                    "dc": "Alternativa — FV + armazenamento (DC acoplado)",
                    "split": "Alternativa — FV com inversor string separado",
                    "scaled": "Alternativa — Híbrido ampliado para absorver todo o FV",
                    "eco": "Alternativa — mais econômica (cobertura parcial de energia)",
                }
                kit_selecionado = _option_to_info(
                    sugerido_opt,
                    ROTULOS_COMBINADO.get(sugerido_opt.rotulo_caminho, "Kit sugerido"),
                    kwp_real,
                )
                alternativas = [
                    _option_to_info(
                        opt,
                        ROTULOS_ALT.get(opt.rotulo_caminho, "Alternativa"),
                        kwp_real,
                    )
                    for opt in alt_opts
                ]
            else:
                # FV inviável (sem módulos com dados) — cai no armazenamento puro
                kit_selecionado, alternativas = _select_kits(kits, energy_backup_kwh, jbw_produtos)
        else:
            # armazenamento puro (sem FV)
            kit_selecionado, alternativas = _select_kits(kits, energy_backup_kwh, jbw_produtos)

            # legacy DC-acoplado simples (consumo+hsp SEM powerpeak_kwp nem taxa_desempenho)
            if req.consumo_medio_mensal_kwh and req.hsp_media and kits:
                best_kit = kits[0]
                solar_dim_result = size_solar_strings(
                    inversor=best_kit.inversor,
                    modulos=pv["modulos"],
                    solar_input=SolarStringsInput(
                        consumo_medio_mensal_kwh=req.consumo_medio_mensal_kwh,
                        hsp_media=req.hsp_media,
                    ),
                )

        if kit_selecionado:
            payback_meses = None

    elif req.tipo_calculo == "backup_direto":
        if req.total_pp_kva is None or req.total_e_eps_kwh is None:
            raise ValueError(
                "total_pp_kva e total_e_eps_kwh são obrigatórios para backup_direto"
            )
        if req.total_e_eps_kwh <= 0:
            raise ValueError("total_e_eps_kwh deve ser maior que zero")

        capacidade_kwh = req.total_e_eps_kwh
        potencia_kw    = req.total_pp_kva
        energia_necessaria_kwh = req.total_e_eps_kwh

        kits, _skipped_i = build_kits(
            inversores, baterias,
            pn_kva=0.0,  # Pn não informado em backup_direto; pico (Pp) é o que filtra
            pp_kva=req.total_pp_kva,
            e_bat_kwh=req.total_e_eps_kwh,
            fase_instalacao=req.tipo_instalacao or "monofasico",
            jbw_produtos=jbw_produtos,
        )
        skipped_total += _skipped_i
        kit_selecionado, alternativas = _select_kits(kits, req.total_e_eps_kwh, jbw_produtos)

    elif req.tipo_calculo == "peak_shaving":
        result: PeakShavingResult = calculate_peak_shaving(PeakShavingInput(
            curva_carga_kw=curva,
            demanda_alvo_kw=req.demanda_alvo_kw,
            tarifa_demanda_rs_kw=req.tarifa_demanda_rs_kw,
        ))
        capacidade_kwh = result.capacidade_necessaria_kwh
        potencia_kw = result.potencia_necessaria_kw
        economia_mensal = result.economia_mensal_estimada_rs

        kits, _skipped_i = build_kits(
            inversores, baterias,
            pn_kva=0.0, pp_kva=potencia_kw,
            e_bat_kwh=capacidade_kwh, fase_instalacao="monofasico",
            jbw_produtos=jbw_produtos,
        )
        skipped_total += _skipped_i
        kit_selecionado, alternativas = _select_kits(kits, capacidade_kwh, jbw_produtos)

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

        kits, _skipped_i = build_kits(
            inversores, baterias,
            pn_kva=0.0, pp_kva=potencia_kw,
            e_bat_kwh=capacidade_kwh, fase_instalacao="monofasico",
            jbw_produtos=jbw_produtos,
        )
        skipped_total += _skipped_i
        kit_selecionado, alternativas = _select_kits(kits, capacidade_kwh, jbw_produtos)
        kwp_alvo_calculado = round(capacidade_kwh, 3)

    calculado_em = datetime.now(timezone.utc)

    frete_info = _resolver_frete(req, kit_selecionado)
    # Todos os kits, não só o escolhido — inclusive as alternativas, que é onde
    # a falta de frete mais engana na hora de comparar.
    _aplicar_frete_e_cobertura(
        req, [kit_selecionado, *alternativas], energia_necessaria_kwh)

    # Integração com Ploomes (Sync Automático) — apenas notifica, não persiste mais
    # (o Project só é criado quando o usuário escolhe um kit, via POST /projects)
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

        import asyncio
        asyncio.create_task(create_ploomes_interaction(req.origem_info.negocio_id, resumo))

    return CalculateResponse(
            projeto_id=None,
            tipo_calculo=req.tipo_calculo,
            origem=req.origem_info.origem,
            negocio_id=req.origem_info.negocio_id,
            solicitado_em=solicitado_em,
            calculado_em=calculado_em,
            capacidade_kwh=capacidade_kwh,
            potencia_kw=potencia_kw,
            energia_necessaria_kwh=energia_necessaria_kwh,
            kwp_alvo=round(kwp_alvo_calculado, 3) if kwp_alvo_calculado else None,
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
            frete=frete_info,
            diagnostico=_montar_diagnostico(
                skipped_total, req, inversores, bool(kwp_alvo_calculado),
                kit_selecionado.marca if kit_selecionado else "",
            ),
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
