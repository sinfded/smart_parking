-- ============================================================================
-- 0007 — Extended lot layout schema for the v2 canvas editor
--
-- The new editor stores ALL layout elements (slots, roads, cameras, etc.)
-- in lots.map_config as a LotMapConfig JSON blob.  Occupancy state stays in
-- slots.current_state and is joined at query time by slotId.
--
-- This migration adds:
--   1. 'vip' to the slot_category enum (admin requested)
--   2. Extra columns on slots (rotation, width, height, code, category override)
--      kept for backward-compat with any direct slot queries.
--   3. A GIN index on lots.map_config for fast element lookups.
-- ============================================================================

-- 1. Add 'vip' to the existing category enum
alter type slot_category add value if not exists 'vip';

-- 2. Extended slot map columns
alter table public.slots
  add column if not exists map_rotation numeric not null default 0,
  add column if not exists map_width    numeric,
  add column if not exists map_height   numeric,
  add column if not exists map_code     text;

-- unique slot code within lot (nullable — only set when editor assigns one)
create unique index if not exists slots_map_code_lot_idx
  on public.slots (lot_id, map_code)
  where deleted_at is null and map_code is not null;

-- 3. GIN index on map_config for fast jsonb queries
create index if not exists lots_map_config_gin_idx
  on public.lots using gin (map_config);

-- 4. Document the new map_config schema
comment on column public.lots.map_config is
  'LotMapConfig v2 JSON: { version, canvas: {width,height}, background: {...}, grid: {...}, elements: [{type, id, x, y, ...}] }. See packages/types/src/lot-layout.ts.';
