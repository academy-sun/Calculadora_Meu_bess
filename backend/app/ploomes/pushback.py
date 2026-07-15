"""
Write-back do resultado do dimensionamento no Ploomes:

  1. Campos resumo no negócio (PATCH /Deals(id) com OtherProperties mapeadas).
  2. Itens do kit como produtos no orçamento mais recente do negócio
     (upsert em /Products por Code, depois POST em /Quotes(id)/Products).
  3. Comentário (interaction) com o resumo — reaproveita o fluxo legado.

Cada etapa reporta sucesso/erro individualmente: o embed mostra o que entrou
e o que falhou, para iterarmos na configuração da conta sem cegueira.
"""

import logging

from app.ploomes import client
from app.ploomes.context import field_map
from app.ploomes.schemas import PushbackRequest

logger = logging.getLogger(__name__)


def _summary_properties(req: PushbackRequest) -> list[dict]:
    """Monta OtherProperties para os campos de saída mapeados na conta."""
    fmap = field_map()
    props: list[dict] = []

    def add(key: str, value, kind: str):
        fk = fmap.get(key)
        if not fk or value is None:
            return
        if kind == "decimal":
            props.append({"FieldKey": fk, "DecimalValue": float(value)})
        else:
            props.append({"FieldKey": fk, "StringValue": str(value)})

    add("kit_preco", req.kit_preco, "decimal")
    add("kit_descricao", req.kit_descricao, "string")
    add("frete_valor", req.frete_valor, "decimal")
    add("frete_descricao", req.frete_descricao, "string")
    add("total_geral", req.total_geral, "decimal")
    return props


async def _upsert_product(nome: str, sku: str | None, preco: float) -> int | None:
    """Encontra produto por Code (sku) ou Name; cria se não existir. Retorna Id."""
    if sku:
        data = await client.get(f"/Products?$filter=Code+eq+'{sku}'&$select=Id&$top=1")
        found = data.get("value") or []
        if found:
            return found[0]["Id"]
    nome_escaped = nome.replace("'", "''")
    data = await client.get(f"/Products?$filter=Name+eq+'{nome_escaped}'&$select=Id&$top=1")
    found = data.get("value") or []
    if found:
        return found[0]["Id"]

    body: dict = {"Name": nome, "UnitPrice": preco}
    if sku:
        body["Code"] = sku
    created = await client.post("/Products", body)
    value = created.get("value")
    if isinstance(value, list) and value:
        return value[0].get("Id")
    return created.get("Id")


async def _latest_quote_id(deal_id: int) -> int | None:
    data = await client.get(
        f"/Quotes?$filter=DealId+eq+{deal_id}&$orderby=Id+desc&$select=Id&$top=1"
    )
    quotes = data.get("value") or []
    return quotes[0]["Id"] if quotes else None


async def push_result(req: PushbackRequest) -> dict:
    """Executa o write-back completo; devolve relatório por etapa."""
    report: dict = {
        "campos": {"ok": False, "detalhe": None},
        "produtos": {"ok": False, "detalhe": None, "itens": []},
        "comentario": {"ok": False},
    }

    # 1 — campos resumo no negócio
    props = _summary_properties(req)
    if props:
        try:
            await client.patch(f"/Deals({req.deal_id})", {"OtherProperties": props})
            report["campos"] = {"ok": True, "detalhe": f"{len(props)} campo(s) atualizados"}
        except client.PloomesError as e:
            report["campos"] = {"ok": False, "detalhe": str(e)}
    else:
        report["campos"] = {
            "ok": False,
            "detalhe": "PLOOMES_FIELD_MAP sem chaves de saída configuradas — nada a gravar",
        }

    # 2 — itens do kit no orçamento mais recente
    if req.incluir_produtos and req.itens:
        try:
            quote_id = await _latest_quote_id(req.deal_id)
            if quote_id is None:
                report["produtos"]["detalhe"] = "negócio sem orçamento — itens não inseridos"
            else:
                inseridos = []
                for item in req.itens:
                    try:
                        product_id = await _upsert_product(item.nome, item.sku, item.preco_unitario)
                        await client.post(
                            f"/Quotes({quote_id})/Products",
                            {
                                "ProductId": product_id,
                                "Quantity": item.qtd,
                                "UnitPrice": item.preco_unitario,
                            },
                        )
                        inseridos.append({"nome": item.nome, "ok": True})
                    except client.PloomesError as e:
                        inseridos.append({"nome": item.nome, "ok": False, "erro": str(e)})
                report["produtos"] = {
                    "ok": all(i["ok"] for i in inseridos),
                    "detalhe": f"orçamento {quote_id}",
                    "itens": inseridos,
                }
        except client.PloomesError as e:
            report["produtos"]["detalhe"] = str(e)

    # 3 — comentário resumo (nunca falha o fluxo)
    resumo = (
        f"⚡ Dimensionamento MeuBESS enviado à proposta\n"
        f"- Kit: {req.kit_descricao}\n"
        f"- Valor do kit: R$ {req.kit_preco:,.2f}\n"
    )
    if req.frete_valor is not None:
        resumo += f"- Frete ({req.frete_descricao or '—'}): R$ {req.frete_valor:,.2f}\n"
    if req.total_geral is not None:
        resumo += f"- Total geral: R$ {req.total_geral:,.2f}\n"
    report["comentario"]["ok"] = await client.create_ploomes_interaction(str(req.deal_id), resumo)

    return report
