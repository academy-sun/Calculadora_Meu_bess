# Integração Ploomes v2 — Embed no gerador de propostas

> Substitui a integração legada (Ploomes chamando `/calculate` diretamente via
> fórmula integrada). O fluxo agora é bidirecional, orquestrado pelo nosso
> backend, com a interface da calculadora embutida no formulário do Ploomes via
> **campo desenvolvedor** (requer CPQ — confirmado na conta).

## Arquitetura

```
Ploomes (formulário do negócio)
  └─ Campo desenvolvedor (JS mínimo — ver ploomes-campo-desenvolvedor.md)
       └─ <iframe src="https://calculadora-meu-bess.vercel.app/embed/ploomes?deal_id={id}">
            1. GET  /ploomes/context/{deal_id}   → prefill (kWp, cidade/UF, estrutura)
            2. POST /calculate                   → kits (mais barato + alternativas)
            3. POST /ploomes/pushback            → grava no Ploomes:
                 a. campos resumo no negócio (PATCH Deals/OtherProperties)
                 b. itens do kit no orçamento (upsert Products + Quotes(id)/Products)
                 c. comentário resumo (Interactions)
            4. postMessage 'meubess:saved'       → campo desenvolvedor notifica/atualiza
```

O vendedor não sai do Ploomes. O backend usa a **User-Key** do Ploomes para ler
e escrever; o embed autentica no nosso backend com **X-API-Key**.

## Variáveis de ambiente (Railway)

| Variável | Uso |
|---|---|
| `API_KEY_PLOOMES` | User-Key do Ploomes (chamadas de SAÍDA para api2.ploomes.com). Também segue válida como key de entrada legada. |
| `API_KEY_EMBED` | Key de ENTRADA usada pelo embed (`X-API-Key` em `/calculate` e `/ploomes/*`). Separada da User-Key por segurança. |
| `PLOOMES_FIELD_MAP` | JSON mapeando nossos campos → FieldKeys da conta (ver abaixo). |

No Vercel, o embed usa a `VITE_API_KEY_PLOOMES` já existente (embutida no
build). Para migrar para a key dedicada, troque o valor dessa env pela
`API_KEY_EMBED` e redeploye o frontend.

### PLOOMES_FIELD_MAP

Chaves de **entrada** (context/prefill): `powerpeak_kwp`, `cidade`, `uf`, `fixing_type`
Chaves de **saída** (pushback): `kit_preco`, `kit_descricao`, `frete_valor`, `frete_descricao`, `total_geral`

```json
{"powerpeak_kwp":"deal_A1B2C3","fixing_type":"deal_D4E5F6",
 "kit_preco":"deal_G7H8I9","kit_descricao":"deal_J0K1L2",
 "frete_valor":"deal_M3N4O5","total_geral":"deal_P6Q7R8"}
```

Cidade/UF saem do `City` nativo do negócio quando preenchido; os FieldKeys
`cidade`/`uf` são fallback. Para descobrir as FieldKeys da conta:

```
GET /ploomes/fields            (header X-API-Key)
GET /ploomes/fields?entity_id=2
```

## Endpoints novos

Todos autenticados por header `X-API-Key` (aceita `API_KEY_EMBED` ou
`API_KEY_PLOOMES`).

### GET /ploomes/context/{deal_id}

Prefill do embed. Resposta:

```json
{
  "deal_id": 123,
  "titulo": "Projeto Solar — Cliente X",
  "powerpeak_kwp": 8.5,
  "cidade": "Londrina",
  "uf": "PR",
  "fixing_type": "tile_ceramic",
  "field_map_configurado": true,
  "raw_fields": [{"field_key": "deal_...", "valor": "..."}]
}
```

`raw_fields` traz todos os campos custom preenchidos no negócio
(diagnóstico/descoberta de FieldKeys).

### POST /calculate (uso pelo embed)

Contrato inalterado (ver [api-ploomes.md](api-ploomes.md)). O embed envia
`tipo_calculo="backup"` com `powerpeak_kwp` (vindo do Ploomes) e/ou
`cargas_backup` (tabela preenchida pelo vendedor, com tensão por carga —
obrigatória para a seleção de inversor), `tipo_frete`/`uf_entrega` e
`perfil_usuario` (default do embed: `consultor`; sobrescrevível via query
`?perfil=` na URL do iframe).

**Nota:** o embed envia `origem="ploomes"` SEM `negocio_id`, para o comentário
automático não disparar a cada recálculo — o comentário sai só no pushback.

### POST /ploomes/pushback

```json
{
  "deal_id": 123,
  "kit_descricao": "WEG — SIW200H M075 + 4× SBW CB100",
  "kit_preco": 69191.00,
  "frete_valor": 3100.00,
  "frete_descricao": "CIF — PR",
  "total_geral": 72291.00,
  "itens": [{"nome": "...", "sku": null, "qtd": 1, "preco_unitario": 8654.16}],
  "incluir_produtos": true
}
```

Resposta = relatório por etapa (o embed exibe; falha parcial não aborta o resto):

```json
{
  "campos":     {"ok": true,  "detalhe": "4 campo(s) atualizados"},
  "produtos":   {"ok": true,  "detalhe": "orçamento 777", "itens": [{"nome": "...", "ok": true}]},
  "comentario": {"ok": true}
}
```

Produtos: upsert por `Code` (sku) ou `Name` em `/Products`, inserção no
orçamento mais recente do negócio (`/Quotes(id)/Products`). Negócio sem
orçamento → itens não inseridos (reportado em `detalhe`).

## Configuração na conta Ploomes (passo a passo)

1. **Campos custom no Negócio** (tipo moeda/texto): Preço do kit, Descrição do
   kit, Frete, Total geral. Anotar as FieldKeys → montar `PLOOMES_FIELD_MAP`.
2. **Campo desenvolvedor** no formulário do negócio — snippet e spike de
   validação em [ploomes-campo-desenvolvedor.md](ploomes-campo-desenvolvedor.md).
3. **Envs no Railway**: `API_KEY_EMBED` (gerar uma key forte) e
   `PLOOMES_FIELD_MAP` (JSON do passo 1). Redeploy automático no push; conferir
   `railway deployment list` (deploy que falha mantém a versão antiga no ar).
4. Testar num negócio de teste: prefill → cargas → calcular → enviar →
   conferir campos, itens do orçamento e comentário.

## Fluxo do vendedor (resumo)

1. Abre o negócio no Ploomes; o gerador de propostas já calculou o kWp.
2. No campo desenvolvedor, a calculadora MeuBESS carrega já preenchida
   (kWp, cidade/UF → frete CIF pré-selecionado, estrutura).
3. Adiciona as cargas críticas de backup (com tensão) e confirma o frete.
4. "Buscar kits" → vê o kit mais barato (alternativas colapsadas).
5. "Enviar para proposta" → campos + itens + comentário entram no Ploomes.

## Legado mantido

- `POST /calculate` com `origem="ploomes"` **e** `negocio_id` ainda posta o
  comentário automático (fluxo antigo de fórmula integrada continua funcional
  para quem chamar direto).
- `app/shared/ploomes.py` é reexport de `app/ploomes/client.py`.
- A referência completa de todos os endpoints segue em
  [api-ploomes.md](api-ploomes.md).
