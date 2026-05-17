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
