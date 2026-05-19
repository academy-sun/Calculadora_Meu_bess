# API MeuBESS — Documentação para Integração Ploomes

> **Base URL (produção):** `https://<seu-app>.up.railway.app`
> Substitua pelo domínio atual do Railway antes de usar.

---

## Autenticação

O endpoint de cálculo usa **API Key** no header HTTP:

```
X-API-Key: <sua-api-key-ploomes>
```

A chave é configurada na variável de ambiente `API_KEY_PLOOMES` no Railway. Qualquer requisição sem a chave correta retorna `401 Unauthorized`.

---

## Fluxo Ploomes → MeuBESS

```
Ploomes envia POST /calculate
        ↓
Backend calcula e salva projeto no Supabase
        ↓
Backend posta comentário automático no negócio Ploomes (async)
        ↓
Resposta JSON retorna kit recomendado + alternativas
```

---

## POST `/calculate`

Endpoint principal. Realiza o dimensionamento e retorna o resultado completo.

### Headers

| Header | Obrigatório | Valor |
|--------|-------------|-------|
| `Content-Type` | ✅ | `application/json` |
| `X-API-Key` | ✅ | Chave da integração Ploomes |

---

### Campos comuns (todos os tipos)

```jsonc
{
  "origem_info": {
    "origem": "ploomes",           // "ploomes" | "interno"
    "negocio_id": "123456",        // ID do negócio no Ploomes (string)
    "negocio_nome": "Empresa ABC", // Nome do negócio (exibido no histórico)
    "solicitante_id": "user-uuid", // ID do usuário que disparou
    "solicitante_nome": "João",    // Nome exibido
    "solicitado_em": "2026-05-19T14:00:00Z" // ISO 8601 UTC
  },
  "tipo_calculo": "backup"  // ver seções abaixo
}
```

---

## Tipo 1 — Backup de Energia

Dimensiona bateria + inversor híbrido para garantir autonomia na falta de energia.

### Campos específicos

| Campo | Tipo | Obrigatório | Padrão | Descrição |
|-------|------|-------------|--------|-----------|
| `tipo_instalacao` | string | ✅ | — | `"monofasico"` ou `"trifasico"` |
| `cargas_backup` | array | ✅ | — | Lista de equipamentos a proteger (ver abaixo) |
| `autonomia_horas` | float | ❌ | `4.0` | Horas de autonomia desejada |
| `dod_percent` | float | ❌ | `90.0` | Profundidade de descarga (0–100) |
| `eficiencia_roundtrip` | float | ❌ | `90.0` | Eficiência do ciclo (0–100) |
| `consumo_medio_mensal_kwh` | float | ❌ | — | Para dimensionamento solar opcional |
| `hsp_media` | float | ❌ | — | Horas de Sol Pleno da cidade (kWh/m²/dia) |

### Objeto `cargas_backup[]`

| Campo | Tipo | Obrigatório | Padrão | Descrição |
|-------|------|-------------|--------|-----------|
| `nome` | string | ✅ | — | Nome do equipamento (exibido na tabela) |
| `qtd` | int | ❌ | `1` | Quantidade de unidades |
| `pnom_w` | float | ✅ | — | Potência nominal em Watts |
| `fp` | float | ❌ | `1.0` | Fator de potência |
| `fd` | float | ❌ | `1.0` | Fator de demanda |
| `ip_in` | float | ❌ | `1.0` | Relação corrente de partida / nominal |
| `tdia_h` | float | ❌ | `4.0` | Horas de uso por dia |

### Exemplo de requisição

```json
{
  "origem_info": {
    "origem": "ploomes",
    "negocio_id": "123456",
    "negocio_nome": "Padaria Central",
    "solicitante_id": "rep-001",
    "solicitante_nome": "Carlos Vendas",
    "solicitado_em": "2026-05-19T14:00:00Z"
  },
  "tipo_calculo": "backup",
  "tipo_instalacao": "monofasico",
  "autonomia_horas": 4,
  "dod_percent": 90,
  "cargas_backup": [
    {
      "nome": "Geladeira Comercial",
      "qtd": 2,
      "pnom_w": 350,
      "fp": 0.92,
      "fd": 0.8,
      "ip_in": 3.0,
      "tdia_h": 24
    },
    {
      "nome": "Iluminação LED",
      "qtd": 10,
      "pnom_w": 20,
      "fp": 1.0,
      "fd": 1.0,
      "ip_in": 1.0,
      "tdia_h": 12
    }
  ]
}
```

### Resposta (backup)

