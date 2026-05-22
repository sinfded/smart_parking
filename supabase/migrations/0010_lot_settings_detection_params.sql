-- Adds missing detection-tuning columns to lot_settings.
-- window_size      : rolling window length used for both occupied/free vote counts
-- overlap_threshold: minimum fraction of the slot polygon covered by a bounding box
--                    to count as a detection hit
-- clahe_clip_limit : CLAHE clip limit for shadow/lighting normalisation before
--                    inference (0.0 disables CLAHE)
alter table public.lot_settings
  add column if not exists window_size        integer not null default 8,
  add column if not exists overlap_threshold  float   not null default 0.40,
  add column if not exists clahe_clip_limit   float   not null default 2.0;
