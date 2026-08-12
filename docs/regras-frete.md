# Regras de frete — para validação com logística

Gerado a partir de `backend/app/engines/shipping.py`, que é o que a
calculadora executa hoje. Origem declarada no código: espelho do
`ShippingCalc.php` da plataforma MeuBESS (método `calculateByRange`),
com dados de `fretes.php` + `min_frets`.

## Como o CIF é calculado

```
1. Acha a FAIXA pelo valor do kit (sem frete)
2. Pega o PERCENTUAL da UF naquela faixa
3. frete = valor_do_kit × percentual
4. frete = MAIOR entre esse resultado e o MÍNIMO da UF
```

O passo 4 é o que mais surpreende: em kit pequeno o percentual não vale,
vale o piso. Ex.: kit de R$ 25.989 para o Acre → 8% = R$ 2.079, mas o
mínimo do AC é R$ 7.900, então cobra-se R$ 7.900.

**Faixas de valor do kit (R$):** até 10.000 | 10.001 a 25.000 | 25.001 a 50.000 | 50.001 a 100.000 | 100.001 a 200.000 | 200.001 a 300.000 | acima de 300.000

## Percentual por UF e faixa, e piso mínimo

| UF | até 10.000 | 10.001 a 25.000 | 25.001 a 50.000 | 50.001 a 100.000 | 100.001 a 200.000 | 200.001 a 300.000 | acima de 300.000 | Mínimo (R$) |
|---|---|---|---|---|---|---|---|---|
| **AC** | 8% | 8% | 8% | 6% | 7% | 7% | 7% | 7.900 |
| **AL** | 8% | 8% | 8% | 6% | 4% | 4% | 4% | 5.900 |
| **AM** | 8% | 8% | 8% | 6% | 4% | 4% | 4% | 10.200 |
| **AP** | 10% | 10% | 8% | 8% | 8% | 8% | 8% | 13.000 |
| **BA** | 8% | 8% | 8% | 6% | 6% | 6% | 6% | 4.900 |
| **CE** | 8% | 8% | 8% | 6% | 6% | 6% | 6% | 7.000 |
| **DF** | 8% | 8% | 8% | 8% | 6% | 6% | 6% | 5.900 |
| **ES** | 8% | 8% | 6% | 4% | 3% | 3% | 3% | 5.200 |
| **GO** | 10% | 10% | 10% | 8% | 8% | 8% | 8% | 5.600 |
| **MA** | 10% | 10% | 8% | 8% | 8% | 8% | 8% | 7.900 |
| **MG** | 8% | 8% | 6% | 4% | 3% | 3% | 3% | 4.500 |
| **MS** | 1% | 10% | 10% | 8% | 6% | 6% | 6% | 3.900 |
| **MT** | 10% | 10% | 10% | 8% | 6% | 6% | 6% | 5.200 |
| **PA** | 10% | 10% | 10% | 8% | 7% | 7% | 7% | 7.400 |
| **PB** | 10% | 10% | 10% | 8% | 8% | 8% | 8% | 6.900 |
| **PE** | 10% | 10% | 10% | 8% | 6% | 6% | 6% | 6.300 |
| **PI** | 10% | 10% | 10% | 8% | 6% | 6% | 6% | 7.200 |
| **PR** | 8% | 8% | 6% | 4% | 2% | 2% | 2% | 1.980 |
| **RJ** | 8% | 8% | 6% | 4% | 3% | 3% | 3% | 4.800 |
| **RN** | 10% | 10% | 10% | 8% | 6% | 6% | 6% | 7.300 |
| **RO** | 10% | 10% | 10% | 8% | 7% | 7% | 7% | 6.200 |
| **RR** | 8% | 8% | 8% | 6% | 4% | 4% | 4% | 12.500 |
| **RS** | 8% | 8% | 6% | 4% | 2% | 2% | 2% | 2.900 |
| **SC** | 8% | 8% | 6% | 4% | 2% | 2% | 2% | 1.400 |
| **SE** | 8% | 8% | 8% | 6% | 6% | 6% | 6% | 5.500 |
| **SP** | 8% | 8% | 6% | 4% | 3% | 3% | 3% | 3.100 |
| **TO** | 8% | 8% | 8% | 6% | 8% | 8% | 8% | 6.400 |

## Ponto que vale conferir com a logística

O **MS** tem 1% na primeira faixa e 10% na segunda — todas as outras UFs
começam em 8% ou 10% e vão CAINDO conforme o kit encarece. O MS é a única
que sobe. Pode ser real (tabela negociada) ou erro de digitação na origem;
na prática quase não aparece, porque abaixo de R$ 10.000 o piso de
R$ 3.900 vence o percentual de qualquer forma.

## Exemplos calculados pelo código

| UF | Valor do kit | Faixa | % | Frete bruto | Frete cobrado | Quem venceu |
|---|---|---|---|---|---|---|
| PR | 25.989,37 | 25.001 a 50.000 | 6% | 1.559,36 | **1.980,00** | **mínimo** |
| AC | 25.989,37 | 25.001 a 50.000 | 8% | 2.079,15 | **7.900,00** | **mínimo** |
| SC | 12.000,00 | 10.001 a 25.000 | 8% | 960,00 | **1.400,00** | **mínimo** |
| SP | 150.000,00 | 100.001 a 200.000 | 3% | 4.500,00 | **4.500,00** | percentual |
| AM | 80.000,00 | 50.001 a 100.000 | 6% | 4.800,00 | **10.200,00** | **mínimo** |
| MS | 9.000,00 | até 10.000 | 1% | 90,00 | **3.900,00** | **mínimo** |

## FOB

Taxa fixa de **1% do valor do kit**, sem mínimo e sem variação por UF.

O código registra que é uma adaptação: o original da MeuBESS (`calculateFob`)
cobra R$ 20 por kWp de FV, e aqui foi convertido para 1% do valor do kit
por ser 'equivalente para os valores típicos de kits BESS'. **Esse é o item
mais frágil da regra e o que mais merece validação** — a equivalência foi
estimada, não medida.

