-- 019_contas.sql
--
-- Uma linha por conta do Ploomes que usa a calculadora.
--
-- POR QUE
--   Até aqui "quem está chamando" eram duas variáveis de ambiente comparadas
--   por igualdade. Isso responde "qual perfil?" e mais nada. Com a calculadora
--   indo para contas de CLIENTES, faltam três respostas que a env não dá:
--
--     1. de QUEM é esta requisição (hoje o log não sabe dizer);
--     2. como cortar o acesso de UM cliente — rotacionar a chave derruba
--        todos, porque a chave é a mesma para todo mundo;
--     3. quantas contas existem, sem abrir o painel do Railway.
--
-- A CHAVE NÃO FICA AQUI
--   Guardamos o SHA-256 dela. Se este banco vazar, as chaves não vazam junto.
--   Hash simples basta: são 256 bits aleatórios, não senha escolhida por
--   humano — não há dicionário para atacar, e um KDF lento só encareceria o
--   caminho quente de toda requisição.
--
-- O PERFIL CONTINUA SENDO DO SERVIDOR
--   `perfil` aqui decide o que calculate/perfil.py devolve. Cliente entra como
--   'restrito': vê o total do kit e nada de valor unitário.

begin;

create table if not exists contas (
  id            uuid primary key default gen_random_uuid(),
  nome          text not null,
  api_key_hash  text not null unique,
  perfil        text not null check (perfil in ('completo', 'restrito')),
  ativa         boolean not null default true,
  observacao    text,
  criado_em     timestamptz not null default now(),
  atualizado_em timestamptz not null default now()
);

comment on table contas is
  'Contas do Ploomes autorizadas a chamar a calculadora. Uma chave por conta.';
comment on column contas.api_key_hash is
  'SHA-256 hex da chave. A chave em claro nunca e gravada: existe so no painel do Railway (semeadura) e no script do campo desenvolvedor da conta.';
comment on column contas.ativa is
  'Revogacao individual. False = 401, sem tocar nas outras contas.';

-- A busca do caminho quente e por hash entre as contas ativas.
create index if not exists contas_hash_ativa_idx
  on contas (api_key_hash) where ativa;

commit;

-- ─────────────────────────────────────────────────────────────────────────────
-- SEMEADURA
--   Não vai aqui de propósito. As chaves atuais existem como variáveis de
--   ambiente, e uma migration não as enxerga — escrever o hash à mão neste
--   arquivo significaria copiar a chave para o histórico do git.
--   Quem semeia é o boot da aplicação (app/contas/service.semear_do_ambiente),
--   de forma idempotente, lendo as envs que já estão no Railway.
-- ─────────────────────────────────────────────────────────────────────────────

-- PÓS-CHECAGEM
-- select nome, perfil, ativa, criado_em from contas order by criado_em;
