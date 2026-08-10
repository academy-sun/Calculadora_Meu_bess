"""Matriz de cenários — trava o comportamento do motor contra o catálogo real.

Os testes unitários provam as regras com produtos de mentira. Isto aqui roda
cenários representativos contra o catálogo de PRODUÇÃO e congela o resultado.
Qualquer mudança futura que altere um kit aparece como diferença ANTES do
deploy, em vez de aparecer numa demonstração para cliente.

    python scripts/cenarios.py                 # roda e mostra
    python scripts/cenarios.py --gravar        # grava a linha de base
    python scripts/cenarios.py --comparar      # compara com a linha de base

Variáveis: API_URL (default produção) e API_KEY (obrigatória).
"""
import json
import os
import sys
from pathlib import Path

import httpx

API = os.environ.get("API_URL", "https://calculadorameubess-production.up.railway.app")
KEY = os.environ.get("API_KEY", "")
BASE = Path(__file__).resolve().parent.parent.parent / "docs" / "cenarios-esperados.json"

ORIGEM = {"origem": "interno", "solicitante_id": "cenarios",
          "solicitante_nome": "Matriz de cenarios",
          "solicitado_em": "2026-01-01T00:00:00Z"}


def carga(nome, pnom_w, *, qtd=1, fp=0.9, ip_in=2.0, tdia=6, tensao="220",
          fase="monofasico"):
    return {"nome": nome, "qtd": qtd, "pnom_w": pnom_w, "fp": fp, "fd": 1.0,
            "ip_in": ip_in, "tdia_h": tdia, "tensao": tensao, "fase": fase}


GELADEIRA = carga("Geladeira", 200, ip_in=3.0, tdia=24)
AR_MONO = carga("Ar condicionado 12k", 1150, ip_in=3.0, tdia=8)
AR_TRI = carga("Ar condicionado 30k", 3600, ip_in=3.0, tdia=8, fase="trifasico")
BOMBA_TRI = carga("Bomba trifásica 5CV", 4000, ip_in=4.0, tdia=4, fase="trifasico")
CARGA_127 = carga("Iluminação 127V", 800, ip_in=1.0, tdia=6, tensao="127")

