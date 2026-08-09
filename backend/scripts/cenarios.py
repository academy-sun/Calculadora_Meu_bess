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


def main() -> None:
    atual = rodar()
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
