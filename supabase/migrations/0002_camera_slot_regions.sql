-- Migration 0002: camera slot regions + lot settings
-- Apply after schema2.sql (0001).
-- These two tables support the camera vision gateway (qt6_gui.py / HeadlessRunner).

-- ============================================================================
-- camera_slot_regions
-- Stores the 4-point polygon (in camera pixel coords) that maps a physical
-- parking slot to a region in a specific camera's field of view.
-- One slot can appear in multiple cameras; one camera can see multiple slots.
-- ============================================================================

create table if not exists public.camera_slot_regions (
  id          uuid primary key default uuid_generate_v4(),
  lot_id      uuid not null references public.lots(id) on delete cascade,
  device_id   uuid not null references public.devices(id) on delete cascade,  -- the camera device
  slot_id     uuid not null references public.slots(id) on delete cascade,
  polygon     jsonb not null,  -- [[x1,y1],[x2,y2],[x3,y3],[x4,y4]] in DISPLAY_W×DISPLAY_H px
  created_at  timestamptz not null default now(),
  unique (device_id, slot_id)
);

create index if not exists camera_slot_regions_lot_idx    on public.camera_slot_regions (lot_id);
create index if not exists camera_slot_regions_device_idx on public.camera_slot_regions (device_id);

-- RLS: lot members read; managers and gateways write (same pattern as devices)
alter table public.camera_slot_regions enable row level security;

create policy "csr read"  on public.camera_slot_regions for select
  using (public.is_lot_member(lot_id));

create policy "csr write" on public.camera_slot_regions for all
  using  (public.is_lot_manager(lot_id) or public.is_lot_gateway(lot_id))
  with check (public.is_lot_manager(lot_id) or public.is_lot_gateway(lot_id));


-- ============================================================================
-- lot_settings
-- Per-lot configuration for the gateway process (detection thresholds, API
-- port, etc.). Separate from lots to keep the lots table narrow and to allow
-- managers to update settings without touching lot metadata.
-- ============================================================================

create table if not exists public.lot_settings (
  lot_id           uuid primary key references public.lots(id) on delete cascade,
  confidence       float   not null default 0.35,
  debounce_frames  integer not null default 3,
  min_duration     integer not null default 5,   -- seconds; sessions shorter than this are dropped
  api_host         text    not null default '0.0.0.0',
  api_port         integer not null default 8000,
  updated_at       timestamptz not null default now()
);

alter table public.lot_settings enable row level security;

create policy "settings read"  on public.lot_settings for select
  using (public.is_lot_member(lot_id));

create policy "settings write" on public.lot_settings for all
  using  (public.is_lot_manager(lot_id) or public.is_lot_gateway(lot_id))
  with check (public.is_lot_manager(lot_id) or public.is_lot_gateway(lot_id));
