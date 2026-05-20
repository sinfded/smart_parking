alter table public.lots
  add column if not exists map_config jsonb not null default '{}';