```jsonc
{
  "projeto_id": "uuid-do-projeto",
  "tipo_calculo": "backup",
  "origem": "ploomes",
  "negocio_id": "123456",
  "solicitado_em": "2026-05-19T14:00:00Z",
  "calculado_em": "2026-05-19T14:00:01Z",

  // Resumo dimensionado
  "capacidade_kwh": 4.8,      // Energia total necessária (kWh)
  "potencia_kw": 5.2,         // Potência total das cargas (kW)
  "payback_meses": null,       // Sempre null para backup

  // Totais da tabela de cargas
  "total_pn_kva": 0.87,
  "total_dmn_kva": 0.71,
  "total_pp_kva": 2.61,
  "total_dmp_kva": 2.13,

  // Detalhamento por equipamento
  "backup_rows": [
    {
      "nome": "Geladeira Comercial",
      "pn_kva": 0.76,
      "dmn_kva": 0.61,
      "pp_kva": 2.28,
      "dmp_kva": 1.83,
      "e_eps_kwh": 18.24
    },
    {
      "nome": "Iluminação LED",
      "pn_kva": 0.2,
      "dmn_kva": 0.2,
      "pp_kva": 0.2,
      "dmp_kva": 0.2,
      "e_eps_kwh": 2.4
    }
  ],

  // Kit recomendado (menor preço que atende os requisitos)
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

  // Outros kits em ordem crescente de preço
  "alternativas": [
    {
      "marca": "WEG",
      "bateria_modelo": "SBW CB050 W00",
      "inversor_modelo": "SIW200H M075 W00",
      "qtd_baterias": 1,
      "qtd_inversores": 1,
      "capacidade_total_kwh": 5.02,
      "potencia_total_kw": 7.5,
      "preco_total": 15499.12
    }
  ],

  // Dimensionamento solar (apenas se consumo_medio_mensal_kwh + hsp_media enviados)
  "solar_dimensionamento": null,

  "economia_mensal_rs": null,
  "economia_anual_rs": null
}
```

---

## Tipo 1b — Backup Direto (uso Ploomes)

Use este tipo quando o Ploomes já possui os totais das cargas calculados. Não é necessário enviar a lista de equipamentos.

### Campos específicos

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `total_pp_kva` | float | ✅ | Potência de pico total das cargas (kVA) — soma das colunas Pp |
| `total_e_eps_kwh` | float | ✅ | Energia necessária já escalada pela autonomia (kWh) |
| `tipo_instalacao` | string | ❌ | `"monofasico"` (padrão) ou `"trifasico"` |

### Exemplo de requisição

```json
{
  "origem_info": {
    "origem": "ploomes",
    "negocio_id": "123456",
    "negocio_nome": "Padaria Central",
    "solicitante_id": "rep-001",
    "solicitante_nome": "Carlos Vendas",
    "solicitado_em": "2026-05-19T14:00:00Z"
  },
  "tipo_calculo": "backup_direto",
  "tipo_instalacao": "monofasico",
  "total_pp_kva": 28.8,
  "total_e_eps_kwh": 4.8
}
```

### Diferença em relação ao Tipo 1

| | `backup` | `backup_direto` |
|-|----------|-----------------|
| Envia equipamentos | ✅ `cargas_backup[]` | ❌ |
| Envia totais | ❌ | ✅ `total_pp_kva` + `total_e_eps_kwh` |
| `backup_rows` na resposta | ✅ detalhamento por linha | `null` |
| Kit recomendado | ✅ | ✅ |

### Erros específicos

| Situação | HTTP | Detalhe |
|----------|------|---------|
| `total_pp_kva` ausente | `500` | `"total_pp_kva e total_e_eps_kwh são obrigatórios para backup_direto"` |
| `total_e_eps_kwh` ausente | `500` | `"total_pp_kva e total_e_eps_kwh são obrigatórios para backup_direto"` |
| `total_e_eps_kwh = 0` | `500` | `"total_e_eps_kwh deve ser maior que zero"` |

---

## Tipo 2 — Arbitragem Tarifária

Dimensiona BESS comercial para carregar fora do horário de ponta e descarregar na ponta, reduzindo a fatura.

### Campos específicos

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `consumo_ponta_kwh` | float[12] | ✅ | Consumo na ponta por mês (Janeiro→Dezembro) em kWh |
| `demanda_ponta_kw` | float[12] | ✅ | Demanda medida na ponta por mês em kW |
| `tarifa_ponta_rs_kwh` | float | ✅ | Tarifa do kWh na ponta (R$) |
| `tarifa_fora_ponta_rs_kwh` | float | ✅ | Tarifa do kWh fora da ponta (R$) |

### Exemplo de requisição

```json
{
  "origem_info": {
    "origem": "ploomes",
    "negocio_id": "789012",
    "negocio_nome": "Supermercado XYZ",
    "solicitante_id": "rep-002",
    "solicitante_nome": "Ana Consultora",
    "solicitado_em": "2026-05-19T15:00:00Z"
  },
  "tipo_calculo": "arbitragem",
  "consumo_ponta_kwh": [320, 310, 330, 300, 290, 280, 275, 280, 295, 305, 315, 325],
  "demanda_ponta_kw":  [85, 82, 88, 80, 76, 74, 72, 74, 78, 81, 84, 86],
  "tarifa_ponta_rs_kwh": 2.50,
  "tarifa_fora_ponta_rs_kwh": 0.32
}
```

### Resposta (arbitragem)

