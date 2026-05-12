# Smart Parking

Multi-tenant parking platform. Ultrasonic sensors detect occupancy, Tapo cameras verify it, a Raspberry Pi gateway bridges the edge to Supabase, and a Nuxt 3 admin dashboard ties it together.

```
ESP32 sensors  ──MQTT──►  Pi gateway  ──RPC──►  Supabase  ◄──  Admin / User apps
Tapo cameras   ──RTSP──►  Pi vision
```

---

## Prerequisites

| Tool | Purpose |
|---|---|
| [Bun](https://bun.sh) | JS runtime + package manager for all apps |
| [uv](https://docs.astral.sh/uv/) | Python package manager for the gateway |
| [Supabase CLI](https://supabase.com/docs/guides/local-development/cli/getting-started) | Local database dev |
| [PlatformIO CLI](https://docs.platformio.org/en/latest/core/installation/index.html) | ESP32 firmware |
| Docker + Docker Compose | MQTT broker + gateway container on the Pi |

---

## 1. Supabase

### Hosted (production)

1. Create a project at [supabase.com](https://supabase.com).
2. Copy your project URL and anon key from **Settings > API**.
3. Apply migrations:

```bash
supabase link --project-ref <your-project-ref>
supabase db push
```

4. (Optional) Seed initial data:

```bash
supabase db execute --file supabase/seed.sql
```

### Local dev

```bash
supabase start          # starts Postgres + Auth + Realtime + Studio
supabase db reset       # applies all migrations + seed.sql from scratch

# Regenerate TypeScript types after schema changes
supabase gen types typescript --local > packages/types/src/database.ts
```

Local Studio runs at `http://localhost:54323`.

---

## 2. Edge layer (Raspberry Pi)

Everything below runs on the Pi. Copy the `edge/` folder to the Pi or clone the repo there.

### 2a. Environment file

Create `edge/gateway/.env` from the example:

```bash
cp edge/gateway/.env.example edge/gateway/.env
```

Edit it with your values:

```env
# Supabase — use the gateway service account key (NOT anon, NOT service_role)
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_KEY=<gateway-publishable-key>

# Gateway identity — must match a row in the gateways table
GATEWAY_EMAIL=gateway@yourdomain.com
GATEWAY_PASSWORD=<gateway-password>

# MQTT broker (Mosquitto running on this Pi)
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883

# Camera detection thresholds (optional — can also be set in the admin UI)
CAMERA_CONFIDENCE=0.35
CAMERA_DEBOUNCE_FRAMES=3
CAMERA_MIN_DURATION=5
API_HOST=0.0.0.0
API_PORT=8000
```

### 2b. Start MQTT broker + gateway (Docker)

```bash
cd edge
docker compose up -d
```

This starts:
- **Mosquitto** on port `1883` — receives readings from all ESP32 sensors
- **Gateway service** — subscribes to MQTT, debounces readings, pushes state to Supabase via `report_slot_state` RPC

View logs:

```bash
docker compose logs -f gateway
docker compose logs -f mosquitto
```

### 2c. Run the gateway without Docker (uv)

```bash
cd edge/gateway
uv sync --extra pi
uv run parking-gateway
```

### 2d. Vision detector (Pi — headless)

The vision detector opens RTSP streams from the Tapo cameras, runs YOLO inference, and updates slot state in Supabase when the camera disagrees with the sensor.

Install and run:

```bash
cd edge/gateway
uv sync --extra pi        # installs opencv-python-headless

# Run with lot auto-detected (only works if there is exactly one lot)
uv run parking-vision --lot <lot-uuid>

# Specify a lighter model explicitly (yolov8n is the default on Pi)
uv run parking-vision --lot <lot-uuid> --model yolov8n.pt

# Credentials from env — or pass as flags
uv run parking-vision --lot <lot-uuid> --email gateway@yourdomain.com --password <pw>
```

The detector exposes a local HTTP API on port `8000`:

| Endpoint | Description |
|---|---|
| `GET /` | Live camera feed dashboard |
| `GET /status` | Slot occupancy summary (JSON) |
| `GET /events` | Recent enter/exit events (JSON) |
| `GET /stream/{n}` | MJPEG stream for camera `n` |

#### Run as a systemd service on the Pi

Create `/etc/systemd/system/parking-vision.service`:

```ini
[Unit]
Description=Smart Parking Vision Detector
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=/home/pi/smart_parking/edge/gateway
EnvironmentFile=/home/pi/smart_parking/edge/gateway/.env
ExecStart=/home/pi/smart_parking/edge/gateway/.venv/bin/parking-vision --lot <lot-uuid>
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable parking-vision
sudo systemctl start parking-vision
sudo journalctl -u parking-vision -f
```

---

## 3. Vision detector (PC — with live preview window)

Useful for development, slot region drawing, and debugging camera angles.

```bash
cd edge/gateway
uv sync --extra pc        # installs opencv-python (with GUI)

# Interactive lot picker + live cv2 preview window
uv run parking-vision-pc

# Non-interactive (lot UUID known)
uv run parking-vision-pc --lot <lot-uuid>

# Use a larger model (PC can handle it)
uv run parking-vision-pc --lot <lot-uuid> --model yolov8s.pt

# Headless mode (no window — stream via HTTP only)
uv run parking-vision-pc --lot <lot-uuid> --no-display
```

Press **Q** or **Esc** in the preview window to stop.

---

## 4. ESP32 firmware

One ESP32 + HC-SR04 sensor per parking slot.

### Configure

Edit `edge/firmware/platformio.ini` and set the `build_flags` for each device:

```ini
build_flags =
    -DWIFI_SSID=\"your_wifi_ssid\"
    -DWIFI_PASS=\"your_wifi_password\"
    -DMQTT_HOST=\"192.168.0.x\"   ; Pi's local IP
    -DMQTT_PORT=1883
    -DLOT_ID=\"<lot-uuid>\"
    -DSLOT_LABEL=\"A-01\"          ; unique per slot, must match slots table
    -DTRIGGER_PIN=5
    -DECHO_PIN=18
```

### Flash

```bash
cd edge/firmware

# Build and upload
pio run --target upload

# Monitor serial output
pio device monitor --baud 115200
```

Each ESP32 publishes to `parking/<lot_id>/slot/<slot_label>/state` at 1 Hz.

---

## 5. Admin dashboard

```bash
cd apps/admin
bun install

# Create env file
cp .env.example .env
# Set SUPABASE_URL and SUPABASE_ANON_KEY inside .env

bun run dev      # http://localhost:3000
bun run build    # production build
bun run preview  # preview production build
```

---

## 6. User web app

```bash
cd apps/web
bun install
bun run dev
```

---

## 7. Run everything (dev monorepo)

From the repo root:

```bash
bun install

bun --filter admin dev    # admin dashboard
bun --filter web dev      # user app
bun run build             # build all apps
```

---

## MQTT topic schema

```
parking/<lot_id>/slot/<slot_label>/state    {"distance_cm": 42, "ts": 12345}
parking/<lot_id>/device/<mac>/health        {"rssi": -67, "uptime": 12345}
parking/<lot_id>/gateway/heartbeat          {"ts": "..."}
```

---

## Slot state machine

```
unknown → free → occupied → free → ...
                └─ disabled  (admin override)
```

- `free → occupied` opens a `parking_session`
- `occupied → free` closes it

State changes always go through the `report_slot_state` RPC — never a direct `UPDATE`.

---

## Debounce rules

The Pi gateway applies these rules before writing to Supabase:

1. ESP32 samples at 1 Hz and sends every reading.
2. Gateway keeps a 5-reading rolling window per slot.
3. State change requires 3 consecutive agreeing readings.
4. `< 80 cm` = occupied · `> 120 cm` = free · in-between = ignored.
5. 10-second cooldown after each confirmed change.

Constants are in [`edge/gateway/gateway/config.py`](edge/gateway/gateway/config.py).
