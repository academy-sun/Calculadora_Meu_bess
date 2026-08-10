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


def explicar_escolha(r: dict, extra: dict) -> str:
    """Por que ESTE kit. Composto do que o motor de fato usou para decidir."""
    if not r.get("kit"):
        avisos = r.get("avisos") or []
        return "Nenhum inversor atende. " + (avisos[0] if avisos else "")
    k, motivos = r["kit"], []

    cargas = extra.get("cargas_backup") or []
    fases = {c.get("fase") for c in cargas if c.get("fase")}
    tensoes = {c.get("tensao") for c in cargas if c.get("tensao")}
    if "trifasico" in fases:
        motivos.append("carga trifásica exige inversor trifásico (R8)")
    if len(tensoes) > 1:
        motivos.append(f"cargas em {'/'.join(sorted(tensoes))} V exigem saída "
                       f"que atenda as duas (R8)")

    # baterias: energia ou potência de partida?
    if k.get("qtd_baterias"):
        n = k["qtd_baterias"]
        usavel = (k["capacidade_kwh"] / n) if n else 0
        e_nec = r.get("energia_necessaria_kwh") or 0
        n_energia = max(1, -(-e_nec // usavel)) if usavel else n
        if n > n_energia:
            motivos.append(
                f"{plural(n, 'bateria', 'baterias')} definidas pela potência de "
                f"partida, não pela energia ({int(n_energia)} bastaria) (R2)")
        else:
            motivos.append(f"{plural(n, 'bateria', 'baterias')} pela energia "
                           f"exigida ({br(e_nec, 1)} kWh)")
        if k.get("distribuicao") and len(k["distribuicao"]) > 1:
            motivos.append(f"distribuídas {'+'.join(map(str, k['distribuicao']))} "
                           f"entre as entradas para extrair potência (R2)")
    if (k.get("qtd_inversores") or 1) > 1:
        motivos.append(f"{k['qtd_inversores']} inversores em paralelo "
                       f"para atender o pico (R4)")

    tem_string = any(i["tipo"] == "inversor_string" for i in (r.get("itens") or []))
    if tem_string and k.get("qtd_baterias"):
        motivos.append("FV acima do teto de matriz do híbrido; excedente em "
                       "inversor string")
    motivos.append("mais barato entre os compatíveis")

    for a in k.get("alertas") or []:
        motivos.append(f"⚠ {a}")
    return ". ".join(motivos)


def resumir(d: dict) -> dict:
    """Só o que importa comparar — nada de timestamp ou id, que mudam sempre."""
    k = d.get("kit_selecionado")
    if not k:
        diag = d.get("diagnostico") or {}
        return {"kit": None, "avisos": sorted(diag.get("avisos") or [])}
    itens = [
        {"tipo": i["tipo"], "qtd": i["qtd"], "nome": i["nome"]}
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
        "avisos": sorted(diag.get("avisos") or []),
        # usados para explicar a escolha na tabela de validação
        "energia_necessaria_kwh": d.get("energia_necessaria_kwh"),
        "total_pp_kva": d.get("total_pp_kva"),
        "kwp_alvo": d.get("kwp_alvo"),
    }


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
        "Motivo da escolha | Preço |",
        "|---|---|---|---|---|---|",
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
        linhas.append(
            f"| **{nome}** | {kwp:g} | {cargas} | {descrever_kit(r)} | "
            f"{explicar_escolha(r, extra)} | "
            f"{'R$ ' + br(preco) if preco else '—'} |"
        )
    return "\n".join(linhas)


def main() -> None:
    atual = rodar()
    if "--tabela" in sys.argv:
        destino = Path(__file__).resolve().parent.parent.parent / "docs" / "cenarios-validacao.md"
        destino.write_text(
            "# Cenários para validação de engenharia\n\n"
            "Gerado por `backend/scripts/cenarios.py --tabela` contra o catálogo\n"
            "de produção. Cada linha é um caso que um consultor monta de verdade.\n"
            "O motivo da escolha é derivado do que o motor usou para decidir —\n"
            "as siglas R2/R4/R8 remetem a\n"
            "[auditoria-regras-r1-r9.md](auditoria-regras-r1-r9.md).\n\n"
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
