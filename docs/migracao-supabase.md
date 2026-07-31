# Migração Supabase — conta Vitor → conta Coelho (2026-07-31)

## Estado atual

**Migração concluída em 31/07/2026.** Banco migrado, aplicação virada e
validada em produção (login, catálogo, cotação). O projeto antigo **não existe
mais** — foi removido da conta do Vitor em algum momento entre a cópia do banco
e a virada.

| | Antigo | Novo |
|---|---|---|
| Ref | `debiageyayshcvbpivdq` | `vxltorwxvxslhexaaqfs` |
| URL | `https://debiageyayshcvbpivdq.supabase.co` | `https://vxltorwxvxslhexaaqfs.supabase.co` |
| Conta | Vitor | Coelho Org (`xeylgyhavlvqyqwjiozv`) |
| Região | us-east-1 | sa-east-1 (São Paulo) |
| Custo | — | $0/mês (free tier) |

Fonte: `db_cluster-28-07-2026@14-47-41.backup.gz` (dump de cluster, PG 17.6).
O `.storage.zip` estava vazio — confirmado que não era download falho: o
projeto de origem tinha `storage.objects = 0` e `storage.buckets = 0`.

## O que foi restaurado (conferido linha a linha)

| Tabela | Origem | Destino |
|---|---|---|
| `meubess_products` | 705 | 705 ✅ |
| `products_bess` | 195 | 195 ✅ |
| `products_solar` | 68 | 68 ✅ |
| `standard_loads` | 155 | 155 ✅ |
| `projects` | 3 | 3 ✅ |
| `auth.users` | 5 | 5 ✅ (senhas e e-mails confirmados preservados) |
| `auth.identities` | 5 | 5 ✅ |

Também preservados: 58 registros com `overrides_tecnicos` (incluindo o fix
dos 3 componentes que não são estrutura), PKs, uniques, FKs, os 6 índices de
`meubess_products` e os GRANTs originais.

Não migrado de propósito: `auth.sessions` / `auth.refresh_tokens` (invalidam
na troca de projeto — todos precisam logar de novo) e o histórico
`supabase_migrations` (o schema já veio aplicado).

## Virada — o que foi executado

**Railway** (`adaptable-playfulness` / `Calculadora_Meu_bess`):
```
DATABASE_URL              postgresql+asyncpg://postgres.vxltorwxvxslhexaaqfs:<SENHA>@aws-0-sa-east-1.pooler.supabase.com:5432/postgres
SUPABASE_URL              https://vxltorwxvxslhexaaqfs.supabase.co   (não existia antes)
SUPABASE_SERVICE_ROLE_KEY <service_role do projeto novo>
```
O host é **`aws-0`**, não `aws-1` — `aws-1-sa-east-1` existe mas responde
`tenant/user not found`. Porta **5432 (session mode)**, não 6543: o engine em
`app/database.py` não seta `statement_cache_size=0`, então o transaction pooler
quebraria os prepared statements do asyncpg.

**Vercel** (`calculadora-meu-bess`, conta `marcoss-projects-706fd7c8`):
```
VITE_SUPABASE_URL       https://vxltorwxvxslhexaaqfs.supabase.co
VITE_SUPABASE_ANON_KEY  eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZ4bHRvcnd4dnhzbGhleGFhcWZzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU1MjA5MjYsImV4cCI6MjEwMTA5NjkyNn0.fmZtEwNa6D5pq9DWM_mz6OrPNdADk9p3f_z7uiQIxY4
```
Gravadas nos 3 ambientes e marcadas **não-sensíveis** de propósito: são
públicas por design (vão no bundle) e, como *sensitive*, o `vercel env pull`
devolve string vazia, o que impede conferir o que está no ar.

**Commits publicados:** `4868acf` (JWKS dinâmico) e `547eec0` (esta doc).

## Validação em produção (31/07/2026)

Feita com um usuário de teste criado e removido ao final:

| Verificação | Resultado |
|---|---|
| Login (emissão de token) | ✅ `alg=ES256`, `kid=ce4ff541-…` do projeto novo |
| `GET /catalog/loads` | ✅ 155 cargas |
| `GET /catalog/products` | ✅ 705 produtos |
| `GET /catalog/bess` | ✅ 194 (de 195 — 1 com `disponivel=false`; `list_bess` filtra) |
| `GET /admin/users` | ✅ usa a `service_role` do projeto novo |
| `POST /calculate` | ✅ kit WEG SBW CB050 ×3 + SIW200H M050 ×1, R$ 25.989,37 |
| `GET /projects` | ✅ 3 cotações |
| Bundle publicado | ✅ referencia só o projeto novo |

## Pendências

**1. Auth → URL Configuration (manual, no painel).** Liberar
`https://calculadora-meu-bess.vercel.app` em Site URL e nas Redirect URLs,
inclusive `/set-password`. Não afeta o login (validado), mas **convite de
usuário e "esqueci a senha" continuam quebrados** até isso ser feito — um
projeto criado via API nasce com Site URL `http://localhost:3000`.

**2. `SUPABASE_JWT_SECRET` está obsoleto.** Ainda guarda o segredo do projeto
antigo. Hoje é inofensivo: só serve de fallback para tokens não-ES256, e o
projeto que o emitia não existe mais. Substituir pelo do projeto novo ou
remover a variável (sem ela o fallback falha fechado).

**3. Backend em Singapura, banco em São Paulo.** O serviço Railway está na
região *Southeast Asia*. Medido em produção: `/health` (sem banco) 401 ms
contra `/catalog/loads` (com banco) 1105 ms — cerca de **700 ms por request só
de ida-e-volta ao banco**. Mover o serviço para *US East* aproximaria os dois
lados e ainda reduziria a latência para usuários no Brasil.

**4. `anon` com `GRANT ALL` e RLS desligado** — ver seção abaixo.

## Pendências de segurança levantadas na migração

1. ~~**Senha do banco antigo vazou no meu output.**~~ **Resolvido por
   circunstância, não por ação.** A senha do projeto antigo apareceu em texto
   claro ao listar as variáveis do Railway (a máscara falhou). Na virada,
   porém, constatou-se que o projeto `debiageyayshcvbpivdq` **não existe
   mais**: o domínio não resolve em DNS e o pooler responde `tenant/user not
   found`. Não há mais o que rotacionar. Se a conta do Vitor for restaurada a
   partir de backup, a senha volta a valer e aí sim precisa ser trocada.

2. **`anon` tem `GRANT ALL` em todas as tabelas do `public`, com RLS
   desligado.** Isso veio do projeto original (é o default do Supabase) e foi
   replicado para manter paridade. Na prática significa que qualquer um com a
   anon key — que é pública, embutida no frontend — pode ler, alterar e apagar
   o catálogo inteiro via PostgREST. A aplicação não depende disso (o backend
   acessa via `DATABASE_URL` como `postgres`, e o frontend só usa o Supabase
   para login), então dá para revogar ou ligar RLS sem quebrar nada.
   Recomendado fazer isso depois da virada validada.

3. Durante a carga, `INSERT` foi concedido a `anon` temporariamente (única
   via de escrita em massa sem a service key) e **revogado logo em seguida**.
   Janela de poucos minutos, em projeto recém-criado e ainda não divulgado.

## Observação sobre os usuários

`caio.ferreira@meubess.com.br` está sem `role` no metadata — a aplicação
trata como `engineer`, que hoje mapeia para o perfil **integrador** (só vê
`kit_ftv`). Os outros 4 estão como `admin`. Ajustar pela tela de Usuários se
não for o desejado.
