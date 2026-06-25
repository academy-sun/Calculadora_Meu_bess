# Restrições de composição do kit (parametrizadas)

Regras que a lógica de montagem de kit deve aplicar. Cada uma é expressa em função
de **atributos do produto** (não de números fixos de marca). Os valores WEG
aparecem só como ilustração. Implementação alvo:
[compatibility.py](../../../../backend/app/engines/compatibility.py).

## R1 — Contagem máxima de baterias

```
total_baterias ≤ inversor.entradas_bateria × bateria.max_em_paralelo
```

- O limite "máx em paralelo" vem do **datasheet da bateria** (baterias em paralelo
  somam corrente; exceder a corrente suportada danifica o equipamento).
- O inversor contribui com o **nº de entradas** (cada entrada = 1 string paralela).
- **WEG:** SBW = 4 em paralelo. SIW200H mono (1 entrada) → 4 baterias (~40 kWh).
  SIW400H tri (2 entradas) → 8 baterias (~80 kWh).
- ⚠️ Hoje `compatibility.py` calcula `n_baterias = ⌈energia/capacidade⌉` **sem este
  teto** — é o bug central a corrigir.

## R2 — Potência entregável pela bateria (limite de corrente) — garante a partida

A potência que chega às cargas pela via DC é limitada pela **corrente** (da bateria
e da entrada do inversor), não pela contagem de baterias. **Precisa cobrir o pico de
partida das cargas** (`Pp`), senão o inversor desarma mesmo sendo "potente".

```
# potência DC disponível (use corrente de pico da bateria p/ a partida):
i_entrada      = min(baterias_na_entrada × bateria.corrente_pico, inversor.corrente_max_entrada)
p_dc_pico      = Σ_entradas (i_entrada × bateria.tensao)
pico_entregavel = min(p_dc_pico, inversor.potencia_pico_eps)
exigir: pico_entregavel ≥ Pp_das_cargas        # senão a partida não é garantida

# nº de baterias que a POTÊNCIA exige (independente da energia):
n_por_potencia = ⌈ Pp / (bateria.corrente_pico × bateria.tensao) ⌉   # respeitando o cap da entrada
```

- A corrente máx por entrada satura com ~2 baterias (ex. WEG: entrada 50 A, bateria
  ~27 A contínua / 65 A pico → 2 baterias já saturam). Baterias **além** disso
  adicionam **energia**, não potência. É o que a "Tabela EPS" da WEG tabula.
- Distribuir baterias entre as entradas aumenta a potência; empilhar tudo numa
  entrada, não.
- **Por isso o nº final de baterias é `max(n_por_energia, n_por_potencia)`** (ver
  metodologia §5). Há casos em que a potência de partida exige mais baterias do que a
  energia — não basta dimensionar pela energia.

## R3 — Potência de pico das cargas

```
Pp_cargas ≤ inversor.potencia_pico        (sustentada ~60 s)
Pn_cargas ≤ inversor.potencia_nominal     (regime contínuo)
```

- `Pp_cargas` vem do levantamento (Pp = Pn × IP/IN), já calculado em `bess.py`.
- Se exceder, o inversor desarma por sobrecarga na partida. Hoje a lógica **ignora**
  o pico — filtra só por EPS médio. Corrigir filtrando por potência de pico.

## R4 — Paralelismo de inversores

```
qtd_inversores ≤ inversor.max_paralelo
potencia_eps_total = qtd_inversores × inversor.potencia_eps
```

- Permite atender cargas além de um inversor. **WEG:** SIW400H = 4 unidades
  (ex. 4×15 = 60 kW); trifásico exige acessório MS Box.
- Hoje `qtd_inversores` é fixo em 1 — deve escalar quando a potência/energia exige.

## R5 — Compatibilidade inversor × bateria (sempre verificar)

```
# Fonte autoritativa quando existir:
bateria.inversores_compativeis contém inversor.modelo
# Na ausência da lista, exigir (necessário, não suficiente):
bateria.faixa_operacao ⊂ inversor.faixa_tensao_bateria
```

- **Não assuma que mesma marca = compatível.** Há inversores WEG que **não** são
  compatíveis com modelos específicos de bateria WEG. Sempre cheque.
