# MeuBess Frontend

Interface web interna para dimensionamento BESS e Solar.

## Setup Local

```bash
cd frontend
npm install
cp .env.example .env.local
# Preencha as variáveis no .env.local
npm run dev
```

## Variáveis de Ambiente

| Variável | Descrição |
|---|---|
| `VITE_SUPABASE_URL` | URL do projeto Supabase (ex: https://abc.supabase.co) |
| `VITE_SUPABASE_ANON_KEY` | Chave anônima do Supabase |
| `VITE_API_URL` | URL do backend no Railway (ex: https://meubess-api.railway.app) |
| `VITE_API_KEY_PLOOMES` | API Key para autenticar no endpoint `/calculate` |

## Deploy (Vercel)

Configure as variáveis de ambiente no dashboard do Vercel antes do deploy:

```bash
npx vercel --prod
```

## Rotas

| Rota | Acesso | Descrição |
|---|---|---|
| `/login` | Público | Login via Supabase Auth |
| `/` | Engineer + Admin | Dashboard com atalhos e últimos projetos |
| `/projects` | Engineer + Admin | Histórico de projetos |
| `/projects/new` | Engineer + Admin | Wizard de novo cálculo |
| `/projects/:id` | Engineer + Admin | Resultado e detalhe do projeto |
| `/catalog/bess` | Admin | Catálogo BESS (baterias + inversores híbridos) |
| `/catalog/solar` | Admin | Catálogo Solar (módulos FV + inversores) |
| `/catalog/loads` | Admin | Cargas Padrão |

## Tipos de Cálculo Suportados

- **Backup** — potência crítica + autonomia + tensão
- **Peak Shaving** — curva de carga + demanda-alvo + tarifa de demanda
- **Arbitragem Tarifária** — curva de carga + janela de ponta + tarifas
- **Solar FV** — irradiação + área disponível
- **Solar + Storage** — combinação FV + armazenamento
