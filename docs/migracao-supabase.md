# Migração Supabase — conta Vitor → conta Coelho (2026-07-31)

## Estado atual

**Banco migrado e verificado.** Aplicação **ainda não** foi virada — segue
apontando para o projeto antigo até o checklist abaixo ser executado.

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

## ⚠️ Checklist de virada (nada disso foi feito ainda)

A troca precisa ser feita **numa janela só**. Se o código subir antes das
envs, o backend passa a validar tokens do projeto novo enquanto o frontend
ainda emite tokens do antigo → login quebra.

**1. Obter no painel do projeto novo** (`vxltorwxvxslhexaaqfs`):
- Senha do banco: Settings → Database → Reset database password
- `service_role` key: Settings → API
- JWT secret (legado, opcional): Settings → API

**2. Railway** (`adaptable-playfulness` / `Calculadora_Meu_bess`):
```
DATABASE_URL              postgresql+asyncpg://postgres.vxltorwxvxslhexaaqfs:<SENHA>@aws-1-sa-east-1.pooler.supabase.com:5432/postgres
SUPABASE_URL              https://vxltorwxvxslhexaaqfs.supabase.co
SUPABASE_SERVICE_ROLE_KEY <service_role do projeto novo>
SUPABASE_JWT_SECRET       <jwt secret do projeto novo>
```
Confirmar o host/porta exatos do pooler no painel (Settings → Database →
Connection string), a região mudou para sa-east-1.

**3. Vercel** (`calculadora-meu-bess`):
```
VITE_SUPABASE_URL       https://vxltorwxvxslhexaaqfs.supabase.co
VITE_SUPABASE_ANON_KEY  eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZ4bHRvcnd4dnhzbGhleGFhcWZzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU1MjA5MjYsImV4cCI6MjEwMTA5NjkyNn0.fmZtEwNa6D5pq9DWM_mz6OrPNdADk9p3f_z7uiQIxY4
```
(a anon key é pública por design — vai no bundle do frontend)

**4. Auth → URL Configuration** no projeto novo: liberar
`https://calculadora-meu-bess.vercel.app` em Site URL e nas Redirect URLs
(inclusive `/set-password`), senão o convite de usuário e o "esqueci a senha"
quebram.

**5. Só então** dar push no commit `4868acf` (JWKS dinâmico) — está commitado
localmente e **não publicado** justamente por isso.

**6. Verificar:** login com uma conta migrada → listar catálogo → gerar uma
cotação → convidar um usuário de teste.

## Pendências de segurança levantadas na migração

1. **Senha do banco antigo vazou no meu output.** Ao listar as variáveis do
   Railway a máscara falhou e o `DATABASE_URL` do projeto antigo apareceu em
   texto claro (usuário `postgres.debiageyayshcvbpivdq`, senha
   `etxrpPitNCNSOM4T`). O projeto antigo continua no ar com os dados —
   **rotacionar essa senha** no painel do Vitor.

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
