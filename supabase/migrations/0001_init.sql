-- ============================================================================
-- Smart Parking — Supabase schema
-- ============================================================================
-- Run this against a fresh Supabase project. Order matters: types → tables →
-- indexes → RLS → functions → triggers.
--
-- Multi-tenant model: every domain row is scoped by lot_id. RLS enforces that
-- (a) lot owners/staff only see their own lots, (b) end users see public lot
-- info + their own sessions, (c) gateway service accounts only write to the
-- lot they belong to.
-- ============================================================================

create extension if not exists "uuid-ossp";
create extension if not exists "postgis";  -- for lot lat/lng + nearby search

-- ============================================================================
-- ENUMS
-- ============================================================================

create type slot_state    as enum ('free', 'occupied', 'unknown', 'reserved', 'disabled');
create type slot_category as enum ('standard', 'compact', 'motorcycle', 'pwd', 'ev', 'truck');
create type device_kind   as enum ('ultrasonic', 'camera', 'gateway');
create type device_health as enum ('online', 'offline', 'degraded');
create type member_role   as enum ('owner', 'manager', 'staff');

-- ============================================================================
-- IDENTITY & TENANCY
-- ============================================================================

-- Mirror of auth.users with app-level profile fields.
-- Created via trigger when a new auth user signs up.
create table public.profiles (
  id          uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  phone       text,
  plate_number text,        -- user's primary vehicle plate, for quick session matching
  created_at  timestamptz not null default now()
);

-- Parking lots — the tenant boundary.
create table public.lots (
  id          uuid primary key default uuid_generate_v4(),
  name        text not null,
  address     text,
  location    geography(point, 4326),  -- lat/lng for "lots near me"
  total_slots int not null default 0,  -- denormalized, kept fresh by trigger
  is_public   boolean not null default true,  -- listed in user app?
  timezone    text not null default 'Asia/Manila',
  created_at  timestamptz not null default now(),
  deleted_at  timestamptz
);
create index lots_location_idx on public.lots using gist (location) where deleted_at is null;
create index lots_public_idx   on public.lots (is_public) where deleted_at is null;

-- Who can administer which lot. A user can manage multiple lots.
create table public.lot_members (
  lot_id     uuid not null references public.lots(id) on delete cascade,
  user_id    uuid not null references auth.users(id) on delete cascade,
  role       member_role not null default 'staff',
  created_at timestamptz not null default now(),
  primary key (lot_id, user_id)
);
create index lot_members_user_idx on public.lot_members (user_id);

-- ============================================================================
-- LOT TOPOLOGY
-- ============================================================================

-- Optional: zones/sections within a lot ("Basement", "Level 2", "Section A").
-- Useful for big lots; ignore if your lots are small.
create table public.zones (
  id      uuid primary key default uuid_generate_v4(),
  lot_id  uuid not null references public.lots(id) on delete cascade,
  name    text not null,
  sort_order int not null default 0
);
create index zones_lot_idx on public.zones (lot_id);

-- The slots themselves. current_state is updated in place by the Pi gateway;
-- this is what the user app reads via Realtime.
create table public.slots (
  id              uuid primary key default uuid_generate_v4(),
  lot_id          uuid not null references public.lots(id) on delete cascade,
  zone_id         uuid references public.zones(id) on delete set null,
  label           text not null,                       -- "A-12", "B7", etc.
  category        slot_category not null default 'standard',
  current_state   slot_state    not null default 'unknown',
  state_changed_at timestamptz  not null default now(),
  -- For map rendering in admin UI; pixel coords on a lot floorplan, optional.
  map_x           numeric,
  map_y           numeric,
  created_at      timestamptz not null default now(),
  deleted_at      timestamptz,
  unique (lot_id, label)
);
create index slots_lot_idx           on public.slots (lot_id) where deleted_at is null;
create index slots_lot_state_idx     on public.slots (lot_id, current_state) where deleted_at is null;
create index slots_lot_category_idx  on public.slots (lot_id, category, current_state) where deleted_at is null;