- Quando o datasheet da bateria declara a **lista de inversores compatíveis**, ela é
  a fonte autoritativa — use-a diretamente. (Ex.: SBW declara "Todos os SIW200H e
  SIW400H", mas outra bateria pode restringir a modelos específicos.)
- Quando não há lista, a compatibilidade de **tensão** (`bateria.faixa_operacao ⊂
  inversor.faixa_tensao_bateria`) é condição **necessária** — mas pode não ser
  suficiente (corrente, protocolo BMS, certificação também importam). Na dúvida, não
  monte o kit às cegas: sinalize para revisão técnica.
- **WEG (exemplo de tensão):** bateria CB100 opera 348–437 V; SIW400H aceita
  150–800 V → cabe na faixa (mas confirme também na lista de compatíveis).

## R6 — Carga monofásica em inversor trifásico (apenas ALERTA)

```
se inversor.fase == trifasico e carga_mono > inversor.potencia_nominal / 3:
    emitir ALERTA  (NÃO bloquear o kit)
```

- Um inversor tri divide a potência entre as 3 fases; uma carga mono não deve passar
  de ~1/3 (ex. 30 kW tri → ~10 kW mono por fase). É **orientação**, não impedimento:
  a plataforma deve sinalizar, não recusar o kit.

## R7 — Compatibilidade inversor × rede da unidade (AC, lado rede) — ALERTA

```
se inversor.fase/tensao_rede != unidade.padrao_entrada:
    emitir ALERTA de infraestrutura (NÃO bloquear necessariamente)
```

A tensão AC tem domínios distintos da tensão DC da bateria (R5). Aqui é o lado
**rede**: o que o inversor espera na conexão com a concessionária vs o padrão de
entrada da unidade consumidora.

- Unidade **mono** mas o dimensionamento exige inversor **tri** → alerta:
  **aumento de carga / troca de padrão de entrada** da unidade junto à concessionária.
- Unidade **tri 127/220** com inversor **tri 220/380** → alerta: precisa de
  **autotransformador** de potência adequada.
- É orientação de infraestrutura — a plataforma sinaliza o custo/obra extra, não
  recusa o kit automaticamente.

## R8 — Compatibilidade saída EPS × cargas de backup (AC, lado carga) — BLOQUEANTE

```
para cada carga_critica:
    exigir carga.tensao/fase ∈ inversor.saida_eps   (senão: kit inviável)
```

Este é o lado **carga**: a saída EPS do inversor precisa alimentar adequadamente
cada carga de backup. Diferente de R7, aqui a incompatibilidade **inviabiliza** o
projeto.

- Inversor mono com **EPS só 220 V** → **não** alimenta carga 127 V.
- **Carga trifásica nunca** em inversor monofásico.
- Inversor **tri 220/380** → não alimenta mono **127 V** (a linha K 220/127 sim).
- Mono **127 V** exige EPS 127 V **ou** **split-phase** 127/220.
- Mistura **127 + 220** mono no backup → exige **split-phase** (ex. SIW200H linha S),
  que alimenta as duas tensões simultaneamente e tolera 100% de desequilíbrio entre
  elas (pode-se concentrar a carga numa perna 127 V).
- **WEG (saída EPS por linha):** M = 220; S = 110/220 (split-phase); T = 380/220;
  K = 380/220 e 220/127.

## R9 — Acessório de paralelismo de baterias (caixa de junção / JBW)

```
necessita_caixa_juncao = (baterias_em_paralelo_por_entrada ≥ 2)
```

- 1 bateria = ligação direta (sem acessório). ≥ 2 baterias numa entrada = 1 caixa de
  junção. No trifásico com baterias nas 2 entradas, 1 caixa por entrada.
- Impacta o **custo/BOM** do kit, não a viabilidade elétrica.

---

## Ordem de aplicação sugerida na montagem

1. Filtrar inversores por **compatibilidade de saída EPS com as cargas** (R8 —
   bloqueante) e pela fase da instalação.
2. Para cada inversor candidato: checar **R3** (pico/nominal ≥ cargas).
3. Calcular baterias por energia (E_BAT) e aplicar **R1** (teto de contagem) + **R2**
   (potência). Se não atende, tentar **R4** (mais inversores).
4. Aplicar **R5** (compatibilidade inversor × bateria) ao parear inversor × bateria.
5. Alertas: **R6** (carga mono em tri) e **R7** (rede/autotransformador).
6. **R9** para compor o BOM (acessórios).
7. Ordenar por custo total e devolver as melhores opções.
