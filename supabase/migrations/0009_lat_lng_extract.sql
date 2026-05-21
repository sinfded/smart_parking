-- Migration 0009: expose lat/lng as plain floats in lot_availability and lots_nearby
--
-- PostgREST serialises geography columns as hex-encoded EWKB, not GeoJSON.
-- Adding explicit ST_Y / ST_X columns gives clients plain float8 values they can
-- use directly without decoding EWKB.

-- DROP required because CREATE OR REPLACE VIEW cannot reorder/insert columns
drop view if exists public.lot_availability cascade;

create view public.lot_availability as
select
  l.id                                                      as lot_id,
  l.name,
  l.address,
  l.location,
  ST_Y(l.location::geometry)                               as lat,
  ST_X(l.location::geometry)                               as lng,
  count(s.id)                                               as total_slots,
  count(s.id) filter (where s.current_state = 'free')       as free_slots,
  count(s.id) filter (where s.current_state = 'occupied')   as occupied_slots,
  count(s.id) filter (where s.current_state in ('unknown','disabled')) as other_slots
from public.lots l
left join public.slots s
  on s.lot_id = l.id and s.deleted_at is null
where l.deleted_at is null and l.is_public = true
group by l.id, l.name, l.address, l.location;

drop function if exists public.lots_nearby(double precision, double precision, int);

create or replace function public.lots_nearby(
  p_lat            double precision,
  p_lng            double precision,
  p_radius_meters  int default 5000
)
returns table (
  lot_id          uuid,
  name            text,
  address         text,
  location        geography,
  lat             double precision,
  lng             double precision,
  total_slots     bigint,
  free_slots      bigint,
  occupied_slots  bigint,
  other_slots     bigint,
  distance_meters double precision
)
language sql
stable
security definer
set search_path = public
as $$
  select
    la.lot_id,
    la.name,
    la.address,
    la.location,
    la.lat,
    la.lng,
    la.total_slots,
    la.free_slots,
    la.occupied_slots,
    la.other_slots,
    ST_Distance(
      l.location,
      ST_MakePoint(p_lng, p_lat)::geography
    ) as distance_meters
  from public.lot_availability la
  join public.lots l on l.id = la.lot_id
  where l.deleted_at is null
    and l.is_public = true
    and l.location is not null
    and ST_DWithin(
      l.location,
      ST_MakePoint(p_lng, p_lat)::geography,
      p_radius_meters
    )
  order by distance_meters;
$$;

grant execute on function public.lots_nearby(double precision, double precision, int) to anon, authenticated;
