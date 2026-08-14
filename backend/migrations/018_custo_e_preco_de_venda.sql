-- 018_custo_e_preco_de_venda.sql
--
-- Passa a guardar o preço de CUSTO que a MeuBESS começou a expor na API
-- (campo `cost`, pedido em 13/08/2026).
--
-- POR QUE
--   O `price` da API é o "Preço de Venda Fixo" do cadastro: preenchido à mão e
--   que NÃO segue a fórmula de margem da plataforma. No módulo LONGI 635 ele
--   vale R$ 600,00 enquanto o custo é R$ 546,10 — margem de 9,87%, e não os
--   23,85% que a MeuBESS aplica de verdade. A calculadora vinha cotando 600,00
--   e o correto é 546,10 / (1 - 0,2385) = R$ 717,14.
--
--   A conta passa a ser feita no motor (kit_attributes.preco_venda), a partir
--   desta coluna. `price` continua sendo importado, mas só como referência.

begin;

alter table meubess_products
  add column if not exists cost numeric;

comment on column meubess_products.cost is
  'Preco de custo do material, vindo do campo `cost` da API MeuBESS. Base do preco de venda: custo / (1 - margem). Nulo significa produto nao cotavel.';

commit;

-- ─────────────────────────────────────────────────────────────────────────────
-- PÓS-CHECAGEM (rodar depois do primeiro sync com a coluna criada)
-- ─────────────────────────────────────────────────────────────────────────────
-- select count(*) as total,
--        count(cost) as com_custo,
--        count(*) filter (where cost is null and coalesce(ativo_manual, active)) as ativos_sem_custo
--   from meubess_products;
--
-- Produto ativo sem custo deixa de ser cotável (o motor o descarta com motivo).
-- Se esse número for alto, é cadastro a resolver com a MeuBESS, não código.
