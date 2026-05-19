# Design: `backup_direto` — Cálculo de Cargas no Ploomes

**Data:** 2026-05-19  
**Autor:** brainstorming session  
**Status:** aprovado para implementação

---

## Contexto

O endpoint `POST /calculate` com `tipo_calculo: "backup"` recebe dados brutos de cada equipamento (`cargas_backup[]`) e calcula Pn, Dmn, Pp, DMp, E_EPS internamente antes de selecionar o kit BESS.

O Ploomes já possui os totais calculados (`total_pp_kva`, `total_e_eps_kwh`) no momento em que dispara a integração. Enviar os dados brutos é redundante e obriga o Ploomes a manter uma lista de parâmetros por equipamento que ele já não usa.

---

## Objetivo

Permitir que o Ploomes envie apenas os totais pré-calculados das cargas e receba o kit BESS recomendado — sem modificar o fluxo existente de `backup`.

---

## Abordagem escolhida

Novo valor `"backup_direto"` no campo `tipo_calculo`. O backend pula o cálculo das cargas e chama `find_compatible_kits` diretamente com os totais recebidos.

Alternativas descartadas:
- **Campos opcionais no `backup` existente** — schema ambígua, dois modos incompatíveis no mesmo tipo
- **Endpoint separado `/calculate/backup-direto`** — duplica auth, criação de projeto e response sem ganho

---

## Mudanças

### 1. `app/calculate/schemas.py`

Adicionar dois campos opcionais a `CalculateRequest`:

```python
total_pp_kva:    Optional[float] = None
total_e_eps_kwh: Optional[float] = None
```

Adicionar `"backup_direto"` ao `Literal` de `tipo_calculo`:

```python
tipo_calculo: Literal[
    "backup", "backup_direto",
    "peak_shaving", "arbitragem",
    "solar", "solar_storage"
]
```

### 2. `app/calculate/service.py`

Novo bloco `elif` em `run_calculation`, após o bloco `"backup"`, sem alterar nenhum bloco existente:

```python
elif req.tipo_calculo == "backup_direto":
    if req.total_pp_kva is None or req.total_e_eps_kwh is None:
        raise ValueError(
            "total_pp_kva e total_e_eps_kwh são obrigatórios para backup_direto"
        )
    if req.total_e_eps_kwh <= 0:
        raise ValueError("total_e_eps_kwh deve ser maior que zero")

    capacidade_kwh = req.total_e_eps_kwh
    potencia_kw    = req.total_pp_kva

    kits = find_compatible_kits(
        baterias=baterias,
        inversores=inversores,
        total_pp_kva=req.total_pp_kva,
        total_e_eps_kwh=req.total_e_eps_kwh,
        tipo_instalacao=req.tipo_instalacao or "monofasico",
    )
    kit_selecionado, alternativas = _kits_to_response(kits)
```

### 3. `docs/api-ploomes.md`

Adicionar seção **Tipo 1b — Backup Direto (Ploomes)** com exemplo de request/response.

---

## Contrato da API

### Request

```json
{
  "origem_info": {
    "origem": "ploomes",
    "negocio_id": "123456",
    "negocio_nome": "Empresa ABC",
    "solicitante_id": "rep-001",
    "solicitante_nome": "João Vendas",
    "solicitado_em": "2026-05-19T14:00:00Z"
  },
  "tipo_calculo": "backup_direto",
  "tipo_instalacao": "monofasico",
  "total_pp_kva": 28.8,
  "total_e_eps_kwh": 4.8
}
```

### Response

Mesmo shape do `backup` normal. Campos `backup_rows`, `total_pn_kva`, `total_dmn_kva`, `total_dmp_kva` ficam `null` (já são opcionais na response).

```json
{
  "projeto_id": "uuid",
  "tipo_calculo": "backup_direto",
  "capacidade_kwh": 4.8,
  "potencia_kw": 28.8,
  "kit_selecionado": {
    "marca": "WEG",
    "bateria_modelo": "SBW CB050 W00",
    "inversor_modelo": "SIW200H M050 W00",
    "qtd_baterias": 1,
    "qtd_inversores": 1,
    "capacidade_total_kwh": 5.02,
    "potencia_total_kw": 5.0,
    "preco_total": 14080.12
  },
  "alternativas": [...],
  "backup_rows": null,
  "payback_meses": null
}
```

---

## Validação e erros

| Situação | HTTP | Detalhe |
|----------|------|---------|
| `total_pp_kva` ou `total_e_eps_kwh` ausente | `400` | `"total_pp_kva e total_e_eps_kwh são obrigatórios para backup_direto"` |
| `total_e_eps_kwh <= 0` | `400` | `"total_e_eps_kwh deve ser maior que zero"` |
| Nenhum kit no catálogo | `200` | `kit_selecionado: null` — dado de negócio, não erro de API |

---

## Compatibilidade

- Nenhuma mudança no fluxo `tipo_calculo: "backup"` — continua funcionando identicamente
- Campos novos (`total_pp_kva`, `total_e_eps_kwh`) são `Optional` — não quebram clients existentes
- Response shape idêntico — frontend não precisa de alteração

---

## Testes necessários

- `backup_direto` com totais válidos → retorna kit
- `backup_direto` sem `total_pp_kva` → 400
- `backup_direto` sem `total_e_eps_kwh` → 400
- `backup_direto` com `total_e_eps_kwh=0` → 400
- `backup` existente continua passando sem alteração
