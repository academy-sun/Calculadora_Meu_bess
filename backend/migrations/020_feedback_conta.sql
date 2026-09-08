-- 020_feedback_conta.sql
--
-- De qual conta veio o feedback.
--
-- POR QUE
--   Hoje um relato chega com origem ('embed' ou 'interna') e mais nada. Com
--   uma conta só dá para adivinhar de quem é; com cinco clientes, não dá.
--   E é justamente o relato de cliente que precisa de resposta rastreável.
--
--   Nulo continua sendo válido: a calculadora interna autentica por sessão,
--   não por chave, então nem toda origem tem conta.

begin;

alter table feedbacks
  add column if not exists conta_id uuid references contas(id) on delete set null;

comment on column feedbacks.conta_id is
  'Conta do Ploomes que enviou o relato. Nulo quando veio da calculadora interna (sessao, nao chave).';

create index if not exists feedbacks_conta_idx on feedbacks (conta_id);

commit;