```jsonc
{
  "projeto_id": "uuid-do-projeto",
  "tipo_calculo": "arbitragem",
  "origem": "ploomes",
  "negocio_id": "789012",
  "solicitado_em": "2026-05-19T15:00:00Z",
  "calculado_em": "2026-05-19T15:00:01Z",

  "capacidade_kwh": 126.0,   // Capacidade total instalada (kWh)
  "potencia_kw": 0.0,

  // Dimensionamento
  "qty_bess": 14,             // Quantidade de módulos BESS
  "qty_consumo": 14,          // Dimensionado por consumo
  "qty_potencia": 1,          // Dimensionado por demanda
  "avg_consumo_ponta": 300.75, // Média mensal de consumo na ponta (kWh)
  "max_demanda_ponta": 88.0,   // Maior demanda registrada (kW)

  "economia_mensal_rs": 654.83,
  "economia_anual_rs": null,
  "payback_meses": 38.2,

  // Sem kit para arbitragem (produto comercial direto)
  "kit_selecionado": null,
  "alternativas": [],
  "backup_rows": null,
  "solar_dimensionamento": null
}
```

---

## Lógica de seleção de kit (Backup)

O sistema tenta encontrar o kit ideal em 4 passes progressivos:

| Pass | Critério | Descrição |
|------|----------|-----------|
| 1 | Mesma marca + mesma fase + EPS ≥ Pp total | Kit ideal |
| 2 | Mesma marca + mesma fase + qualquer EPS | Relaxa potência EPS |
| 3 | Mesma marca + qualquer fase + qualquer EPS | Relaxa fase |
| 4 | Qualquer marca + qualquer fase + qualquer EPS | Último recurso |

> **Sempre retorna pelo menos o menor kit disponível**, mesmo que nenhum atenda 100% dos requisitos. Isso garante que o vendedor sempre receba uma sugestão comercial.

**Fórmulas do dimensionamento:**
- `Pn (kVA) = ⌈qtd × (Pnom / FP)⌉ / 1000`
- `Pp (kVA) = Pn × IP/IN`
- `E_EPS (kWh) = Pn × T_dia`
- `Capacidade necessária (kWh) = E_EPS_total × autonomia_h / 24`
- `Qtd baterias = ⌈capacidade / (cap_bat × DoD/100)⌉`

---

## Interação automática no Ploomes

Quando `origem = "ploomes"` e `negocio_id` está presente, o sistema posta automaticamente um comentário no negócio com o resumo do dimensionamento:

```
📊 Dimensionamento BESS concluído (BACKUP)
- Capacidade: 4.8 kWh
- Potência: 5.2 kW
- Kit Sugerido: WEG SBW CB050 W00
- Investimento: R$ 14.080,12

👉 Ver detalhes: https://calculadora-meu-bess.vercel.app/projects/<projeto_id>
```

---

## Códigos de resposta

| Código | Situação |
|--------|----------|
| `200 OK` | Cálculo realizado com sucesso |
| `400 Bad Request` | Parâmetros inválidos (ex: `cargas_backup` vazia) |
| `401 Unauthorized` | `X-API-Key` ausente ou incorreta |
| `422 Unprocessable Entity` | Estrutura do JSON inválida (campos faltando ou tipo errado) |
| `500 Internal Server Error` | Erro inesperado no servidor |

---

## Campos do `kit_selecionado` e `alternativas[]`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `marca` | string | Marca do fabricante |
| `bateria_modelo` | string | Modelo da bateria |
| `inversor_modelo` | string | Modelo do inversor híbrido |
| `qtd_baterias` | int | Quantidade de baterias necessárias |
| `qtd_inversores` | int | Quantidade de inversores (sempre 1) |
| `capacidade_total_kwh` | float | Capacidade útil total instalada (kWh) |
| `potencia_total_kw` | float | Potência contínua do inversor (kW) |
| `preco_total` | float | Preço total do kit em R$ |

---

## Campos do `backup_rows[]`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `nome` | string | Nome do equipamento |
| `pn_kva` | float | Potência nominal (kVA) |
| `dmn_kva` | float | Demanda média nominal (kVA) |
| `pp_kva` | float | Potência de pico / partida (kVA) |
| `dmp_kva` | float | Demanda de pico (kVA) |
| `e_eps_kwh` | float | Energia diária que o EPS deve fornecer (kWh) |

---

## Endpoint auxiliar — Consulta de projeto

Retorna os dados de um projeto já calculado. Requer JWT do Supabase (usuário autenticado).

```
GET /projects/{projeto_id}
Authorization: Bearer <supabase-jwt>
```

---

## Valores de referência para `ip_in` por tipo de carga

| Tipo de Equipamento | `fp` típico | `ip_in` típico |
|---------------------|-------------|----------------|
| Iluminação LED | 1.0 | 1.0 |
| Iluminação fluorescente | 0.92 | 1.5 |
| Computador / notebook | 0.85 | 2.0 |
| Geladeira / freezer | 0.92 | 3.0 |
| Ar condicionado | 0.92 | 6.0 |
| Motor bomba | 0.85 | 7.0 |
| Motor industrial | 0.80 | 8.0 |

---

*Documentação gerada em 2026-05-19 — MeuBESS API v1.0*
