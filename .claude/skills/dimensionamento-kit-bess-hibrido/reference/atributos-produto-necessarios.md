# Contrato de dados do produto (marca-agnóstico)

Lista dos atributos que **cada tipo de produto precisa ter cadastrado** para o
dimensionamento de kit funcionar. Para cada um: unidade, se é obrigatório, **por
que** é necessário (qual passo do cálculo consome), **onde aparece no datasheet**
e o valor WEG de exemplo.

Princípio: estes atributos são os mesmos para qualquer marca. Só os **valores**
mudam. Todo atributo abaixo foi confirmado como presente nos datasheets WEG.

---

## Inversor híbrido

| Atributo | Unidade | Obrig. | Por que é necessário | Onde no datasheet | Exemplo WEG |
|---|---|---|---|---|---|
| Potência nominal de saída | kW | Sim | Capacidade contínua; base p/ comparar com consumo médio das cargas normais | "Potência Nominal de Saída" | SIW200H M050 = 5,0 kW |
| Potência de pico (EPS) | kW | Sim | A potência de pico das cargas críticas (`Pp`) deve caber aqui; senão o inversor desarma na partida | "Potência Aparente de Pico de Saída (60s)" | SIW200H M050 = 6,0 kVA @60s |
| Duração do pico | s | Sim | O pico é sustentado por tempo limitado; depois cai p/ a nominal | junto da pot. de pico | 60 s |
| Potência EPS nominal | kW | Sim | Potência contínua disponível na saída de backup (≠ saída on-grid) | "SAÍDA EPS / Potência Aparente Máxima" | SIW200H M050 = 5,0 kVA |
| Tipo de fase | enum (mono/tri/splitphase) | Sim | Define compatibilidade com a instalação e a regra de carga mono em tri | "Tensão Nominal da Rede" (2L+N / 3L+N…) | SIW200H = mono 220 V; SIW400H = tri 380/220 |
| Nº de entradas de bateria | int | Sim | Multiplica o limite de baterias em paralelo (total = entradas × máx-paralelo) | "Número de Entradas de Bateria" | SIW200H = 1; SIW400H = 2 |
| Corrente máx por entrada de bateria | A | Sim | Limita a **potência** entregável por entrada (corrente × tensão); explica a "Tabela EPS" | "Corrente Máxima de Carga/Descarga" | SIW200H = 40 A; SIW400H = 50+50 A |
| Faixa de tensão de bateria aceita | V (min–max) | Sim | A tensão de operação da bateria precisa caber nesta faixa (compatibilidade) | "Tensão da Bateria" / "Faixa de Tensão da Bateria" | SIW200H = 80–480 V; SIW400H = 150–800 V |
| Nº máx de unidades em paralelo | int | Recomendado | Permite escalar potência além de um inversor (soma EPS) | "Operação em Paralelo" | SIW400H = 4; SIW200H mono = 5 (off-grid) |
| Nº de MPPT / strings por MPPT | int | Opcional* | Relevante p/ o lado solar do kit, não p/ a parte BESS | "Nº de Rastreadores MPPT" | SIW200H M050 = 2 MPPT, 1 string/MPPT |

\* MPPT é necessário para dimensionar os módulos FV, não a bateria. Já existe
como `qty_mppt`/`qty_inputs_per_mppt` na réplica.

### Derivados (NÃO são campos de produto — calcule)
- **Máx baterias do inversor** = `entradas_bateria × bateria.max_em_paralelo`.
- **Limite de carga monofásica** (só p/ tri) = `potencia_nominal ÷ 3` → **alerta**.

---

## Bateria

