# Smart Parking

Multi-tenant smart parking platform. Ultrasonic sensors detect occupancy, a Raspberry Pi gateway bridges the edge to Supabase, and a Nuxt 3 admin dashboard ties it together.

```
ESP32 (5 sensors) ──MQTT──► Pi gateway ──RPC──► Supabase ◄── Admin dashboard
                                                          ◄── Mobile PWA
```

---

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| [Bun](https://bun.sh) | 1.x | JS runtime + package manager for all apps |
| [uv](https://docs.astral.sh/uv/) | 0.4+ | Python package manager for the gateway |
| [Supabase CLI](https://supabase.com/docs/guides/cli) | latest | Database migrations |
| [PlatformIO CLI](https://docs.platformio.org/en/latest/core/installation/index.html) | latest | ESP32 firmware |
| Docker + Docker Compose | — | MQTT broker + gateway on the Pi |

---

## 1. Supabase

### Hosted (production)

1. Create a project at [supabase.com](https://supabase.com).
2. Copy your **project URL** and **anon key** (starts with `eyJ...`) from **Settings → API**.
3. Apply the schema:

```bash
supabase link --project-ref <your-project-ref>
supabase db push
```

> The single migration file is `supabase/migrations/0000_app.sql`. It creates all tables, RLS policies, functions, triggers, and enables Realtime on `slots` and `lots`.

4. (Optional) Seed initial data:

```bash
supabase db execute --file supabase/seed.sql
```

### Local dev

```bash
supabase start          # starts Postgres + Auth + Realtime + Studio
supabase db reset       # applies migrations + seed.sql from scratch

# Regenerate TypeScript types after schema changes
supabase gen types typescript --local > packages/types/src/database.ts
```

Local Studio runs at `http://localhost:54323`.

---

## 2. Admin dashboard

### Setup

```bash
cd apps/admin
bun install
cp .env.example .env   # then fill in the values below
bun run dev            # http://localhost:3000
```

`.env`:

```env
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...   # anon/public key
```

> Use the JWT anon key (starts with `eyJ`), not the `sb_publishable_` format — the Nuxt Supabase module requires a JWT.

### Initial configuration

After logging in for the first time:

1. **Create a lot** — Lots → New lot. Copy the lot UUID from the URL.
2. **Add slots** — open the lot → Slots → add each slot with a label matching what you will enter on the ESP32 (e.g. `S-01`, `S-02`).
3. **Create a gateway user** — in Supabase Dashboard → Authentication → Users → Invite user. Use a dedicated email (e.g. `gateway-lot1@yourapp.com`). Then insert a row in the `gateways` table linking `auth_user_id` to `lot_id`.
4. **Register devices** — Devices → Add device → select `ultrasonic`, enter the ESP32 MAC address, select the lot and slot.

---

## 3. Edge layer (Raspberry Pi)

### 3a. Environment file

```bash
cp edge/gateway/.env.example edge/gateway/.env
```

Fill in `edge/gateway/.env`:

```env
# Supabase
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...   # anon/public key

# Gateway identity — must match a row in the gateways table
LOT_ID=<lot-uuid>
GATEWAY_EMAIL=gateway-lot1@yourapp.com
GATEWAY_PASSWORD=<gateway-password>

# MQTT broker (Mosquitto running on this Pi)
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883

# Debounce thresholds (optional — defaults shown)
DISTANCE_OCCUPIED_CM=80.0
DISTANCE_FREE_CM=120.0
ROLLING_WINDOW=5
CONFIRM_READINGS=3
COOLDOWN_SECONDS=10
```

### 3b. Start with Docker (recommended)

```bash
cd edge
docker compose up -d
```

This starts:
- **Mosquitto** on port `1883` — receives readings from all ESP32s
- **Gateway service** — subscribes to MQTT, debounces readings, calls `report_slot_state` RPC

View logs:

```bash
docker compose logs -f gateway
docker compose logs -f mosquitto
```

### 3c. Run without Docker (uv)

```bash
cd edge/gateway
uv sync
uv run python -m gateway.main
```

### 3d. Run as a systemd service

Create `/etc/systemd/system/parking-gateway.service`:

```ini
[Unit]
Description=Smart Parking Gateway
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=/home/pi/smart_parking/edge/gateway
EnvironmentFile=/home/pi/smart_parking/edge/gateway/.env
ExecStart=/home/pi/smart_parking/edge/gateway/.venv/bin/python -m gateway.main
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable parking-gateway
sudo systemctl start parking-gateway
sudo journalctl -u parking-gateway -f
```

---

## 4. ESP32 firmware

Each ESP32 drives up to **5 HC-SR04 ultrasonic sensors**. Configuration is done via a built-in web portal — no reflashing needed to change settings.

### Install PlatformIO

```bash
python3 -m venv ~/.platformio-venv
~/.platformio-venv/bin/pip install platformio
echo 'export PATH="$HOME/.platformio-venv/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Flash

Connect the ESP32 via USB, then:

```bash
cd edge/firmware

# Build and upload (downloads toolchain on first run — takes a few minutes)
pio run --target upload

# Open serial monitor
pio device monitor
```

If the upload hangs at `Connecting......`, hold the **BOOT** button on the ESP32 until it says `Writing...`, then release.

### Provision via web portal

On first boot (or after a factory reset), the ESP32 broadcasts a Wi-Fi access point:

1. Connect your phone or laptop to **`SmartParking-Setup`**
2. Open **`192.168.4.1`** in a browser (the page opens automatically as a captive portal on most phones)
3. Fill in the form:

| Field | Value |
|---|---|
| Wi-Fi SSID | Your parking lot Wi-Fi network |
| Wi-Fi password | Wi-Fi password |
| MQTT broker IP | Pi's local IP address (e.g. `192.168.0.110`) |
| MQTT port | `1883` |
| Lot ID | UUID from the admin dashboard |
| Slot label 1–5 | Must exactly match slot labels created in admin (e.g. `S-01`). Leave blank to disable a sensor. |
| Trigger / Echo pins | GPIO pin numbers per sensor (see default wiring below) |

4. Tap **Save and reboot** — the ESP32 connects to Wi-Fi and starts publishing readings.

### Default pin wiring (5 sensors)

| Sensor | TRIG | ECHO |
|--------|------|------|
| 1 | 5 | 18 |
| 2 | 13 | 19 |
| 3 | 14 | 21 |
| 4 | 23 | 22 |
| 5 | 25 | 26 |

### Factory reset

Hold the **BOOT** button (GPIO 0) for **3 seconds** while the ESP32 is running. The serial monitor will show:

```
[boot] Config cleared — rebooting.
```

The device will restart and broadcast `SmartParking-Setup` again.

### Find the ESP32 MAC address

The MAC address is printed in the serial monitor on every boot:

```
[wifi] Connected.
[mqtt] Connected to 192.168.0.110:1883
```

It is also part of the MQTT client ID (e.g. `esp32-aabbccddeeff`). Use this when registering the device in the admin panel under **Devices**.

### Monitor live readings

From any machine on the same network as the Pi:

```bash
mosquitto_sub -h <pi-ip> -t "parking/#" -v
```

---

## 5. Mobile PWA

Browse-only app for users to check live slot availability.

```bash
cd apps/mobile
bun install
cp .env.example .env   # same SUPABASE_URL and SUPABASE_KEY as admin
bun run dev
```

No authentication required — the app reads public lot data directly from Supabase.

---

## 6. Run everything (monorepo)

```bash
bun install

bun --filter admin dev    # admin dashboard  → http://localhost:3000
bun --filter mobile dev   # mobile PWA       → http://localhost:3001
bun run build             # build all apps
```

---

## Architecture reference

### MQTT topic schema

```
parking/<lot_id>/slot/<slot_label>/state    {"distance_cm": "42.3", "ts": "2026-05-16T14:23:01+08:00"}
parking/<lot_id>/device/<mac>/health        {"rssi": -67, "uptime": 12345}
parking/<lot_id>/gateway/heartbeat          {"ts": "..."}
```

### Slot state machine

```
unknown → free → occupied → free → ...
                └─ disabled  (admin override)
```

- `free → occupied` opens a `parking_session`
- `occupied → free` closes it

State changes always go through the `report_slot_state` RPC — never a direct `UPDATE`.

### Debounce rules (Pi gateway)

1. ESP32 samples at 1 Hz and sends every reading.
2. Gateway keeps a 5-reading rolling window per slot.
3. State change requires 3 consecutive agreeing readings.
4. `< 80 cm` = occupied · `> 120 cm` = free · in-between = ignored.
5. 10-second cooldown after each confirmed change.

Thresholds are tunable via `.env` — see `edge/gateway/gateway/config.py`.

### Design rules

- ESP32s never talk directly to Supabase — all writes go through the Pi gateway.
- Slot state changes go through `report_slot_state` RPC only (atomic: updates slot + appends event + opens/closes session).
- Each Pi has its own Supabase auth user registered in the `gateways` table.
- Soft deletes only on `lots` and `slots` — use `deleted_at`, never `DELETE`.
- Every domain table has a `lot_id` column gated by RLS.
