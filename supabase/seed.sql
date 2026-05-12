-- Local dev seed — run after migrations
-- supabase db reset will apply migrations then this file automatically

-- Insert a test lot
insert into public.lots (id, name, address, timezone)
values (
  '00000000-0000-0000-0000-000000000001',
  'Test Lot',
  '123 Main St',
  'Asia/Manila'
);

-- Insert a camera device for the test lot
insert into public.devices (id, lot_id, kind, mac_or_serial, metadata)
values (
  '00000000-0000-0000-0000-000000000010',
  '00000000-0000-0000-0000-000000000001',
  'camera',
  'AA:BB:CC:DD:EE:FF',
  '{"name": "Entrance Cam", "url": "rtsp://user:pass@192.168.0.100:554/stream1", "position": 0}'
);

-- Insert a couple of test slots
insert into public.slots (id, lot_id, label, category)
values
  ('00000000-0000-0000-0000-000000000020', '00000000-0000-0000-0000-000000000001', 'A-01', 'standard'),
  ('00000000-0000-0000-0000-000000000021', '00000000-0000-0000-0000-000000000001', 'A-02', 'standard');
