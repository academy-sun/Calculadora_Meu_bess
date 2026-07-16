# API MeuBESS — Documentação Completa

> **Base URL (produção):** `https://calculadorameubess-production.up.railway.app`

> ⚠️ **Integração com o Ploomes:** o fluxo de fórmula integrada descrito aqui é
> **legado**. A integração atual (embed via campo desenvolvedor + write-back)
> está documentada em [integracao-ploomes-v2.md](integracao-ploomes-v2.md).

---

## Sumário

- [Autenticação](#autenticação)
- [POST /calculate](#post-calculate)
  - [Tipo 1 — Backup de Energia](#tipo-1--backup-de-energia)
  - [Tipo 1b — Backup Direto (Ploomes)](#tipo-1b--backup-direto-ploomes)
  - [Tipo 2 — Arbitragem Tarifária](#tipo-2--arbitragem-tarifária)
  - [Tipo 3 — Peak Shaving](#tipo-3--peak-shaving)
  - [Tipo 4 — Solar / Solar + Storage](#tipo-4--solar--solar--storage)
- [GET /projects](#get-projects)
- [GET /projects/{id}](#get-projectsid)
- [DELETE /projects/{id}](#delete-projectsid)
- [DELETE /projects (bulk)](#delete-projects-bulk)
- [GET /catalog/bess](#get-catalogbess)
- [POST /catalog/bess](#post-catalogbess)
- [PUT /catalog/bess/{id}](#put-catalogbessid)
- [DELETE /catalog/bess/{id}](#delete-catalogbessid)
- [GET /catalog/solar](#get-catalogsolar)
- [POST /catalog/solar](#post-catalogsolar)
- [PUT /catalog/solar/{id}](#put-catalogsolarid)
- [DELETE /catalog/solar/{id}](#delete-catalogsolarid)
- [GET /catalog/loads](#get-catalogloads)
- [POST /catalog/loads](#post-catalogloads)
- [PUT /catalog/loads/{id}](#put-catalogloadsid)
- [DELETE /catalog/loads/{id}](#delete-catalogloadsid)
- [POST /catalog/sync](#post-catalogsync)
- [GET /catalog/sync/status](#get-catalogsyncstatus)
- [GET /health](#get-health)
- [Lógica de seleção de kit (Backup)](#lógica-de-seleção-de-kit-backup)
- [Interação automática no Ploomes](#interação-automática-no-ploomes)
- [Códigos de resposta](#códigos-de-resposta)
- [Referências](#referências)

---

## Autenticação

A API usa dois mecanismos de autenticação dependendo do endpoint:

| Mecanismo | Header | Onde usar |
|-----------|--------|-----------|
| **API Key** | `X-API-Key: <chave>` | `POST /calculate` |
| **JWT Supabase** | `Authorization: Bearer <token>` | `/projects`, `/catalog` (leitura) |
| **JWT Admin** | `Authorization: Bearer <token>` (role=admin) | `/catalog` (escrita), `/catalog/sync` |

A API Key é configurada na variável de ambiente `API_KEY_PLOOMES` no Railway. Qualquer requisição ao `/calculate` sem a chave correta retorna `401 Unauthorized`.

---

## POST `/calculate`

Endpoint principal de dimensionamento. Recebe parâmetros de projeto, calcula o sistema BESS ideal, salva o projeto no banco e retorna o resultado completo.

### Headers

| Header | Obrigatório | Valor |
|--------|-------------|-------|
| `Content-Type` | ✅ | `application/json` |
| `X-API-Key` | ✅ | Chave da integração Ploomes |

### Campos comuns (todos os tipos)

```jsonc
{
  "origem_info": {
    "origem": "ploomes",           // "ploomes" | "interno"
    "negocio_id": "123456",        // ID do negócio no Ploomes (string, opcional)
    "negocio_nome": "Empresa ABC", // Nome do negócio (exibido no histórico, opcional)
    "solicitante_id": "user-uuid", // ID do usuário que disparou (obrigatório)
    "solicitante_nome": "João",    // Nome exibido (obrigatório)
    "solicitado_em": "2026-05-19T14:00:00Z" // ISO 8601 UTC (obrigatório)
  },
  "tipo_calculo": "backup"  // ver seções abaixo
}
```

### Tipos de cálculo disponíveis

| `tipo_calculo` | Descrição |
|----------------|-----------|
| `"backup"` | Backup com lista de equipamentos brutos |
| `"backup_direto"` | Backup com totais pré-calculados (uso Ploomes) |
| `"arbitragem"` | Arbitragem tarifária ponta/fora-ponta |
| `"peak_shaving"` | Corte de demanda de ponta |
| `"solar"` | Dimensionamento fotovoltaico puro |
| `"solar_storage"` | Fotovoltaico + armazenamento |

---

## Tipo 1 — Backup de Energia

Dimensiona bateria + inversor híbrido para garantir autonomia na falta de energia. O backend calcula Pn, Pp, E_EPS por equipamento antes de selecionar o kit.

### Campos específicos

| Campo | Tipo | Obrigatório | Padrão | Descrição |
|-------|------|-------------|--------|-----------|
| `tipo_instalacao` | string | ✅ | — | `"monofasico"` ou `"trifasico"` |
| `cargas_backup` | array | ✅ | — | Lista de equipamentos a proteger |
| `autonomia_horas` | float | ❌ | `4.0` | Horas de autonomia desejada |
| `dod_percent` | float | ❌ | `90.0` | Profundidade de descarga (0–100) |
| `eficiencia_roundtrip` | float | ❌ | `90.0` | Eficiência do ciclo (0–100) |
| `consumo_medio_mensal_kwh` | float | ❌ | — | Para dimensionamento solar opcional |
| `hsp_media` | float | ❌ | — | Horas de Sol Pleno da cidade (kWh/m²/dia) |

### Objeto `cargas_backup[]`

| Campo | Tipo | Obrigatório | Padrão | Descrição |
|-------|------|-------------|--------|-----------|
| `nome` | string | ✅ | — | Nome do equipamento |
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

  "capacidade_kwh": 4.8,    // Energia necessária (kWh) para a janela de autonomia
  "potencia_kw": 5.2,       // Potência de pico total das cargas (kW)
  "payback_meses": null,    // Sempre null para backup

  // Totais calculados da tabela de cargas
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

## Tipo 1b — Backup Direto (Ploomes)

Versão simplificada do backup para uso exclusivo do Ploomes. O Ploomes já possui os totais calculados da tabela de cargas — este tipo pula o recálculo e chama a seleção de kit diretamente.

**Quando usar:** sempre que o Ploomes já tiver `total_pp_kva` e `total_e_eps_kwh` disponíveis no negócio. Evita reenviar todos os equipamentos individualmente.

### Diferença em relação ao `backup`

| | `backup` | `backup_direto` |
|---|---|---|
| Entrada | Lista de equipamentos brutos | Totais pré-calculados |
| Cálculo de Pn, Pp, E_EPS | Feito pelo backend | Feito pelo Ploomes |
| `backup_rows` na resposta | Preenchido | `null` |
| `total_pn_kva`, `total_dmn_kva` | Preenchidos | `null` |

### Campos específicos

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `tipo_instalacao` | string | ❌ | `"monofasico"` (padrão) ou `"trifasico"` |
| `total_pp_kva` | float | ✅ | Potência de pico total das cargas (kVA) |
| `total_e_eps_kwh` | float | ✅ | Energia total necessária — já escalada para a janela de autonomia (kWh) |

### Exemplo de requisição

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

### Resposta (backup_direto)

Mesmo shape do `backup` normal. Campos exclusivos da tabela de cargas ficam `null`:

```jsonc
{
  "projeto_id": "uuid-do-projeto",
  "tipo_calculo": "backup_direto",
  "origem": "ploomes",
  "negocio_id": "123456",
  "solicitado_em": "2026-05-19T14:00:00Z",
  "calculado_em": "2026-05-19T14:00:01Z",

  "capacidade_kwh": 4.8,
  "potencia_kw": 28.8,
  "payback_meses": null,

  // Null — não há recálculo por equipamento
  "backup_rows": null,
  "total_pn_kva": null,
  "total_dmn_kva": null,
  "total_pp_kva": null,
  "total_dmp_kva": null,

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
  "alternativas": [],

  "solar_dimensionamento": null,
  "economia_mensal_rs": null,
  "economia_anual_rs": null
}
```

### Validação e erros

| Situação | HTTP | Mensagem |
|----------|------|---------|
| `total_pp_kva` ausente | `400` | `"total_pp_kva e total_e_eps_kwh são obrigatórios para backup_direto"` |
| `total_e_eps_kwh` ausente | `400` | `"total_pp_kva e total_e_eps_kwh são obrigatórios para backup_direto"` |
| `total_e_eps_kwh <= 0` | `400` | `"total_e_eps_kwh deve ser maior que zero"` |
| Nenhum kit no catálogo | `200` | `kit_selecionado: null` — dado de negócio, não erro de API |

---

## Tipo 2 — Arbitragem Tarifária

Dimensiona BESS comercial para carregar fora do horário de ponta e descarregar na ponta, reduzindo a fatura de energia.

### Campos específicos

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `consumo_ponta_kwh` | float[12] | ✅ | Consumo na ponta por mês (Jan→Dez) em kWh |
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

  "capacidade_kwh": 126.0,  // Capacidade total instalada (kWh)
  "potencia_kw": 0.0,

  // Dimensionamento
  "qty_bess": 14,              // Quantidade de módulos BESS necessários
  "qty_consumo": 14,           // Módulos dimensionados por consumo
  "qty_potencia": 1,           // Módulos dimensionados por demanda
  "avg_consumo_ponta": 300.75, // Média mensal de consumo na ponta (kWh)
  "max_demanda_ponta": 88.0,   // Maior demanda registrada nos 12 meses (kW)

  "economia_mensal_rs": 654.83,
  "economia_anual_rs": null,
  "payback_meses": 38.2,

  // Sem kit individual para arbitragem (produto comercial modular)
  "kit_selecionado": null,
  "alternativas": [],
  "backup_rows": null,
  "solar_dimensionamento": null,
  "total_pn_kva": null,
  "total_dmn_kva": null,
  "total_pp_kva": null,
  "total_dmp_kva": null
}
```

---

## Tipo 3 — Peak Shaving

Dimensiona BESS para cortar a demanda de ponta, reduzindo a parcela de demanda na fatura.

### Campos específicos

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `curva_carga_kw` | float[24] | ❌* | Curva de carga horária (24 pontos, kW) |
| `cargas` | array | ❌* | Lista de cargas para gerar curva sintética |
| `demanda_alvo_kw` | float | ✅ | Demanda máxima desejada após corte (kW) |
| `tarifa_demanda_rs_kw` | float | ✅ | Tarifa de demanda contratada (R$/kW) |

> *Enviar `curva_carga_kw` **ou** `cargas` — pelo menos um é necessário.

### Objeto `cargas[]` (para gerar curva sintética)

| Campo | Tipo | Obrigatório | Padrão | Descrição |
|-------|------|-------------|--------|-----------|
| `nome` | string | ✅ | — | Nome da carga |
| `potencia_w` | float | ✅ | — | Potência em Watts |
| `quantidade` | int | ❌ | `1` | Quantidade de unidades |
| `horas_uso_dia` | float | ✅ | — | Horas de uso por dia |

### Exemplo de requisição

```json
{
  "origem_info": {
    "origem": "interno",
    "solicitante_id": "usr-123",
    "solicitante_nome": "Técnico",
    "solicitado_em": "2026-05-19T10:00:00Z"
  },
  "tipo_calculo": "peak_shaving",
  "curva_carga_kw": [10, 10, 10, 10, 10, 12, 20, 35, 42, 45, 44, 43,
                     40, 41, 44, 46, 45, 38, 30, 25, 20, 15, 12, 10],
  "demanda_alvo_kw": 35.0,
  "tarifa_demanda_rs_kw": 45.0
}
```

### Resposta (peak_shaving)

```jsonc
{
  "projeto_id": "uuid-do-projeto",
  "tipo_calculo": "peak_shaving",
  "capacidade_kwh": 22.0,
  "potencia_kw": 11.0,
  "kit_selecionado": { /* KitInfo */ },
  "alternativas": [],
  "economia_mensal_rs": 495.0,
  "payback_meses": 28.5,
  "backup_rows": null,
  "solar_dimensionamento": null
}
```

---

## Tipo 4 — Solar / Solar + Storage

Dimensiona sistema fotovoltaico. `"solar_storage"` inclui armazenamento BESS.

### Campos específicos

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `irradiacao_kwh_m2_dia` | float | ✅ | Irradiação solar local (kWh/m²/dia) |
| `area_disponivel_m2` | float | ✅ | Área disponível para os painéis (m²) |
| `curva_carga_kw` | float[24] | ❌ | Curva de consumo horária (para base de cálculo) |
| `cargas` | array | ❌ | Alternativo à curva de carga |

### Exemplo de requisição

```json
{
  "origem_info": {
    "origem": "interno",
    "solicitante_id": "usr-123",
    "solicitante_nome": "Técnico",
    "solicitado_em": "2026-05-19T10:00:00Z"
  },
  "tipo_calculo": "solar_storage",
  "irradiacao_kwh_m2_dia": 5.2,
  "area_disponivel_m2": 80.0,
  "curva_carga_kw": [5, 5, 5, 5, 5, 6, 10, 18, 22, 24, 23, 22,
                     21, 22, 23, 24, 23, 19, 14, 11, 9, 7, 6, 5]
}
```

---

## GET `/projects`

Lista os projetos do usuário autenticado. Admins veem todos os projetos.

### Headers

| Header | Obrigatório | Valor |
|--------|-------------|-------|
| `Authorization` | ✅ | `Bearer <supabase-jwt>` |

### Query Parameters

| Parâmetro | Tipo | Padrão | Descrição |
|-----------|------|--------|-----------|
| `origem` | string | — | Filtrar por origem (`"ploomes"` ou `"interno"`) |
| `negocio_id` | string | — | Filtrar por ID do negócio Ploomes |
| `limit` | int | `50` | Máximo de registros retornados |

### Exemplo

```
GET /projects?origem=ploomes&negocio_id=123456&limit=10
Authorization: Bearer <jwt>
```

### Resposta

```jsonc
[
  {
    "id": "uuid",
    "tipo_calculo": "backup_direto",
    "estado": "concluido",
    "versao": 1,
    "origem": "ploomes",
    "negocio_id": "123456",
    "negocio_nome": "Empresa ABC",
    "solicitante_id": "rep-001",
    "solicitante_nome": "João Vendas",
    "solicitado_em": "2026-05-19T14:00:00Z",
    "calculado_em": "2026-05-19T14:00:01Z",
    "parametros": { /* dados completos do projeto incluindo kit */ }
  }
]
```

---

## GET `/projects/{id}`

Retorna os dados de um projeto específico.

### Headers

| Header | Obrigatório | Valor |
|--------|-------------|-------|
| `Authorization` | ✅ | `Bearer <supabase-jwt>` |

### Resposta

```jsonc
{
  "id": "uuid",
  "tipo_calculo": "backup",
  "estado": "concluido",
  "versao": 1,
  "origem": "ploomes",
  "negocio_id": "123456",
  "negocio_nome": "Padaria Central",
  "solicitante_id": "rep-001",
  "solicitante_nome": "Carlos Vendas",
  "solicitado_em": "2026-05-19T14:00:00Z",
  "calculado_em": "2026-05-19T14:00:01Z",
  "parametros": { /* todos os parâmetros e resultados */ }
}
```

| Código | Situação |
|--------|----------|
| `200` | Projeto encontrado |
| `404` | Projeto não encontrado |

---

## DELETE `/projects/{id}`

Exclui um projeto. O usuário pode excluir apenas seus próprios projetos; admins podem excluir qualquer um.

### Headers

| Header | Obrigatório | Valor |
|--------|-------------|-------|
| `Authorization` | ✅ | `Bearer <supabase-jwt>` |

| Código | Situação |
|--------|----------|
| `204` | Excluído com sucesso |
| `403` | Sem permissão |
| `404` | Não encontrado |

---

## DELETE `/projects` (bulk)

Exclui múltiplos projetos em uma única requisição.

### Headers

| Header | Obrigatório | Valor |
|--------|-------------|-------|
| `Authorization` | ✅ | `Bearer <supabase-jwt>` |
| `Content-Type` | ✅ | `application/json` |

### Body

```json
{
  "ids": ["uuid-1", "uuid-2", "uuid-3"]
}
```

### Resposta

```json
{
  "deleted": ["uuid-1", "uuid-2"],
  "forbidden": ["uuid-3"]
}
```

---

## GET `/catalog/bess`

Lista todos os produtos BESS (baterias e inversores híbridos) do catálogo.

### Headers

| Header | Obrigatório | Valor |
|--------|-------------|-------|
| `Authorization` | ✅ | `Bearer <supabase-jwt>` |

### Resposta — campos de `ProductBESSRead`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | uuid | ID do produto |
| `marca` | string | Fabricante |
| `modelo` | string | Código do modelo |
| `tipo` | string | `"bateria"` ou `"inversor_hibrido"` |
| `capacidade_kwh` | float\|null | Capacidade total (kWh). Quando `dod_percent` é null, já representa energia útil |
| `dod_percent` | float\|null | Profundidade de descarga (%). **null** = `capacidade_kwh` já é energia útil (convenção produtos sincronizados) |
| `potencia_continua_kw` | float\|null | Potência contínua (kW) — inversores |
| `pot_ca_max_eps_kva` | float\|null | Potência máxima EPS (kVA) — inversores |
| `fase` | string\|null | `"monofasico"` ou `"trifasico"` |
| `preco` | float\|null | Preço unitário (R$) |
| `disponivel` | bool | Disponível para dimensionamento |

> **Nota `dod_percent`:** Produtos sincronizados da plataforma meubess.com.br chegam com `dod_percent = null`. Nesse caso, o motor de seleção trata `capacidade_kwh` como energia 100% utilizável (comportamento correto, pois a plataforma já fornece a capacidade útil).

---

## POST `/catalog/bess`

Cria um novo produto BESS manualmente. Requer perfil **admin**.

### Headers

| Header | Obrigatório | Valor |
|--------|-------------|-------|
| `Authorization` | ✅ | `Bearer <admin-jwt>` |
| `Content-Type` | ✅ | `application/json` |

### Body (ProductBESSCreate)

```json
{
  "marca": "WEG",
  "modelo": "SBW CB050 W00",
  "tipo": "bateria",
  "capacidade_kwh": 5.02,
  "dod_percent": 100,
  "potencia_continua_kw": null,
  "pot_ca_max_eps_kva": null,
  "fase": null,
  "preco": 8500.00,
  "disponivel": true
}
```

| Código | Situação |
|--------|----------|
| `201` | Criado com sucesso |
| `422` | Campos inválidos |

---

## PUT `/catalog/bess/{id}`

Atualiza um produto BESS existente. Requer perfil **admin**.

Body: mesmo formato do `POST /catalog/bess`.

| Código | Situação |
|--------|----------|
| `200` | Atualizado |
| `404` | Não encontrado |

---

## DELETE `/catalog/bess/{id}`

Remove um produto BESS. Requer perfil **admin**.

| Código | Situação |
|--------|----------|
| `204` | Removido |
| `404` | Não encontrado |

---

## GET `/catalog/solar`

Lista os módulos fotovoltaicos disponíveis.

### Headers

| Header | Obrigatório | Valor |
|--------|-------------|-------|
| `Authorization` | ✅ | `Bearer <supabase-jwt>` |

---

## POST `/catalog/solar`

Cria um módulo solar. Requer **admin**.

### Body (ProductSolarCreate)

```json
{
  "marca": "Canadian Solar",
  "modelo": "CS3W-450P",
  "tipo": "modulo_fv",
  "potencia_wp": 450,
  "voc_v": 49.2,
  "vmp_v": 41.5,
  "isc_a": 11.3,
  "imp_a": 10.8,
  "preco": 850.00,
  "disponivel": true
}
```

---

## PUT `/catalog/solar/{id}`

Atualiza um módulo solar. Requer **admin**.

Body: mesmo formato do `POST /catalog/solar`.

| Código | Situação |
|--------|----------|
| `200` | Atualizado |
| `404` | Não encontrado |

---

## DELETE `/catalog/solar/{id}`

Remove um módulo solar. Requer **admin**.

| Código | Situação |
|--------|----------|
| `204` | Removido |
| `404` | Não encontrado |

---

## GET `/catalog/loads`

Lista as cargas padrão do catálogo (usadas para preencher a tabela de equipamentos no frontend).

### Headers

| Header | Obrigatório | Valor |
|--------|-------------|-------|
| `Authorization` | ✅ | `Bearer <supabase-jwt>` |

### Resposta — campos de `StandardLoadRead`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | uuid | ID |
| `nome` | string | Nome do equipamento |
| `pnom_w` | float | Potência nominal (W) |
| `fp` | float | Fator de potência típico |
| `ip_in` | float | Relação corrente de partida |
| `categoria` | string | Categoria (ex: refrigeração, iluminação) |

---

## POST `/catalog/loads`

Cria uma carga padrão. Requer **admin**.

### Body (StandardLoadCreate)

```json
{
  "nome": "Ar condicionado 12.000 BTU",
  "pnom_w": 1100,
  "fp": 0.92,
  "ip_in": 6.0,
  "categoria": "climatizacao"
}
```

| Código | Situação |
|--------|----------|
| `201` | Criado |
| `422` | Campos inválidos |

---

## PUT `/catalog/loads/{id}`

Atualiza uma carga padrão. Requer **admin**.

Body: mesmo formato do `POST /catalog/loads`.

| Código | Situação |
|--------|----------|
| `200` | Atualizado |
| `404` | Não encontrado |

---

## DELETE `/catalog/loads/{id}`

Remove uma carga padrão. Requer **admin**.

| Código | Situação |
|--------|----------|
| `204` | Removido |
| `404` | Não encontrado |

---

## POST `/catalog/sync`

Sincroniza o catálogo completo da plataforma meubess.com.br para o banco de dados local. Faz upsert em `products_bess` ou `products_solar` conforme o tipo do produto. Requer **admin**.

> **Importante:** Produtos sincronizados chegam com `dod_percent = null`. O motor de seleção trata isso corretamente — veja a nota em [GET /catalog/bess](#get-catalogbess).

### Headers

| Header | Obrigatório | Valor |
|--------|-------------|-------|
| `Authorization` | ✅ | `Bearer <admin-jwt>` |

### Resposta

```json
{
  "upserted_bess": 42,
  "upserted_solar": 8,
  "errors": []
}
```

| Código | Situação |
|--------|----------|
| `200` | Sincronização concluída |
| `503` | Falha ao acessar a plataforma de origem |

---

## GET `/catalog/sync/status`

Verifica a configuração da sincronização sem fazer requisições externas. Requer **admin**.

### Resposta

```json
{
  "api_key_configured": true,
  "api_key_preview": "sk-abc123…",
  "api_url": "https://plataforma.meubess.com.br"
}
```

---

## GET `/health`

Verifica se o servidor está em pé. Sem autenticação.

```
GET /health
→ 200 OK
{ "status": "ok" }
```

---

## Lógica de seleção de kit (Backup)

O sistema tenta encontrar o kit ideal em 4 passes progressivos, garantindo que **sempre retorne pelo menos o menor kit disponível**:

| Pass | Critério | Descrição |
|------|----------|-----------|
| 1 | Mesma marca + mesma fase + EPS ≥ Pp total | Kit ideal |
| 2 | Mesma marca + mesma fase + qualquer EPS | Relaxa potência EPS |
| 3 | Mesma marca + qualquer fase + qualquer EPS | Relaxa fase |
| 4 | Qualquer marca + qualquer fase + qualquer EPS | Último recurso |

> Isso garante que o vendedor **sempre receba uma sugestão comercial**, mesmo que nenhum kit atenda 100% dos requisitos técnicos.

**Fórmulas do dimensionamento (`backup` com lista de cargas):**

```
Pn (kVA)         = qtd × (Pnom / FP) / 1000
DMn (kVA)        = Pn × FD
Pp (kVA)         = Pn × (IP/IN)
DMp (kVA)        = DMn × (IP/IN)
E_EPS (kWh)      = Pn × T_dia

Capacidade (kWh) = Σ E_EPS × autonomia_h / 24
Qtd baterias     = ⌈capacidade / (cap_bat × DoD/100)⌉
```

> **`backup_direto`:** Pula todo esse cálculo. `total_pp_kva` e `total_e_eps_kwh` são usados diretamente.

---

## Interação automática no Ploomes

Quando `origem = "ploomes"` e `negocio_id` está presente, o sistema posta automaticamente um comentário no negócio Ploomes após o cálculo (de forma assíncrona, sem bloquear a resposta):

```
📊 Dimensionamento BESS concluído (BACKUP_DIRETO)
- Capacidade: 4.8 kWh
- Potência: 28.8 kW
- Kit Sugerido: WEG SBW CB050 W00
- Investimento: R$ 14.080,12

👉 Ver detalhes: https://calculadora-meu-bess.vercel.app/projects/<projeto_id>
```

---

## Códigos de resposta

| Código | Situação |
|--------|----------|
| `200 OK` | Cálculo ou consulta realizada com sucesso |
| `201 Created` | Recurso criado com sucesso |
| `204 No Content` | Operação de exclusão concluída |
| `400 Bad Request` | Parâmetros de negócio inválidos (ex: `total_e_eps_kwh <= 0`, `cargas_backup` vazia) |
| `401 Unauthorized` | `X-API-Key` ausente/incorreta ou JWT ausente |
| `403 Forbidden` | JWT válido mas sem permissão para o recurso |
| `404 Not Found` | Recurso não encontrado |
| `422 Unprocessable Entity` | Estrutura do JSON inválida (campos faltando ou tipo errado) |
| `500 Internal Server Error` | Erro inesperado no servidor |
| `503 Service Unavailable` | Falha ao acessar serviço externo (ex: sync de catálogo) |

---

## Referências

### Campos do `kit_selecionado` e `alternativas[]`

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

### Campos do `backup_rows[]`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `nome` | string | Nome do equipamento |
| `pn_kva` | float | Potência nominal (kVA) |
| `dmn_kva` | float | Demanda média nominal (kVA) |
| `pp_kva` | float | Potência de pico / partida (kVA) |
| `dmp_kva` | float | Demanda de pico (kVA) |
| `e_eps_kwh` | float | Energia diária que o EPS deve fornecer (kWh) |

### Valores de referência para `ip_in` por tipo de carga

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

*Documentação gerada em 2026-05-20 — MeuBESS API v1.1*
