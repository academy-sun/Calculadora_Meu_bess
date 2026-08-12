-- 017_feedbacks.sql
--
-- Caixa de entrada de feedback do usuário da calculadora (embed do Ploomes e
-- acesso direto).
--
-- POR QUE GRAVAR, E NÃO SÓ MANDAR E-MAIL
--   E-mail falha em silêncio: credencial expirada, caixa cheia, spam. Um
--   feedback perdido é pior que um feedback atrasado — quem escreveu acha que
--   avisou. Então o registro é a fonte da verdade e o e-mail é notificação em
--   cima dele. `email_enviado` diz o que aconteceu com cada um.
--
-- O CAMPO QUE FAZ ISSO SERVIR PARA ALGUMA COISA é `contexto`: as entradas do
-- cálculo e o kit que saiu. "O dimensionamento está errado" sem isso é
-- irrespondível — não dá para reproduzir o que a pessoa viu.

begin;

create table if not exists feedbacks (
  id            uuid primary key default gen_random_uuid(),
  criado_em     timestamptz not null default now(),

  -- 'embed' (dentro do Ploomes) ou 'interna' (calculadora com login)
  origem        text not null,
  -- 'dimensionamento' | 'melhoria' | 'erro' — o autor classifica
  tipo          text,
  mensagem      text not null,

  -- Quem escreveu. No embed vem do contexto do Ploomes (pode ser nulo); na
  -- interna, do usuário logado.
  autor_nome    text,
  autor_email   text,

  --: Entradas do cálculo + resumo do kit, para reproduzir o caso.
  contexto      jsonb,
  url           text,
  user_agent    text,

  email_enviado boolean not null default false,
  email_erro    text,
  lido          boolean not null default false
);

comment on column feedbacks.contexto is
  'Entradas do calculo e kit resultante no momento do envio. E o que permite reproduzir o caso relatado.';

-- A leitura é sempre "os mais recentes primeiro", e a triagem filtra por lido.
create index if not exists ix_feedbacks_criado_em on feedbacks (criado_em desc);
create index if not exists ix_feedbacks_lido on feedbacks (lido) where lido = false;

commit;

-- ─────────────────────────────────────────────────────────────────────────────
-- ROLLBACK
-- ─────────────────────────────────────────────────────────────────────────────
-- drop table if exists feedbacks;
