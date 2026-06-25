---
name: dimensionamento-kit-bess-hibrido
description: >-
  Regras de engenharia para dimensionar e montar kits BESS híbridos (inversor
  híbrido + bateria) e para decidir QUAIS atributos de produto precisam ser
  cadastrados para o cálculo funcionar. Use sempre que o trabalho envolver a
  lógica de montagem/compatibilidade de kits da calculadora (compatibility.py,
  bess.py, calculate/service.py), o dimensionamento de baterias/inversores, o
  levantamento de cargas (EPS/backup, potência de pico, IP/IN), ou a decisão de
  quais campos cadastrar nos produtos (meubess_products / plataforma MeuBESS).
  O conhecimento é marca-agnóstico — a WEG (inversores SIW200H/SIW400H e bateria
  SBW) entra apenas como exemplo validado; outras marcas têm valores diferentes
  para os MESMOS atributos. Mesmo que o pedido não cite "dimensionamento"
  explicitamente, consulte esta skill antes de propor regras de kit ou campos de
  produto, para não inventar critérios.
---

# Dimensionamento de kits BESS híbridos

## Para que serve

A montagem de um kit BESS (bateria + inversor híbrido) tem restrições físicas
reais: quantas baterias o inversor comporta, qual potência ele entrega, se a
bateria é eletricamente compatível, quando precisa de acessório. Ignorar isso
gera kits impossíveis de instalar (ex.: 8 baterias num inversor que aceita 4) ou
subdimensionados (inversor que desarma no pico de partida das cargas).

Esta skill reúne o conhecimento de engenharia para fazer isso **certo** e,
crucialmente, define **o contrato de dados** — quais atributos cada produto
precisa ter cadastrado para o cálculo ser possível.

## Princípio central: atributos, não regras fixas de marca

Cada marca/modelo tem critérios próprios. Portanto **não** codifique "4 baterias
por inversor" como regra universal — isso é o valor WEG. Codifique a **regra
parametrizada** ("baterias ≤ entradas × máx-em-paralelo") e leia os números dos
**atributos do produto**, que vêm do datasheet de cada equipamento.

A WEG (SIW200H mono, SIW400H tri, bateria SBW) é o exemplo concreto que valida o
contrato. Toda regra aqui é ilustrada com valores WEG, mas o que importa é o
atributo, não o número.

> **Regra inegociável:** todo atributo exigido pelo cálculo precisa ser
> **encontrável no datasheet** do produto. Se algo necessário não estiver no
> datasheet, isso é um problema — sinalize explicitamente em vez de inventar.

## Quando usar e o que ler

| Situação | Leia |
|---|---|
| Decidir/auditar campos a cadastrar nos produtos | `reference/atributos-produto-necessarios.md` ⭐ |
| Implementar/ajustar a lógica de kit (compatibilidade) | `reference/restricoes-composicao-kit.md` |
| Calcular energia/potência das cargas (EPS, backup, pico) | `reference/metodologia-dimensionamento.md` |
| Ver os valores reais de um modelo WEG | `reference/especificacoes-produtos.md` + `reference/datasheets/` |
| Base de cargas (IP/IN, FP, perfil horário) p/ cadastro | `reference/db_cargas.csv` |

## Resumo das restrições (parametrizadas)

Detalhe e justificativa em `reference/restricoes-composicao-kit.md`. Em síntese:

1. **Contagem de baterias:** `total_baterias ≤ inversor.entradas_bateria ×
   bateria.max_em_paralelo`. (WEG mono = 1 entrada × 4 = 4; tri = 2 × 4 = 8.)
2. **Potência entregável (limite POR ENTRADA):** cada entrada tem teto de corrente
   (WEG = 50 A). Baterias em paralelo na MESMA entrada somam corrente até esse teto;
   acima dele, adicionar bateria dá **energia**, não potência. **Distribua** as
   baterias entre as entradas (ex.: 2+1, não 3+0) para extrair mais potência. O nº
   final de baterias = `max(por energia, por potência de partida)`.
3. **Potência de pico:** o pico das cargas (`Pp`, função do IP/IN) deve caber na
   **potência de pico** do inversor (sustentada ~60 s; depois cai para a nominal).
