# Design: Dimensionamento de Módulos Solares no Backup

**Data:** 2026-04-24  
**Status:** Aprovado  
**Escopo:** Adicionar etapa de dimensionamento FV ao fluxo de cálculo Backup existente

---

## 1. Visão Geral

O dimensionamento solar entra como **etapa 2 do Backup**, executada logo após a seleção do kit BESS (bateria + inversor híbrido). O fluxo completo fica:

```
Cargas → E_bat → Kit BESS (bateria + inversor) → [NOVO] Solar (módulos + strings)
```

O solar é **opcional**: se o usuário não preencher consumo mensal e cidade, `solar_result` retorna `null` e projetos existentes não são afetados.

---

## 2. Novos Campos nos Catálogos

### 2.1 `products_bess` — Inversores Híbridos (4 campos)

| Campo | Tipo SQL | Descrição |
|---|---|---|
| `mppt_v_min` | FLOAT | Tensão mínima de entrada MPPT (V) |
| `mppt_v_max` | FLOAT | Tensão máxima de entrada MPPT (V) |
| `mppt_i_max_a` | FLOAT | Corrente máxima por entrada MPPT (A) |
| `mppt_qty` | INTEGER | Número de entradas MPPT |

### 2.2 `products_solar` — Módulos FV (4 campos)

| Campo | Tipo SQL | Descrição |
|---|---|---|
| `voc_v` | FLOAT | Tensão de circuito aberto (V) |
| `vmp_v` | FLOAT | Tensão no ponto de máxima potência (V) |
| `isc_a` | FLOAT | Corrente de curto-circuito (A) |
| `imp_a` | FLOAT | Corrente no ponto de máxima potência (A) |

Todos nullable — não quebra registros existentes. Módulos/inversores sem esses dados são ignorados no string sizing.

---

## 3. Algoritmo de Dimensionamento

### 3.1 Fórmula base

```
kWp_necessário = consumo_medio_mensal_kwh / (HSP_media × 0.8 × 30)
```

### 3.2 String Sizing (por módulo do catálogo)

Para cada módulo FV disponível no catálogo com `voc_v`, `vmp_v`, `isc_a`, `imp_a` preenchidos:

**Passo 1 — Verificar compatibilidade com o inversor selecionado:**
```
n_serie_min = ceil(mppt_v_min / vmp_v)
n_serie_max = floor(mppt_v_max / voc_v)   # usa Voc para segurança
```
- Se `n_serie_min > n_serie_max` → módulo incompatível com este inversor → descarta

**Passo 2 — Calcular configuração ótima:**
```
n_serie = n_serie_max                               # maximiza tensão → melhor eficiência
n_paralelo_max = floor(mppt_i_max_a / imp_a)        # limite de corrente por MPPT
n_strings_necessarias = ceil(kWp_necessário × 1000 / (n_serie × potencia_pico_wp))
n_paralelo = ceil(n_strings_necessarias / mppt_qty) # distribui pelas entradas MPPT
n_paralelo = min(n_paralelo, n_paralelo_max)        # respeita limite de corrente (capa)
```

**Passo 3 — Resultado para este módulo:**
```
qty_modulos    = n_serie × n_paralelo × mppt_qty
kWp_instalado  = qty_modulos × potencia_pico_wp / 1000
cobertura_pct  = (kWp_instalado × HSP_media × 0.8 × 30) / consumo_medio_mensal × 100
```

### 3.3 Seleção do melhor módulo

Todos os módulos compatíveis são rankeados por:
1. Prioridade: `kWp_instalado` mais próximo de `kWp_necessário` (sem ultrapassar por mais de 20%)
2. Empate: menor custo total (`qty_modulos × preco`)

Se nenhum módulo atingir 100% de cobertura, seleciona o que maximiza `kWp_instalado` dentro dos limites do inversor. O `cobertura_pct` no resultado informa o usuário da cobertura parcial.

---

## 4. API

### 4.1 `CalculateRequest` — campos novos (opcionais)

```python
consumo_medio_mensal_kwh: Optional[float] = None  # kWh/mês informado pelo usuário
hsp_media: Optional[float] = None                 # HSP extraído do JSON de cidades no frontend
```

### 4.2 `CalculateResponse` — novo campo

```python
class SolarDimensionamento(BaseModel):
    modulo_marca: str
    modulo_modelo: str
    modulo_wp: float
    qty_modulos: int
    n_serie: int           # módulos por string
    n_paralelo: int        # strings por entrada MPPT
    mppt_qty: int          # entradas MPPT utilizadas
    kwp_instalado: float
    cobertura_pct: float   # % do consumo mensal coberto

# Em CalculateResponse:
solar_dimensionamento: Optional[SolarDimensionamento] = None
```

