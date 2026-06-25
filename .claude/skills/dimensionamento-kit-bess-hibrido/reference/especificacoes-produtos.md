# Especificações WEG (exemplo validado do contrato)

Valores extraídos dos datasheets em `datasheets/`. São o **exemplo** que preenche
o contrato de `atributos-produto-necessarios.md` — outras marcas têm valores
diferentes para os mesmos atributos. Em caso de dúvida, o datasheet original
prevalece.

## Bateria SBW CB050 / CB100 W00 (alta tensão, LFP)

| Atributo | CB050 | CB100 |
|---|---|---|
| Energia utilizável (kWh) | 5,02 | 10,07 |
| Energia nominal (kWh) | 5,18 | 10,36 |
| DoD (%) | 90 | 90 |
| Máx módulos em paralelo | 4 | 4 |
| Capacidade máx do sistema (kWh) | 20,8 | 41,6 |
| Corrente máx contínua carga/descarga (A) | 27 | 27 |
| Corrente recomendada de carga (A) | 13,5 | 13,5 |
| Corrente de pico de descarga (A) | 65 @ 30 s | 65 @ 30 s |
| Corrente de pico de carga (A) | 32,4 @ 5 s | 32,4 @ 5 s |
| Tensão nominal (V) | 192 | 384 |
| Tensão de operação (V) | 174,0–218,4 | 348,0–436,8 |
| Química | LiFePO4 prismática | LiFePO4 prismática |
| C-rate (carga/descarga típico) | ~1 C (pico) / 0,3 C (vida útil) | idem |
| Ciclos de vida | ≥ 6000 (@0,3C, 90% DoD) | ≥ 6000 |
| Compatível | Todos SIW200H e SIW400H | Todos SIW200H e SIW400H |

> A bateria é **modular**: monta-se 1 a 4 módulos em paralelo por string. O limite
> "4 em paralelo" é o atributo que, combinado com o nº de entradas do inversor,
> define o total de baterias do kit.

## Inversor híbrido monofásico SIW200H (linha M, 220 V)

| Atributo | M030 | M037 | M046 | M050 | M060 |
|---|---|---|---|---|---|
| Potência nominal de saída (kW) | 3,0 | 3,68 | 4,6 | 5,0 | 6,0 |
| Potência aparente máx saída (kVA) | 3,3 | 4,05 | 5,06 | 5,5 | 6,6 |
| EPS nominal (kVA) | 3,0 | 3,68 | 4,6 | 5,0 | 6,0 |
| EPS pico 60 s (kVA) | 3,6 | 4,4 | 5,5 | 6,0 | 7,2 |
| Nº de entradas de bateria | 1 | 1 | 1 | 1 | 1 |
| Corrente máx carga/descarga (A) | 40 | 40 | 40 | 40 | 40 |
| Faixa de tensão de bateria (V) | 80–480 | 80–480 | 80–480 | 80–480 | 80–480 |
| Máx baterias (1 entrada × 4) | 4 | 4 | 4 | 4 | 4 |
| Capacidade máx (kWh) | até ~40 | até ~40 | até ~40 | até ~40 | até ~40 |
| Fase | monofásico 220/230/240 V | | | | |
| MPPT | 2 (1 string cada) | | | | |
| Paralelismo off-grid | 5 unidades | | | | |

## Inversor híbrido monofásico SIW200H (linha S — SplitPhase 110/220 V)

| Atributo | S038 | S057 | S075 | S096 | S114 |
|---|---|---|---|---|---|
| Potência nominal de saída (kW) | 3,8 | 5,7 | 7,5 | 9,6 | 11,4 |
| EPS pico 60 s (kVA) | 5,13 | 7,70 | 10,13 | 12,96 | 15,39 |
| EPS pico 10 min (kVA) | 4,56 | 6,84 | 9,00 | 11,52 | 13,68 |
| Corrente máx carga/descarga (A) | 27 (único) / 50 (paralelo) | | | | |
| Corrente de pico de descarga (A) | 60 @ 60 s | | | | |
| Faixa de tensão de bateria (V) | 85–460 | | | | |
| Nº de MPPT | 3 | | | | |
| Fase | SplitPhase 110/220 V (2L+N) | | | | |

## Inversor híbrido trifásico SIW400H (linha T, 380 V)

| Atributo | T010 | T012 | T015 | T020 | T025 | T030 |
|---|---|---|---|---|---|---|
| Potência CA nominal (kVA) | 10 | 12 | 15 | 20 | 25 | 30 |
| Potência CA aparente máx (kVA) | 11 | 13,2 | 16,5 | 22 | 27,5 | 30 |
| EPS nominal (kVA) | 10 | 12 | 15 | 20 | 25 | 30 |
| EPS pico 60 s (kVA) | 12 | 14,4 | 18 | 24 | 30 | 36 |
| Nº de entradas de bateria | 2 | 2 | 2 | 2 | 2 | 2 |
| Corrente máx por entrada (A) | 50+50 | 50+50 | 50+50 | 50+50 | 50+50 | 50+50 |
| Faixa de tensão de bateria (V) | 150–800 | | | | | |
| Máx baterias (2 entradas × 4) | 8 | 8 | 8 | 8 | 8 | 8 |
| Capacidade máx (kWh) | até ~80 | | | | | |
| Paralelismo | máx 4 unidades | | | | | |
| Fase | trifásico 380/220 (3L+N+PE) | | | | | |

## Inversor híbrido trifásico SIW400H (linha K — tensão dupla 380/220 e 220/127)

A linha K (K007 T012 … K017 T030) é trifásica de tensão dupla. Mesmas restrições
estruturais da linha T (2 entradas de bateria, faixa de tensão, paralelismo).
Para valores exatos por modelo, consulte
`datasheets/DATASHEET_SIW400H_K007_T030_W20_PT_web (1).pdf`.

## Acessórios mencionados (não são produtos de kit, mas condicionam a montagem)

- **Caixa de junção (JBW):** faz o paralelismo CC das baterias. 1 bateria = ligação
  direta (sem JBW); ≥ 2 baterias = 1 JBW por entrada com baterias em paralelo.
- **MS Box:** gestão de energia para paralelismo de inversores trifásicos.
- **Medidor / TC:** necessário para conexão à rede (zero-export / carga da bateria).
