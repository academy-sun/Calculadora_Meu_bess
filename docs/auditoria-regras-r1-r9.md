# Auditoria das regras R1–R9 no motor de kit

Cada restrição da skill `dimensionamento-kit-bess-hibrido`
([restricoes-composicao-kit.md](../.claude/skills/dimensionamento-kit-bess-hibrido/reference/restricoes-composicao-kit.md))
mapeada para **onde está implementada** e **qual teste a prova**.

Motivo desta auditoria: as duas falhas de R8 encontradas em campo (validava só
tensão, e era contornada no caminho combinado) existiam porque ninguém tinha
conferido que a regra escrita estava inteira no motor. Regra sem teste é regra
que ninguém sabe se roda.

Implementação: [kit_builder.py](../backend/app/engines/kit_builder.py) —
não `compatibility.py`, como a skill supõe (referência desatualizada).

| Regra | O que exige | Onde | Teste |
|---|---|---|---|
| **R1** | `baterias ≤ entradas × máx_paralelo` | `build_kits` → `cap_bat` | `TestR1TetoDeBaterias` (3) |
| **R2** | corrente truncada **por entrada**; distribuir > concentrar; `n = max(energia, potência)` | `_distribuir`, `_pico_dc_kw` | `TestR2PotenciaPorEntrada` (3) |
| **R3** | `Pp ≤ pico` e `Pn ≤ nominal` | `build_kits` → `qtd_inv` | `TestComercial`, `test_inversor_sem_pico_e_descartado_com_motivo` |
| **R4** | `qtd_inversores ≤ máx_paralelo` | `build_kits` → `ia["max_paralelo"]` | `TestR4TetoDeParalelismo` (2), `test_t015_escala_para_2_inversores_no_pico` |
| **R5** | lista do datasheet da bateria é autoritativa; sem ela, faixa de tensão | `_compativel` | `TestR5CompatibilidadeInversorBateria` (3) |
| **R6** | carga mono em tri ≤ ⅓ da potência — **alerta** | `build_kits` → `alertas` | `TestR6CargaMonoEmTrifasico` (2) |
| **R7** | inversor × rede da unidade — **alerta** | `_alertas_rede` | `TestR7Rede` (3) |
| **R8** | saída EPS × carga: **tensão e fase** — bloqueante | `_serve_tensoes`, `_serve_fases`, `compativel_com_cargas` | 8 testes + `test_combinado_nao_oferece_hibrido_incompativel_com_a_fase` |
| **R9** | `n_jbw` = entradas com ≥ 2 baterias | `_montar_kit` | `TestR9CaixaDeJuncao` (2), `test_duas_baterias_e_uma_caixa_de_juncao` |

## O que a auditoria encontrou

**R5 rejeitava em silêncio.** Par inversor×bateria incompatível saía do laço com
`continue`, sem `SkipReason`. O usuário via "nenhum kit compatível" sem motivo
nenhum — e ficar sem kit sem explicação foi justamente o que tornou os erros de
campo tão difíceis de diagnosticar. Corrigido: agora registra
`"<motivo> (com <bateria>)"`.

**R2 era a regra menos testada** e é a mais sutil: a corrente soma *dentro* da
entrada mas trunca no teto *dela*, então **distribuir 2+1 entrega o dobro de
3+0**. Também não havia teste do caso em que a **potência de partida exige mais
baterias que a energia** — que é o cenário do treinamento. Ambos cobertos agora.

**R1 e R4 tinham o caminho feliz testado, não o teto.** Escalar para 2
inversores estava provado; recusar quando passa de `máx_paralelo`, não.

## Fora do escopo de R1–R9, mas na mesma família

Duas restrições do lado FV não estão na skill e foram descobertas em campo:

- **Teto de matriz FV do inversor** — o motor validava tensão e corrente de
  string, nunca a potência que o inversor processa. Ver
  `MAX_MATRIZ_DC_AC_HIBRIDO` em `pv_kit.py` e os testes de `dc_capacity_modules`.
- **Reaplicar R8 depois de trocar o inversor** — o caminho combinado FV+BESS
  substitui o híbrido ("ampliado") depois do filtro. Toda troca de inversor
  precisa repassar por `compativel_com_cargas`.

## Lacunas conhecidas (não são bugs de código)

`peak_power_kw` do SIW300H, `max_parallel_units` da linha S e os atributos do
`SBW300 B050` não estão nos datasheets disponíveis. Os produtos ficam de fora do
cálculo, e o painel de diagnóstico diz qual atributo falta em cada um.
