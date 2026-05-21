-- Migration 0008: confidence guard + source-priority arbitration in report_slot_state
--
-- Problem: two cameras watching the same slot can produce conflicting readings.
--          The old RPC was pure last-write-wins with no arbitration.
--
-- Rules applied (in order, non-manual sources only):
--   1. Sensor priority — ultrasonic always beats camera for 30 s after its last report.
--   2. Confidence guard — a higher-confidence conflicting report within 10 s blocks
--      the lower-confidence one, regardless of source.
--
-- Manual overrides (p_source = 'manual') bypass all guards.

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
  v_lot_id uuid;
  v_prev   slot_state;
begin
  select lot_id, current_state
    into v_lot_id, v_prev
    from public.slots
   where id = p_slot_id and deleted_at is null;

  if v_lot_id is null then
    raise exception 'unknown slot %', p_slot_id;
  end if;

  if not (public.is_lot_gateway(v_lot_id) or public.is_lot_manager(v_lot_id)) then
    raise exception 'not authorized for lot %', v_lot_id;
  end if;

  -- ── Conflict arbitration (skipped for manual overrides) ─────────────────────

  if p_source <> 'manual' then

    -- Rule 1: ultrasonic beats camera.
    -- If an ultrasonic report disagrees with us within the last 30 seconds, drop
    -- the camera reading entirely.
    if p_source = 'camera' and exists (
      select 1 from public.slot_events
       where slot_id   = p_slot_id
         and source    = 'ultrasonic'
         and new_state <> p_new_state
         and occurred_at > now() - interval '30 seconds'
    ) then
      return;
    end if;

    -- Rule 2: confidence guard.
    -- If a conflicting report with strictly higher confidence arrived within the
    -- last 10 seconds, the current reading loses the tie-break.
    if p_confidence is not null and exists (
      select 1 from public.slot_events
       where slot_id    = p_slot_id
         and new_state  <> p_new_state
         and confidence >  p_confidence
         and occurred_at > now() - interval '10 seconds'
    ) then
      return;
    end if;

  end if;

  -- ── Apply state change ───────────────────────────────────────────────────────

  if v_prev is distinct from p_new_state then
    update public.slots
       set current_state    = p_new_state,
           state_changed_at = now()
     where id = p_slot_id;

    insert into public.slot_events
      (lot_id, slot_id, previous_state, new_state, source, confidence, metadata)
    values
      (v_lot_id, p_slot_id, v_prev, p_new_state, p_source, p_confidence, p_metadata);

    -- Session bookkeeping
    if v_prev in ('free', 'unknown') and p_new_state = 'occupied' then
      insert into public.parking_sessions (lot_id, slot_id, plate_number, metadata)
      values (v_lot_id, p_slot_id, p_plate_number, p_metadata);
    elsif v_prev = 'occupied' and p_new_state in ('free', 'unknown') then
      update public.parking_sessions
         set ended_at = now()
       where slot_id = p_slot_id and ended_at is null;
    end if;
  end if;
end $$;