4. **Paralelismo de inversores:** `qtd_inversores ≤ inversor.max_paralelo` (WEG
   tri = 4; soma a potência EPS, ex. 4×15 = 60 kW).
5. **Compatibilidade inversor × bateria:** **sempre** verificar — não assuma que
   mesma marca = compatível (há inversores WEG que não pareiam com certos modelos de
   bateria WEG). Use a **lista de compatíveis** do datasheet da bateria quando ela
   existir (fonte autoritativa); na ausência dela, exija
   `bateria.faixa_tensao ⊂ inversor.faixa_tensao_bateria`.
6. **Carga monofásica em inversor trifásico:** ≤ potência ÷ 3. Isto é apenas
   **alerta**, NÃO bloqueia o kit.
7. **Compatibilidade inversor × rede da unidade (AC, lado rede):** se a fase/tensão
   exigida pelo inversor difere da entrada de energia da unidade, é **alerta** de
   infraestrutura — ex.: unidade mono mas dimensionamento exige tri → precisa
   aumento de carga/troca de padrão de entrada; unidade tri 127/220 com inversor tri
   220/380 → precisa **autotransformador** de potência adequada.
8. **Compatibilidade saída EPS × cargas de backup (AC, lado carga) — BLOQUEANTE:**
   cada carga crítica precisa ter sua tensão/fase atendida pela saída EPS do
   inversor. Ex.: inversor mono com EPS só 220 V não alimenta carga 127 V; carga
   trifásica nunca em inversor mono; inversor tri 220/380 não alimenta mono 127 V.
   **Split-phase** (ex. SIW200H linha S) alimenta 127 e 220 V mono simultaneamente —
   prefira-o quando há mistura 127/220.
9. **Acessório (caixa de junção / JBW):** `n_jbw` = nº de **entradas** com ≥ 2
   baterias em paralelo (ex.: distribuição 2+1 → 1 JBW; 2+2 → 2 JBW; 1+1 → 0). A
   **MS Box** é outra coisa: serve para paralelizar **inversores** tri (vários),
   não baterias — um único inversor não precisa.

## Metodologia de dimensionamento (resumo)

Detalhe em `reference/metodologia-dimensionamento.md`. Dois modos:

- **Autoconsumo:** baterias dimensionadas pela sobra de energia solar (clipping);
  inversor pelas cargas normais (consumo médio).
- **Backup / EPS:** baterias pela energia das **cargas críticas** ×
  autonomia; inversor pela **potência de pico** das críticas (partida de motores,
  compressores). `E_BAT = E_EPS × autonomia/24`, ajustado por DoD e eficiência.

As fórmulas de levantamento de carga (Pn, Dmn, Pp, DMp, E_EPS a partir de POT, FP,
FD, IP/IN, tempo de uso) **já estão implementadas** em
[bess.py](../../../backend/app/engines/bess.py) (`calculate_backup`). Reaproveite
em vez de reimplementar.

## Contrato de dados do produto + lacunas na plataforma

Esta é a ponte para a calculadora. O contrato completo (atributo → unidade →
por quê → campo no datasheet → exemplo WEG) está em
`reference/atributos-produto-necessarios.md`. Resumo do mapeamento para a tabela
`meubess_products` da calculadora:

**Já existem** campos utilizáveis: `power`, `max_output_power`, `max_eps_power`,
`battery_inputs`, `voltage`, `phase`, `qty_mppt`.

**Faltam (candidatos a adicionar no cadastro da MeuBESS — todos presentes nos
datasheets):**
- *Inversor:* potência de pico + duração; corrente máx por entrada de bateria;
  faixa de tensão de bateria aceita; nº máx de unidades em paralelo.
- *Bateria:* capacidade útil e nominal; DoD; máx módulos em paralelo; corrente máx
  contínua e de pico de carga/descarga; tensão nominal e faixa de operação; química.

Ao trabalhar na **Fase 3b** (adaptar `compatibility.py`/`calculate/service.py`
para ler de `meubess_products`), consuma esses atributos: derive o tipo efetivo
por `coalesce(tipo_manual, tipo_auto)`, limite a contagem de baterias, escale
inversores, filtre por potência de pico e valide a compatibilidade de tensão.
Onde um atributo ainda não existir no cadastro, trate como ausente (não bloqueie)
e registre a lacuna — não invente um default silencioso que mascare o problema.