-- Devices = the physical things reporting state. ESP32s, cameras, the Pi itself.
-- mac_or_serial lets the Pi route incoming MQTT messages to the right slot.
create table public.devices (
  id            uuid primary key default uuid_generate_v4(),
  lot_id        uuid not null references public.lots(id) on delete cascade,
  slot_id       uuid references public.slots(id) on delete set null,  -- null for cameras/gateways
  kind          device_kind not null,
  mac_or_serial text not null,
  health        device_health not null default 'offline',
  last_seen_at  timestamptz,
  metadata      jsonb not null default '{}'::jsonb,    -- ip, firmware version, model, etc.
  created_at    timestamptz not null default now(),
  unique (lot_id, mac_or_serial)
);
create index devices_lot_idx  on public.devices (lot_id);
create index devices_slot_idx on public.devices (slot_id);

-- Gateway service accounts. Each Pi gets a row here AND a corresponding
-- auth.users entry — auth_user_id links them so RLS can identify which lot
-- a writing gateway belongs to. The api_key column is for non-JWT fallback.
create table public.gateways (
  id            uuid primary key default uuid_generate_v4(),
  lot_id        uuid not null unique references public.lots(id) on delete cascade,
  auth_user_id  uuid unique references auth.users(id) on delete set null,
  name          text not null,
  last_seen_at  timestamptz,
  created_at    timestamptz not null default now()
);

-- ============================================================================
-- LIVE STATE & EVENTS
-- ============================================================================

-- Append-only log. The Pi writes one row per state transition. Powers
-- analytics (occupancy by hour, dwell times) and is the audit trail.
-- Partitioning by month is recommended once this gets large; left as a single
-- table for simplicity.
create table public.slot_events (
  id            bigserial primary key,
  lot_id        uuid not null references public.lots(id) on delete cascade,
  slot_id       uuid not null references public.slots(id) on delete cascade,
  previous_state slot_state,
  new_state     slot_state not null,
  source        text not null default 'ultrasonic',   -- 'ultrasonic' | 'camera' | 'manual'
  confidence    numeric,                              -- e.g. OCR confidence if camera
  occurred_at   timestamptz not null default now(),
  metadata      jsonb not null default '{}'::jsonb    -- plate, snapshot url, raw distance, etc.
);
create index slot_events_lot_time_idx  on public.slot_events (lot_id, occurred_at desc);
create index slot_events_slot_time_idx on public.slot_events (slot_id, occurred_at desc);

-- Parking sessions = "a car was here from T1 to T2". Derived from slot_events
-- but kept as its own table because that's what billing, history, and user
-- "my parking history" screens need. Closed sessions get ended_at set.
create table public.parking_sessions (
  id            uuid primary key default uuid_generate_v4(),
  lot_id        uuid not null references public.lots(id) on delete cascade,
  slot_id       uuid not null references public.slots(id) on delete cascade,
  user_id       uuid references auth.users(id) on delete set null,  -- matched via plate, may be null
  plate_number  text,
  started_at    timestamptz not null default now(),
  ended_at      timestamptz,
  duration_seconds int generated always as (
    case when ended_at is null then null
         else extract(epoch from (ended_at - started_at))::int end
  ) stored,
  metadata      jsonb not null default '{}'::jsonb
);
create index sessions_lot_active_idx   on public.parking_sessions (lot_id) where ended_at is null;
create index sessions_slot_active_idx  on public.parking_sessions (slot_id) where ended_at is null;
create index sessions_user_idx         on public.parking_sessions (user_id, started_at desc);
create index sessions_lot_started_idx  on public.parking_sessions (lot_id, started_at desc);

-- ============================================================================
-- DERIVED VIEW — what the user app reads
-- ============================================================================

create or replace view public.lot_availability as
select
  l.id            as lot_id,
  l.name,
  l.address,
  l.location,
  count(s.id)                                          as total_slots,
  count(s.id) filter (where s.current_state = 'free')  as free_slots,
  count(s.id) filter (where s.current_state = 'occupied') as occupied_slots,
  count(s.id) filter (where s.current_state in ('unknown','disabled')) as other_slots
from public.lots l
left join public.slots s
  on s.lot_id = l.id and s.deleted_at is null
where l.deleted_at is null and l.is_public = true
group by l.id, l.name, l.address, l.location;

-- ============================================================================
-- HELPER FUNCTIONS for RLS
-- ============================================================================