| Atributo | Unidade | Obrig. | Por que é necessário | Onde no datasheet | Exemplo WEG (SBW) |
|---|---|---|---|---|---|
| Capacidade útil | kWh | Sim | Energia realmente usável; base do nº de baterias p/ atender E_BAT | "Energia utilizável" | CB050 = 5,02; CB100 = 10,07 |
| Capacidade nominal | kWh | Opcional | Referência; útil = nominal × DoD | "Energia nominal" | CB050 = 5,18; CB100 = 10,36 |
| DoD (profundidade de descarga) | % | Sim | Converte capacidade nominal em útil; entra no E_BAT | "Profundidade de descarga" | 90 % |
| Máx módulos em paralelo | int | Sim | Limite de baterias por string (somam corrente; exceder danifica) — vem do datasheet DA BATERIA | "Quantidade de Módulos por Sistema: Máximo de N em Paralelo" | 4 em paralelo |
| Corrente máx contínua de carga/descarga | A | Sim | Define a potência contínua que a bateria entrega; com a tensão → C-rate | "Corrente máxima de carga/descarga" | 27 A |
| Corrente de pico de descarga | A (@ s) | Recomendado | Suporta o pico de partida das cargas por curto período | "Corrente de descarga de pico" | 65 A @ 30 s |
| Tensão nominal | V | Sim | Compatibilidade com a faixa de bateria do inversor | "Tensão nominal" | CB050 = 192; CB100 = 384 |
| Faixa de tensão de operação | V (min–max) | Sim | A faixa real precisa caber na faixa aceita pelo inversor | "Tensão de operação" | CB050 = 174–218; CB100 = 348–437 |
| Química | enum (LFP, NMC…) | Opcional | Compatibilidade e perfil de segurança | "Tipo de bateria" | LiFePO4 (LFP) |
| Inversores compatíveis | lista | Recomendado | Fonte autoritativa do par bateria×inversor; mesma marca NÃO garante compatibilidade | "Compatível" | "Todos SIW200H e SIW400H" (outra bateria pode restringir) |

### Derivados (calcule)
- **C-rate** = potência de descarga ÷ capacidade = (corrente × tensão) ÷ capacidade.
  Ex.: 27 A × ~192 V ≈ 5,2 kW ÷ 5,02 kWh ≈ **1 C** (descarrega em ~1 h).
- **Necessita caixa de junção (JBW)** = `baterias_em_paralelo ≥ 2`.

---

## Checagens de compatibilidade kit (inversor × bateria)

1. **Compatibilidade declarada:** se o datasheet da bateria traz a **lista de
   inversores compatíveis**, ela é a fonte autoritativa — o par precisa estar nela.
   **Mesma marca não basta:** há inversores WEG incompatíveis com certos modelos de
   bateria WEG.
2. **Tensão (quando não há lista):** `bateria.faixa_operacao ⊂
   inversor.faixa_tensao_bateria`. Necessária, mas não necessariamente suficiente
   (BMS/protocolo/certificação também contam) — na dúvida, marque p/ revisão.
3. **Contagem:** `n_baterias ≤ inversor.entradas × bateria.max_em_paralelo`.
4. **Potência:** potência entregável = `min(inversor.potencia_pico,
   Σ por entrada de [corrente_max_entrada × tensao_bateria])`. Mais baterias além
   da saturação de corrente da entrada **não** aumentam a potência.

## Lacunas no cadastro atual (`meubess_products`)

Mapeamento para os campos da réplica (ver `../../../../backend/app/catalog/models.py`):

| Atributo necessário | Campo em meubess_products | Status |
|---|---|---|
| Inversor: potência nominal | `max_output_power` (ou `power`) | ✅ existe |
| Inversor: potência EPS | `max_eps_power` | ✅ existe |
| Inversor: nº entradas de bateria | `battery_inputs` | ✅ existe |
| Inversor: fase | `phase` | ✅ existe |
| Inversor: MPPT | `qty_mppt`, `qty_inputs_per_mppt` | ✅ existe |
| Inversor: **potência de pico + duração** | — | ⚠️ a adicionar |
| Inversor: **corrente máx por entrada** | — | ⚠️ a adicionar |
| Inversor: **faixa de tensão de bateria** | parcial (`voltage` é da rede, não da bateria) | ⚠️ a adicionar |
| Inversor: **máx unidades em paralelo** | — | ⚠️ a adicionar |
| Bateria: **capacidade útil / nominal** | — | ⚠️ a adicionar |
| Bateria: **DoD** | — | ⚠️ a adicionar |
| Bateria: **máx em paralelo** | — | ⚠️ a adicionar |
| Bateria: **corrente máx contínua/pico** | — | ⚠️ a adicionar |
| Bateria: **tensão nominal/faixa** | — | ⚠️ a adicionar |
| Bateria: química | — | opcional |

**Recomendação:** os campos ⚠️ devem ser criados no cadastro da plataforma MeuBESS
(todos existem nos datasheets, logo são cadastráveis). Enquanto não existirem, a
lógica de kit deve tratá-los como ausentes e **sinalizar** a lacuna (marcar o
produto como "precisa revisão técnica"), nunca assumir um default que mascare o
risco de um kit fisicamente inviável.