# Cada cenário é um caso que um consultor realmente monta. Manter curto e
# legível — a lista é para ser revisada por humano, não para ser exaustiva.
CENARIOS = [
    ("mono-pequeno-sem-fv", dict(
        cargas_backup=[GELADEIRA], tipo_instalacao="monofasico",
        padrao_entrada="mono_220", autonomia_dias=1)),
    ("mono-medio-sem-fv", dict(
        cargas_backup=[GELADEIRA, AR_MONO], tipo_instalacao="monofasico",
        padrao_entrada="mono_220", autonomia_dias=1)),
    ("mono-2-dias-autonomia", dict(
        cargas_backup=[GELADEIRA, AR_MONO], tipo_instalacao="monofasico",
        padrao_entrada="mono_220", autonomia_dias=2)),
    ("mistura-127-220-exige-split", dict(
        cargas_backup=[CARGA_127, AR_MONO], tipo_instalacao="monofasico",
        padrao_entrada="mono_127", autonomia_dias=1)),
    ("trifasico-pequeno", dict(
        cargas_backup=[AR_TRI], tipo_instalacao="trifasico",
        padrao_entrada="tri_220_380", autonomia_dias=1)),
    ("trifasico-com-bomba", dict(
        cargas_backup=[AR_TRI, BOMBA_TRI], tipo_instalacao="trifasico",
        padrao_entrada="tri_220_380", autonomia_dias=1)),
    ("trifasico-380v", dict(
        cargas_backup=[carga("Motor trifásico 380 V", 7500, ip_in=3.0, tdia=6,
                             tensao="380", fase="trifasico")],
        tipo_instalacao="trifasico", padrao_entrada="tri_220_380", autonomia_dias=1)),
    ("bifasico-220", dict(
        cargas_backup=[carga("Chuveiro bifásico", 5500, ip_in=1.0, tdia=1,
                             fase="bifasico")],
        tipo_instalacao="monofasico", padrao_entrada="mono_220", autonomia_dias=1)),
    ("ongrid-puro-8kwp", dict(
        powerpeak_kwp=8.5, tipo_instalacao="monofasico",
        padrao_entrada="mono_220")),
    ("ongrid-puro-20kwp", dict(
        powerpeak_kwp=20.0, tipo_instalacao="monofasico",
        padrao_entrada="mono_220")),
    # Mesmos 20 kWp do cenário acima, mudando só o padrão de entrada. Sem
    # cargas não há tensão de carga para restringir nada — quem limita o
    # inversor é a rede em que ele será ligado, e é isso que este par mostra.
    ("ongrid-puro-20kwp-tri-380", dict(
        powerpeak_kwp=20.0, tipo_instalacao="trifasico",
        padrao_entrada="tri_220_380")),
    ("combinado-mono-8kwp", dict(
        cargas_backup=[GELADEIRA, AR_MONO], powerpeak_kwp=8.5,
        tipo_instalacao="monofasico", padrao_entrada="mono_220", autonomia_dias=1)),
    ("combinado-mono-18kwp", dict(
        cargas_backup=[GELADEIRA], powerpeak_kwp=18.5,
        tipo_instalacao="monofasico", padrao_entrada="mono_220", autonomia_dias=1)),
    ("combinado-tri-15kwp", dict(
        cargas_backup=[AR_TRI], powerpeak_kwp=15.0,
        tipo_instalacao="trifasico", padrao_entrada="tri_220_380", autonomia_dias=1)),
    ("frete-cif-acre", dict(
        cargas_backup=[AR_MONO], tipo_instalacao="monofasico",
        padrao_entrada="mono_220", autonomia_dias=1,
        tipo_frete="cif", uf_entrega="AC")),
    ("frete-fob", dict(
        cargas_backup=[AR_MONO], tipo_instalacao="monofasico",
        padrao_entrada="mono_220", autonomia_dias=1, tipo_frete="fob")),
    ("carga-sem-tensao-nem-fase", dict(
        cargas_backup=[{"nome": "Carga crua", "qtd": 1, "pnom_w": 1000,
                        "fp": 1.0, "fd": 1.0, "ip_in": 1.0, "tdia_h": 4}],
        tipo_instalacao="monofasico", padrao_entrada="mono_220", autonomia_dias=1)),
    ("carga-enorme-sem-solucao", dict(
        cargas_backup=[carga("Forno industrial", 200000, ip_in=3.0, tdia=8)],
        tipo_instalacao="trifasico", padrao_entrada="tri_220_380", autonomia_dias=2)),
]


FASE_CURTA = {"monofasico": "mono", "bifasico": "bi", "trifasico": "tri"}


def br(v: float, casas: int = 2) -> str:
    """Número em pt-BR — o documento vai para revisão de engenharia."""
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def plural(n: int, singular: str, plural_: str) -> str:
    return f"{n} {singular if n == 1 else plural_}"


def descrever_cargas(extra: dict) -> str:
    """As cargas do cenário em português, para o engenheiro conferir."""
    cargas = extra.get("cargas_backup") or []
    if not cargas:
        return "—"
    partes = []
    for c in cargas:
        fase = FASE_CURTA.get(c.get("fase") or "", "fase não informada")
        tensao = f"{c['tensao']} V" if c.get("tensao") else "tensão não informada"
        partes.append(f"{c['qtd']}× {c['nome']} {c['pnom_w']} W {fase} {tensao} "
                      f"(IP/IN {c['ip_in']:g}, {c['tdia_h']:g} h/dia)")
    dias = extra.get("autonomia_dias")
    sufixo = f" — autonomia {dias:g} dia(s)" if dias else ""
    return "; ".join(partes) + sufixo


def descrever_kit(r: dict) -> str:
    """Todos os itens do kit, não só o inversor."""
    if not r.get("kit"):
        return "nenhum kit compatível"
    ordem = {"inversor": 0, "inversor_string": 1, "bateria": 2, "modulo_fv": 3}
    itens = sorted(r.get("itens") or [], key=lambda i: ordem.get(i["tipo"], 9))
    partes = [f"{i['qtd']}× {i['nome']}" for i in itens]
    k = r["kit"]
    if k.get("n_jbw"):
        partes.append(f"{k['n_jbw']}× caixa de junção (JBW)")
    return "<br>".join(partes) if partes else "—"