---

## 5. Dados de Irradiação (Cidades)

**Fonte:** arquivo `irradiacao.txt` fornecido (~5.500 municípios brasileiros)  
**Formato original:** JS array com objetos `{ Nome, Estado, Sigla, "Mês a mês" }`  
**Campo usado:** último valor do "Mês a mês" = MÉDIA anual (HSP)

**Processamento:** script Python gera `frontend/src/data/irradiacao.json`:
```json
[
  { "nome": "ABADIA DE GOIÁS", "estado": "GOIÁS", "sigla": "GO", "hsp": 5.26 },
  ...
]
```

**Autocomplete:** busca local no frontend (sem requisição ao backend), filtra por nome da cidade ou sigla do estado.

---

## 6. Frontend

### 6.1 Formulário Backup (`NewProjectPage.tsx`)

Dois novos campos **opcionais** abaixo da seção de autonomia:

- **Consumo médio mensal (kWh):** input numérico
- **Cidade:** combobox com busca por digitação, exibe `"NOME DA CIDADE - UF"`, armazena o `hsp` da cidade selecionada internamente

Ambos devem ser preenchidos para o solar ser calculado. Se apenas um for preenchido, o sistema ignora a etapa solar (não envia os campos no payload).

### 6.2 Resultado do Backup

Nova seção **"Dimensionamento Solar"** exibida abaixo do kit BESS, somente quando `solar_dimensionamento` vier preenchido na response:

```
☀️ Dimensionamento Solar
Módulo selecionado:   [Marca] [Modelo] — [Wp] Wp
Configuração:         [n_serie]S × [n_paralelo]P × [mppt_qty] MPPT
Total de módulos:     [qty_modulos] unidades
Potência instalada:   [kwp_instalado] kWp
Cobertura estimada:   [cobertura_pct]% do consumo mensal
```

### 6.3 Catálogo Admin

Os novos campos MPPT e elétricos aparecem nos formulários de edição dos catálogos:
- `CatalogBESSPage` — 4 novos campos numéricos para inversores híbridos
- `CatalogSolarPage` — 4 novos campos numéricos para módulos FV

---

## 7. Arquivos a Criar / Modificar

| Arquivo | Ação |
|---|---|
| `backend/migrations/007_solar_mppt_fields.sql` | Criar — migration com os 8 novos campos |
| `backend/app/engines/solar_strings.py` | Criar — função `size_solar_strings()` |
| `backend/app/calculate/schemas.py` | Modificar — `SolarDimensionamento`, 2 campos em `CalculateRequest`, 1 em `CalculateResponse` |
| `backend/app/calculate/service.py` | Modificar — chamar `size_solar_strings()` após `find_compatible_kits()` |
| `backend/app/catalog/schemas.py` | Modificar — 4 campos novos em `ProductBESSCreate/Read` e `ProductSolarCreate/Read` |
| `backend/app/catalog/models.py` | Modificar — 4 campos novos em `ProductBESS` e `ProductSolar` |
| `frontend/scripts/generate_irradiacao.py` | Criar — script que gera o JSON das cidades |
| `frontend/src/data/irradiacao.json` | Criar — ~5.500 cidades com HSP |
| `frontend/src/pages/NewProjectPage.tsx` | Modificar — 2 novos campos no form Backup |
| `frontend/src/pages/CatalogBESSPage.tsx` | Modificar — 4 campos MPPT no form de inversor |
| `frontend/src/pages/CatalogSolarPage.tsx` | Modificar — 4 campos elétricos no form de módulo |
| `frontend/src/types/index.ts` | Modificar — campos novos em `ProductBESS`, `ProductSolar`, tipos de response |

---

## 8. Restrições e Casos de Borda

- **Inversor sem dados MPPT:** se o inversor do kit selecionado não tiver `mppt_v_min/max/i_max_a/mppt_qty` preenchidos, `solar_dimensionamento` retorna `null` com mensagem `"Inversor sem dados MPPT cadastrados"`
- **Nenhum módulo compatível:** se nenhum módulo do catálogo for compatível com o inversor, retorna `null` com mensagem `"Nenhum módulo FV compatível no catálogo"`
- **Cobertura parcial:** quando o inversor não suporta kWp suficiente, retorna o máximo possível com `cobertura_pct < 100`
- **Solar não solicitado:** se `consumo_medio_mensal_kwh` ou `hsp_media` for `null`, pula toda a etapa solar silenciosamente
