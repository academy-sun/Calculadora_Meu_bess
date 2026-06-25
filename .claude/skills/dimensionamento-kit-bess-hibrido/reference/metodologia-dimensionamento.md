# Metodologia de dimensionamento (destilada do treinamento WEG)

Esta é a **regra geral** de como dimensionar — vale para qualquer marca. Os
números específicos (potência de pico, máx baterias, etc.) vêm dos **atributos do
produto** (ver `atributos-produto-necessarios.md`), não daqui.

## 1. Conceito: fluxo de energia híbrido

Um inversor híbrido conecta rede + solar + bateria + cargas. A energia flui para
onde há menor tensão (demanda). Há duas saídas:
- **Saída on-grid** (cargas normais): só funciona com a rede presente.
- **Saída EPS / backup** (cargas críticas): alimentada pela bateria/solar quando a
  rede cai. O comutador (backup box / antilhamento) separa as duas na falta de rede.

Separar **cargas críticas** das **normais** é o passo central: o cliente decide o
que precisa continuar ligado sem rede (geladeira, câmeras, internet…). Quase nunca
se dimensiona o sistema para 100% das cargas — isso encarece demais.

## 2. Modos de operação

| Modo | O que dimensiona as baterias | O que dimensiona o inversor |
|---|---|---|
| **Autoconsumo** | Sobra de energia solar (clipping) p/ descarga noturna | Cargas normais (consumo médio) |
| **Backup / EPS** | Energia das cargas **críticas** × autonomia | **Potência de pico** das cargas críticas |
| **Off-grid** | Todas as cargas viram críticas | Idem, p/ todas as cargas |

## 3. Levantamento de cargas (o coração do EPS)

Para cada carga crítica, são necessários **três** parâmetros — não só a potência:

- **Potência nominal** (W) — consumo em regime.
- **Potência de pico / partida** — via fator **IP/IN** (corrente de partida ÷
  nominal). Motores/compressores partem em 6× a nominal; equipamentos com inversor
  de frequência (ar-condicionado inverter) partem em ~1,2–1,5×. **Entender o IP/IN
  real reduz drasticamente o inversor necessário.**
- **Tempo de uso** (h/dia) e simultaneidade — quais cargas ligam juntas.

A base `db_cargas.csv` traz IP/IN, FP (fator de potência), FD (fator de demanda),
potência e perfil horário 0–23h para ~145 equipamentos típicos. Use-a como
referência ao cadastrar cargas.

### Fórmulas (já implementadas em bess.py → `calculate_backup`)

Por carga: `Pn(kVA) = ⌈qtd × (PNOM/FP)⌉ / 1000`; `Dmn = Pn × FD`;
`Pp = Pn × IP/IN`; `DMp = Dmn × IP/IN`; `E_EPS = Pn × tempo_uso`.

Totais por soma. Daí:
- **E_BAT** (energia de bateria) `= ΣE_EPS × autonomia_h / 24`, depois ajustada por
  DoD e eficiência round-trip → define **quantas baterias**.
- **Pp total** (pico) define a **potência de pico** que o inversor precisa suportar.
- **Pn / Dmn total** define a **potência nominal** do inversor.

## 4. Seleção do inversor

0. **Filtre por tensão antes da potência.** A saída EPS do inversor precisa atender
   a tensão/fase de **todas** as cargas críticas (R8 — bloqueante): carga 127 V exige
   EPS 127 V ou split-phase; carga tri exige inversor tri; etc. Confira também a
   compatibilidade com a rede da unidade (R7) — se exigir tri numa unidade mono, ou
   autotransformador, isso é alerta de infraestrutura. Ver
   `restricoes-composicao-kit.md`.
1. Calcule `Pp total` (pico) e `Pn total` (nominal) das cargas críticas.
2. Escolha um inversor cuja **potência de pico ≥ Pp total** e **nominal ≥ Pn total**.
3. Se nenhum inversor único atende, use **paralelismo** (até o limite do modelo) —
   a potência EPS soma (ex. 4 × 15 kW = 60 kW).
4. **Insight de consultoria:** quanto melhor se entende o IP/IN real das cargas,
   menor (e mais barato) o inversor. Ex.: um ar-condicionado inverter de 1500 W com
   IP/IN 1,5 tem pico ~3,4 kVA — cabe num inversor de 5 kW; assumindo IP/IN 6
   (errado), exigiria 2 inversores de 7,5 kW.

## 5. Seleção das baterias

1. **Por energia:** `n_energia = ⌈E_BAT / capacidade_util_da_bateria⌉`.
2. **Por potência (R2):** `n_potencia = ⌈Pp / (corrente_pico_bateria × tensao)⌉` —
   quantas baterias são necessárias para **entregar o pico de partida** das cargas
   (a corrente da bateria/entrada limita a potência, não só a energia).
3. **Nº de baterias = `max(n_energia, n_potencia)`.** Não basta dimensionar pela
   energia: há casos (muita partida, pouco tempo de backup) em que a potência exige
   mais baterias. Depois **respeite o teto** `n_baterias ≤ entradas × máx_em_paralelo`
   (R1); se estourar, vá para mais inversores (R4).
4. Confirme o **pico entregável** = `min(potência DC das baterias, pico EPS do
   inversor) ≥ Pp` — ver "Tabela EPS" potência-vs-nº-de-baterias.
4. **Reserva de backup:** pode-se reservar parte da capacidade só p/ emergência e
   deixar o resto ciclar em autoconsumo (parametrização no monitoramento).

## 6. C-rate (regime de carga/descarga)

`C-rate = potência ÷ capacidade`. Bateria de 10 kWh que entrega 5 kW → 0,5 C
(descarrega em 2 h); 10 kW → 1 C (1 h); 3,3 kW → 0,3 C (3 h). O C-rate liga a
**potência** (corrente × tensão) à **energia** (capacidade) — é o que explica por
que aumentar baterias além da saturação de corrente dá energia, não potência.

## 7. Normas e segurança

- **Antilhamento** (anti-ilhamento): NBR 6216 / Portaria INMETRO 140 — desconecta a
  saída on-grid na falta de rede; só as críticas seguem alimentadas. Os SIW200H/400H
  têm backup box/comutador automático interno.
- **Black start:** evite depender disso; configure o inversor p/ religar automático.