def sequencia_calculo(r: dict, extra: dict) -> str:
    """O passo a passo que levou a ESTE inversor, com os números de cada etapa.

    Não é texto decorativo: cada passo cita o valor que o motor comparou, para
    o engenheiro poder refazer a conta na mão e discordar com fundamento.
    """
    passos = []
    cargas = extra.get("cargas_backup") or []
    pn, pp = r.get("total_pn_kva"), r.get("total_pp_kva")
    e_nec = r.get("energia_necessaria_kwh")
    kwp = r.get("kwp_alvo") or extra.get("powerpeak_kwp")

    # 1. levantamento
    if cargas:
        dias = extra.get("autonomia_dias") or 1
        passos.append(
            f"**1. Levantamento das cargas** — Pn {br(pn or 0)} kVA, "
            f"Pp {br(pp or 0)} kVA (pico de partida = Pn × IP/IN), "
            f"energia {br(e_nec or 0, 1)} kWh para {dias:g} dia(s)")
    else:
        passos.append("**1. Sem cargas de backup** — dimensionamento só pelo FV")

    # 2. filtro de compatibilidade AC
    fases = {c.get("fase") for c in cargas if c.get("fase")}
    tensoes = sorted({c.get("tensao") for c in cargas if c.get("tensao")})
    if cargas:
        if not fases and not tensoes:
            passos.append("**2. Compatibilidade de saída (R8)** — ⚠ carga sem "
                          "tensão nem fase: a regra NÃO foi aplicada")
        else:
            exig = []
            if "trifasico" in fases:
                exig.append("saída trifásica")
            if tensoes:
                exig.append(f"atender {'/'.join(tensoes)} V")
            passos.append(f"**2. Compatibilidade de saída (R8)** — exige "
                          f"{' e '.join(exig)}; inversores que não atendem são "
                          f"descartados antes de qualquer conta de potência")

    if not r.get("kit"):
        motivos = r.get("motivos_incompat") or []
        detalhe = ("<br>".join(f"• {m}" for m in motivos[:6])
                   if motivos else "sem detalhe registrado")
        passos.append("**3. Nenhum inversor atende** — motivo por modelo:<br>"
                      + detalhe)
        return "<br><br>".join(passos)

    k = r["kit"]
    itens = r.get("itens") or []
    inv = next((i for i in itens if i["tipo"] == "inversor"), None)
    bat = next((i for i in itens if i["tipo"] == "bateria"), None)
    n_inv = k.get("qtd_inversores") or 1

    # 3. potência do inversor
    if inv and cargas:
        pico_un = inv.get("potencia_pico_kw")
        nom_un = inv.get("potencia_inversao_kw")
        detalhe = []
        if pico_un:
            detalhe.append(f"pico {br(pico_un)} kVA × {n_inv} = "
                           f"{br(pico_un * n_inv)} kVA ≥ Pp {br(pp or 0)}")
        if nom_un:
            detalhe.append(f"nominal {br(nom_un)} kW × {n_inv} = "
                           f"{br(nom_un * n_inv)} kW ≥ Pn {br(pn or 0)}")
        passos.append(f"**3. Potência do inversor (R3/R4)** — {'; '.join(detalhe)}"
                      + (f". {n_inv} unidades em paralelo" if n_inv > 1 else ""))

    # 4. energia -> baterias
    if bat and k.get("qtd_baterias"):
        n = k["qtd_baterias"]
        util = bat.get("energia_unit_kwh") or (k["capacidade_kwh"] / n)
        n_energia = max(1, int(-(-(e_nec or 0) // util))) if util else n
        entradas = (inv or {}).get("entradas_bateria")
        teto = f", teto de {entradas * n_inv * 4} pelo nº de entradas (R1)" if entradas else ""
        passos.append(
            f"**4. Energia → nº de baterias (R1)** — {br(e_nec or 0, 1)} kWh ÷ "
            f"{br(util)} kWh úteis = {n_energia} bateria(s){teto}")

        # 5. potência de partida -> distribuicao
        dist = k.get("distribuicao") or []
        i_ent = (inv or {}).get("corrente_entrada_a")
        i_pico = bat.get("corrente_pico_a")
        tensao_bat = bat.get("tensao_v")
        if dist and i_ent and i_pico and tensao_bat:
            parcelas = [f"min({d}×{br(i_pico,0)}; {br(i_ent,0)}) A"
                        for d in dist if d > 0]
            passos.append(
                f"**5. Potência de partida (R2)** — {n} baterias distribuídas "
                f"{'+'.join(map(str, dist))} entre as entradas; corrente = "
                f"{' + '.join(parcelas)} → pico entregável "
                f"{br(k.get('pico_kw') or 0)} kW"
                + (f" (subiu de {n_energia} para {n} baterias porque a energia "
                   f"sozinha não entregava o pico)" if n > n_energia else ""))
        if k.get("n_jbw"):
            passos.append(f"**6. Acessório (R9)** — {k['n_jbw']} caixa(s) de "
                          f"junção, uma por entrada com 2+ baterias")

    # FV
    if kwp:
        tem_string = any(i["tipo"] == "inversor_string" for i in itens)
        teto = (inv or {}).get("potencia_inversao_kw")
        txt = (f"**7. Fotovoltaico** — {br(kwp)} kWp alvo; ")
        if tem_string and bat:
            txt += ("acima do teto de matriz do híbrido, excedente vai para "
                    "inversor string (caminho split)")
        elif tem_string:
            txt += "sem armazenamento, todo o FV em inversor string"
        else:
            txt += (f"cabe na entrada CC do híbrido"
                    + (f" (teto ≈ {br((teto or 0) * 2)} kWp = 2× a potência CA)"
                       if teto else ""))
        passos.append(txt)

    # Escolha final. A resposta traz duas alternativas com significados
    # diferentes, e misturá-las faria parecer que o motor não pegou a mais
    # barata: "outra composição" é a 2ª colocada entre as VIÁVEIS (mais cara,
    # por definição); "mais econômica" é sub-dimensionada de propósito — não
    # cobre a autonomia pedida, então é mais barata e está fora da disputa.
    if not bat and not (r.get("concorrentes") or []):
        # On-grid puro: não há disputa inversor×bateria para explicar.
        passos.append(f"**Escolha final** — R$ {br(k['preco'])}")
        for a in k.get("alertas") or []:
            passos.append(f"⚠ {a}")
        return "<br><br>".join(passos)

    linhas_conc = [f"• **escolhida** — {k['qtd_baterias'] or 0}× "
                   f"{(k.get('bateria') or '—')[-14:]}, "
                   f"{br(k.get('capacidade_kwh') or 0, 1)} kWh → "
                   f"**R$ {br(k['preco'])}**"]
    fora_disputa = []
    for c in r.get("concorrentes") or []:
        desc = (f"{c['qtd_baterias']}× {(c['bateria'] or '—')[-14:]} "
                f"({(c['inversor'] or '')[:26]}), "
                f"{br(c.get('capacidade_kwh') or 0, 1)} kWh → "
                f"R$ {br(c['preco'] or 0)}")
        if "econômica" in (c.get("rotulo") or ""):
            fora_disputa.append(
                f"• {desc} — **sub-dimensionada de propósito**: cobre "
                f"{br(c.get('capacidade_kwh') or 0, 1)} dos "
                f"{br(e_nec or 0, 1)} kWh pedidos. É mais barata porque "
                f"entrega menos autonomia; não competiu.")
        elif c["preco"] and abs(c["preco"] - k["preco"]) < 0.01:
            linhas_conc.append(
                f"• {desc} ← **empatou no centavo**. Mesma energia, mesmo "
                f"pico ({br(k.get('pico_kw') or 0)} kW, limitado pelo "
                f"inversor). Desempate: menos componentes.")
        else:
            linhas_conc.append(f"• {desc} — 2ª colocada entre as viáveis")
    passos.append(
        "**Escolha final** — o motor não escolheu o inversor primeiro. Ele "
        "montou TODAS as combinações inversor×bateria que passaram nos "
        "filtros acima, cada uma com seu preço, e só então ordenou. "
        "Classificação:<br>" + "<br>".join(linhas_conc)
        + (("<br><br>_Fora da disputa:_<br>" + "<br>".join(fora_disputa))
           if fora_disputa else ""))
    for a in k.get("alertas") or []:
        passos.append(f"⚠ {a}")
    return "<br><br>".join(passos)


def equipamentos_bloqueados(r: dict) -> str:
    """O que poderia ter entrado se o cadastro estivesse completo."""
    f = r.get("fora_por_cadastro") or {}
    linhas = []
    for t in f.get("inversores") or []:
        linhas.append(f"🔌 {t}")
    for t in f.get("baterias") or []:
        linhas.append(f"🔋 {t}")
    if f.get("outros"):
        linhas.append(f"_+ {f['outros']} itens sem spec (cabines BSCW e baterias "
                      f"de outras marcas) — não são módulos candidatos_")
    return "<br>".join(linhas) if linhas else "nenhum"


def resumir(d: dict) -> dict:
    """Só o que importa comparar — nada de timestamp ou id, que mudam sempre."""
    k = d.get("kit_selecionado")
    diag = d.get("diagnostico") or {}
    comum = {
        "energia_necessaria_kwh": d.get("energia_necessaria_kwh"),
        "total_pn_kva": d.get("total_pn_kva"),
        "total_pp_kva": d.get("total_pp_kva"),
        "kwp_alvo": d.get("kwp_alvo"),
        "avisos": sorted(diag.get("avisos") or []),
        "fora_por_cadastro": _fora_por_cadastro(diag),
        "motivos_incompat": _motivos_incompat(diag),
    }
    if not k:
        return {"kit": None, **comum}
    ELETRICOS = ("potencia_inversao_kw", "potencia_pico_kw", "entradas_bateria",
                 "corrente_entrada_a", "energia_unit_kwh", "corrente_pico_a",
                 "tensao_v")
    itens = [
        {"tipo": i["tipo"], "qtd": i["qtd"], "nome": i["nome"],
         **{c: i[c] for c in ELETRICOS if i.get(c) is not None}}
        for i in (k.get("itens") or [])
        if i["tipo"] in ("inversor", "inversor_string", "bateria", "modulo_fv")
    ]
    diag = d.get("diagnostico") or {}
    return {
        "kit": {
            "inversor": k.get("inversor_modelo"),
            "bateria": k.get("bateria_modelo"),
            "qtd_baterias": k.get("qtd_baterias"),
            "qtd_inversores": k.get("qtd_inversores"),
            "distribuicao": k.get("distribuicao_baterias"),
            "n_jbw": k.get("n_caixas_juncao"),
            "capacidade_kwh": k.get("capacidade_total_kwh"),
            "pico_kw": k.get("pico_entregavel_kw"),
            "kwp": k.get("kwp_instalado"),
            "preco": k.get("preco_total"),
            "alertas": sorted(k.get("alertas") or []),
        },
        "itens": sorted(itens, key=lambda x: (x["tipo"], x["nome"])),
        "frete": (d.get("frete") or {}).get("valor"),
        "alternativas": len(d.get("alternativas") or []),
        "concorrentes": [
            {"rotulo": a.get("rotulo"), "inversor": a.get("inversor_modelo"),
             "qtd_baterias": a.get("qtd_baterias"),
             "bateria": a.get("bateria_modelo"),
             "capacidade_kwh": a.get("capacidade_total_kwh"),
             "preco": a.get("preco_total")}
            for a in (d.get("alternativas") or [])
        ],
        **comum,
    }


def _motivos_incompat(diag: dict) -> list:
    """Motivos distintos de incompatibilidade dos INVERSORES — o que explica um
    cenario sem solucao."""
    out, vistos = [], set()
    for d in diag.get("descartados") or []:
        t = d.get("titulo") or ""
        if d.get("tipo") != "incompativel" or "SIW" not in t or t in vistos:
            continue
        vistos.add(t)
        out.append(f"{t}: {d.get('motivo')}")
    return out[:12]


def _fora_por_cadastro(diag: dict) -> dict:
    inversores, baterias, outros = [], [], 0
    vistos = set()
    for d in diag.get("descartados") or []:
        if d.get("tipo") != "dado_ausente":
            continue
        t = d.get("titulo") or ""
        if t in vistos:
            continue
        vistos.add(t)
        falta = (d.get("motivo") or "").split(":", 1)[-1].strip()
        if "SIW" in t:
            inversores.append(f"{t} (falta {falta})")
        elif "Módulo de Bateria" in t:
            baterias.append(f"{t} (falta {falta})")
        else:
            outros += 1
    return {"inversores": inversores, "baterias": baterias, "outros": outros}


def rodar() -> dict:
    if not KEY:
        sys.exit("defina API_KEY")
    out = {}
    with httpx.Client(timeout=180) as c:
        for nome, extra in CENARIOS:
            payload = {"origem_info": ORIGEM, "tipo_calculo": "backup",
                       "perfil_usuario": "admin", "dod_percent": 90,
                       "eficiencia_roundtrip": 90, **extra}
            r = c.post(f"{API}/calculate", headers={"X-API-Key": KEY}, json=payload)
            if r.status_code >= 400:
                out[nome] = {"erro": f"HTTP {r.status_code}", "corpo": r.text[:200]}
            else:
                out[nome] = resumir(r.json())
            print(f"  {nome:<28} {'ERRO' if r.status_code >= 400 else 'ok'}")
    return out


def descrever(nome: str, r: dict) -> str:
    if "erro" in r:
        return f"{r['erro']}"
    if not r.get("kit"):
        return "nenhum kit compatível"
    k = r["kit"]
    partes = [f"{k['inversor'][:40]}"]
    if k["qtd_inversores"] and k["qtd_inversores"] > 1:
        partes.append(f"x{k['qtd_inversores']}")
    # o inversor string faz parte do kit e precisa aparecer na revisão — sem
    # ele a linha esconde metade do que está sendo cotado
    for i in r.get("itens") or []:
        if i["tipo"] == "inversor_string":
            partes.append(f"+ string {i['qtd']}x {i['nome'][:30]}")
    if k["qtd_baterias"]:
        partes.append(f"+ {k['qtd_baterias']} bat {k['distribuicao']}")
    if k["kwp"]:
        partes.append(f"| {k['kwp']} kWp")
    partes.append(f"| R$ {k['preco']:.0f}")
    return " ".join(partes)


def gerar_tabela(atual: dict) -> str:
    """Markdown para revisão de engenharia."""
    linhas = [
        "| Cenário | FV (kWp) | Cargas de armazenamento | Kit escolhido | "
        "Sequência de cálculo | Bloqueados por cadastro incompleto | "
        "Preço do kit | Frete | Total |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    por_nome = dict(CENARIOS)
    for nome, r in atual.items():
        extra = por_nome.get(nome, {})
        kwp = r.get("kwp_alvo") or extra.get("powerpeak_kwp") or 0
        pp = r.get("total_pp_kva")
        cargas = descrever_cargas(extra)
        if pp:
            cargas += f"<br>**Pp total {br(pp)} kVA**"
        preco = (r.get("kit") or {}).get("preco")
        # Frete em coluna própria: ele nunca entrou no preco_total do kit, então
        # dois cenários idênticos com fretes diferentes saíam com o mesmo número
        # e pareciam bug. É o mesmo kit — o que muda está aqui do lado.
        frete = r.get("frete")
        rotulo_frete = "—"
        if extra.get("tipo_frete") == "cif":
            rotulo_frete = f"CIF {extra.get('uf_entrega') or ''}".strip()
        elif extra.get("tipo_frete") == "fob":
            rotulo_frete = "FOB"
        cel_frete = (f"{rotulo_frete}<br>R$ {br(frete)}" if frete
                     else rotulo_frete)
        total = (preco or 0) + (frete or 0)
        linhas.append(
            f"| **{nome}** | {kwp:g} | {cargas} | {descrever_kit(r)} | "
            f"{sequencia_calculo(r, extra)} | {equipamentos_bloqueados(r)} | "
            f"{'R$ ' + br(preco) if preco else '—'} | {cel_frete} | "
            f"{'R$ ' + br(total) if preco else '—'} |"
        )
    return "\n".join(linhas)


def main() -> None:
    atual = rodar()
    if "--tabela" in sys.argv:
        destino = Path(__file__).resolve().parent.parent.parent / "docs" / "cenarios-validacao.md"
        destino.write_text(
            "# Cenários para validação de engenharia\n\n"
            "Gerado por `backend/scripts/cenarios.py --tabela` contra o catálogo\n"
            "de produção. As siglas R1–R9 remetem a\n"
            "[auditoria-regras-r1-r9.md](auditoria-regras-r1-r9.md).\n\n"
            "## Como o motor decide (vale para todas as linhas)\n\n"
            "**Não é uma busca gulosa.** O motor não escolhe o inversor mais\n"
            "barato para depois testar se ele serve. A ordem é:\n\n"
            "1. **Enumera todas as combinações** — laço duplo sobre *cada*\n"
            "   inversor × *cada* bateria do catálogo.\n"
            "2. **Aplica os filtros em cada par**, nesta ordem: dados completos →\n"
            "   saída EPS compatível com tensão e fase das cargas (R8; carga\n"
            "   trifásica exige a tensão **entre fases**, então um 380/220 não\n"
            "   serve carga trifásica 220 V) →\n"
            "   potência de pico e nominal, escalando inversores em paralelo se\n"
            "   preciso (R3/R4) → compatibilidade inversor×bateria (R5) →\n"
            "   nº de baterias por energia e por potência de partida, respeitando\n"
            "   o teto de entradas (R1/R2).\n"
            "3. **Cada par que sobrevive vira um kit completo, com preço.**\n"
            "4. **Só no fim ordena**, por: menor preço → maior pico entregável →\n"
            "   menos componentes. O preço decide *entre os viáveis*; nunca\n"
            "   dispensa uma restrição.\n\n"
            "Consequência prática: um inversor caro que é o único a atender a\n"
            "fase da carga vence um barato incompatível, porque o barato nem\n"
            "chega à etapa de preço. E quando dois kits empatam — a CB100 custa\n"
            "exatamente o dobro da CB050, então 4×CB050 e 2×CB100 dão o mesmo\n"
            "total — o desempate é explícito, não a ordem da lista.\n\n"
            "A coluna **Sequência de cálculo** mostra esses passos com os números\n"
            "de cada cenário e termina com a classificação por preço.\n\n"
            "Duas ressalvas sobre essa classificação:\n\n"
            "- Ela mostra o 1º e o 2º colocados, não a lista inteira — é o que a\n"
            "  API devolve para a tela. As demais combinações viáveis existiram e\n"
            "  perderam no preço; não aparecem aqui.\n"
            "- A linha **_fora da disputa_**, quando aparece, é a \"alternativa\n"
            "  mais econômica\": um kit **sub-dimensionado de propósito**, que\n"
            "  NÃO cobre a autonomia pedida. Ele é mais barato justamente por\n"
            "  isso, e por isso não concorreu. É uma oferta comercial para o\n"
            "  cliente que quer gastar menos e aceita menos autonomia — nunca\n"
            "  uma resposta ao dimensionamento solicitado.\n\n"
            + gerar_tabela(atual) + "\n",
            encoding="utf-8")
        print(f"\ntabela gravada: {destino}")
        return
    if "--gravar" in sys.argv:
        BASE.parent.mkdir(parents=True, exist_ok=True)
        BASE.write_text(json.dumps(atual, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nlinha de base gravada: {BASE}")
        return

    print("\n=== resultado ===")
    for nome, r in atual.items():
        print(f"  {nome:<28} {descrever(nome, r)}")

    if "--comparar" in sys.argv:
        if not BASE.exists():
            sys.exit(f"\nsem linha de base em {BASE} — rode --gravar primeiro")
        base = json.loads(BASE.read_text(encoding="utf-8"))
        difs = [n for n in set(base) | set(atual) if base.get(n) != atual.get(n)]
        print("\n=== comparação com a linha de base ===")
        if not difs:
            print("  nenhuma diferença")
            return
        for n in sorted(difs):
            print(f"\n  [{n}]")
            print(f"     antes: {descrever(n, base.get(n, {}))}")
            print(f"     agora: {descrever(n, atual.get(n, {}))}")
        sys.exit(f"\n{len(difs)} cenário(s) mudaram — revise antes de publicar")


if __name__ == "__main__":
    main()
