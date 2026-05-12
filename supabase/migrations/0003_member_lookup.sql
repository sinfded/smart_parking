-- Migration 0003: email on profiles, member profile visibility, role update policy,
-- and a find_user_by_email helper for the admin member-management UI.

-- ── profiles.email ────────────────────────────────────────────────────────────
alter table public.profiles add column if not exists email text;

-- Backfill from auth.users (runs as superuser during migration)
update public.profiles p
set email = u.email
from auth.users u
where p.id = u.id;

-- Keep email fresh on new sign-ups / email changes
create or replace function public.handle_new_auth_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, display_name, email)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'display_name', split_part(new.email, '@', 1)),
    new.email
  )
  on conflict (id) do update
    set email = excluded.email,
        display_name = coalesce(profiles.display_name, excluded.display_name);
  return new;
end $$;

-- ── profiles RLS: lot members can read fellow members' profiles ───────────────
-- The existing "profiles self read" policy only allows reading one's own row.
-- Lot admins need to see all members of their lots.
create policy "profiles lot member read" on public.profiles for select
  using (
    id = auth.uid()
    or exists (
      select 1
      from public.lot_members lm_self
      join public.lot_members lm_other on lm_self.lot_id = lm_other.lot_id
      where lm_self.user_id = auth.uid()
        and lm_other.user_id = profiles.id
    )
  );

-- ── lot_members: owners can update roles ──────────────────────────────────────
create policy "members owner update" on public.lot_members for update
  using (
    exists (
      select 1 from public.lot_members
      where lot_id = lot_members.lot_id
        and user_id = auth.uid()
        and role = 'owner'
    )
  );

-- ── find_user_by_email ────────────────────────────────────────────────────────
-- Security-definer so it can read auth.users without exposing the table.
-- Returns null if no user matches.
create or replace function public.find_user_by_email(p_email text)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_id uuid;
begin
  select id into v_id
  from auth.users
  where email = lower(trim(p_email));
  return v_id;
end $$;

grant execute on function public.find_user_by_email(text) to authenticated;
