-- Adds a separate debounce threshold for confirming a slot is free.
-- debounce_frames     = consecutive detected frames  → confirmed occupied (fast)
-- debounce_frames_free = consecutive empty frames    → confirmed free    (slow)
alter table public.lot_settings
  add column if not exists debounce_frames_free int not null default 10;