-- Is the calling user a member of this lot (any role)?
create or replace function public.is_lot_member(p_lot_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.lot_members
    where lot_id = p_lot_id and user_id = auth.uid()
  );
$$;

-- Is the calling user a manager or owner (write access to lot config)?
create or replace function public.is_lot_manager(p_lot_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.lot_members
    where lot_id = p_lot_id
      and user_id = auth.uid()
      and role in ('owner', 'manager')
  );
$$;

-- Is the calling user the gateway service account for this lot?
create or replace function public.is_lot_gateway(p_lot_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.gateways
    where lot_id = p_lot_id and auth_user_id = auth.uid()
  );
$$;

-- ============================================================================
-- ROW LEVEL SECURITY
-- ============================================================================

alter table public.profiles         enable row level security;
alter table public.lots             enable row level security;
alter table public.lot_members      enable row level security;
alter table public.zones            enable row level security;
alter table public.slots            enable row level security;
alter table public.devices          enable row level security;
alter table public.gateways         enable row level security;
alter table public.slot_events      enable row level security;
alter table public.parking_sessions enable row level security;

-- profiles: each user manages their own
create policy "profiles self read"   on public.profiles for select using (id = auth.uid());
create policy "profiles self update" on public.profiles for update using (id = auth.uid());
create policy "profiles self insert" on public.profiles for insert with check (id = auth.uid());

-- lots: anyone authenticated can read public lots (for the user app);
-- members can read their own lots even if not public; managers can update.
create policy "lots public read"   on public.lots for select
  using (deleted_at is null and (is_public = true or public.is_lot_member(id)));
create policy "lots manager write" on public.lots for update
  using (public.is_lot_manager(id));
create policy "lots owner insert"  on public.lots for insert
  with check (auth.uid() is not null);
-- After insert, the creator should be added as 'owner' in lot_members
-- (handled by the after-insert trigger below).

-- lot_members: members can see fellow members of lots they belong to;
-- only owners can add/remove members.
create policy "members read same lot" on public.lot_members for select
  using (public.is_lot_member(lot_id));
create policy "members owner insert"  on public.lot_members for insert
  with check (
    exists (select 1 from public.lot_members
            where lot_id = lot_members.lot_id and user_id = auth.uid() and role = 'owner')
  );
create policy "members owner delete"  on public.lot_members for delete
  using (
    exists (select 1 from public.lot_members
            where lot_id = lot_members.lot_id and user_id = auth.uid() and role = 'owner')
  );

-- zones, slots: readable by anyone for public lots; writable by managers + gateways
create policy "zones read"    on public.zones for select
  using (exists (select 1 from public.lots l
                 where l.id = zones.lot_id
                   and l.deleted_at is null
                   and (l.is_public or public.is_lot_member(l.id))));
create policy "zones write"   on public.zones for all
  using (public.is_lot_manager(lot_id))
  with check (public.is_lot_manager(lot_id));

create policy "slots read"    on public.slots for select
  using (deleted_at is null and exists (
    select 1 from public.lots l
    where l.id = slots.lot_id
      and l.deleted_at is null
      and (l.is_public or public.is_lot_member(l.id))
  ));
create policy "slots manager write" on public.slots for all
  using (public.is_lot_manager(lot_id))
  with check (public.is_lot_manager(lot_id));
-- Gateways update only current_state + state_changed_at via the rpc below;
-- they don't get general slot write access.

-- devices, gateways: members read; managers write; gateway can update its own row
create policy "devices read"  on public.devices for select using (public.is_lot_member(lot_id));
create policy "devices write" on public.devices for all
  using (public.is_lot_manager(lot_id) or public.is_lot_gateway(lot_id))
  with check (public.is_lot_manager(lot_id) or public.is_lot_gateway(lot_id));

create policy "gateways read"  on public.gateways for select using (public.is_lot_member(lot_id));
create policy "gateways write" on public.gateways for all
  using (public.is_lot_manager(lot_id))
  with check (public.is_lot_manager(lot_id));

-- slot_events: members read full history; gateways insert
create policy "events member read" on public.slot_events for select
  using (public.is_lot_member(lot_id));
create policy "events gateway insert" on public.slot_events for insert
  with check (public.is_lot_gateway(lot_id));

-- parking_sessions: lot members see all sessions in their lot; users see their own
create policy "sessions member read" on public.parking_sessions for select
  using (public.is_lot_member(lot_id) or user_id = auth.uid());
create policy "sessions gateway write" on public.parking_sessions for all
  using (public.is_lot_gateway(lot_id) or public.is_lot_manager(lot_id))
  with check (public.is_lot_gateway(lot_id) or public.is_lot_manager(lot_id));

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Create a profile row when a new auth user signs up.
create or replace function public.handle_new_auth_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, display_name)
  values (new.id, coalesce(new.raw_user_meta_data->>'display_name', split_part(new.email, '@', 1)))
  on conflict (id) do nothing;
  return new;
end $$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_auth_user();

-- Add the creator as 'owner' when a lot is inserted.
create or replace function public.handle_new_lot()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  if auth.uid() is not null then
    insert into public.lot_members (lot_id, user_id, role)
    values (new.id, auth.uid(), 'owner')
    on conflict do nothing;
  end if;
  return new;
end $$;

drop trigger if exists on_lot_created on public.lots;
create trigger on_lot_created
after insert on public.lots
for each row execute function public.handle_new_lot();

-- Keep lots.total_slots fresh.
create or replace function public.refresh_lot_total_slots()
returns trigger language plpgsql as $$
declare
  target_lot uuid;
begin
  target_lot := coalesce(new.lot_id, old.lot_id);
  update public.lots
  set total_slots = (select count(*) from public.slots
                     where lot_id = target_lot and deleted_at is null)
  where id = target_lot;
  return null;
end $$;

create trigger slots_total_count
after insert or update of deleted_at or delete on public.slots
for each row execute function public.refresh_lot_total_slots();

-- ============================================================================
-- RPC: the only way gateways change slot state
-- ============================================================================
-- The Pi calls this via PostgREST. It (1) updates slots.current_state,
-- (2) appends a slot_events row, (3) opens/closes a parking_session — all
-- atomically. Avoids the Pi having to issue three separate writes that could
-- race or partially fail.

create or replace function public.report_slot_state(
  p_slot_id      uuid,
  p_new_state    slot_state,
  p_source       text default 'ultrasonic',
  p_confidence   numeric default null,
  p_plate_number text default null,
  p_metadata     jsonb default '{}'::jsonb
) returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_lot_id    uuid;
  v_prev      slot_state;
begin
  select lot_id, current_state into v_lot_id, v_prev
  from public.slots where id = p_slot_id and deleted_at is null;

  if v_lot_id is null then
    raise exception 'unknown slot %', p_slot_id;
  end if;

  -- Authorization: caller must be the gateway for this lot (or a manager doing manual override).
  if not (public.is_lot_gateway(v_lot_id) or public.is_lot_manager(v_lot_id)) then
    raise exception 'not authorized for lot %', v_lot_id;
  end if;

  if v_prev is distinct from p_new_state then
    update public.slots
    set current_state = p_new_state,
        state_changed_at = now()
    where id = p_slot_id;

    insert into public.slot_events (lot_id, slot_id, previous_state, new_state, source, confidence, metadata)
    values (v_lot_id, p_slot_id, v_prev, p_new_state, p_source, p_confidence, p_metadata);

    -- Session bookkeeping: open on free->occupied, close on occupied->free.
    if v_prev in ('free','unknown') and p_new_state = 'occupied' then
      insert into public.parking_sessions (lot_id, slot_id, plate_number, metadata)
      values (v_lot_id, p_slot_id, p_plate_number, p_metadata);
    elsif v_prev = 'occupied' and p_new_state in ('free','unknown') then
      update public.parking_sessions
      set ended_at = now()
      where slot_id = p_slot_id and ended_at is null;
    end if;
  end if;
end $$;

grant execute on function public.report_slot_state(uuid, slot_state, text, numeric, text, jsonb) to authenticated;

-- ============================================================================
-- REALTIME
-- ============================================================================
-- Enable Realtime on slots so the user app gets live updates.
-- (In Supabase Dashboard: Database → Replication → enable for these tables,
--  or run the ALTER PUBLICATION below.)
alter publication supabase_realtime add table public.slots;
alter publication supabase_realtime add table public.lots;
