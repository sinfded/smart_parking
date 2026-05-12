# Smart Parking — Project Context

This file is read by Claude Code and the VS Code extension. It defines the architecture, conventions, and guardrails for this project. **Read this before suggesting changes.**

---

## What this project is

A multi-tenant smart parking platform. Each parking lot runs its own edge stack; all lots share a single Supabase backend; users and lot admins use a web/mobile app built with Nuxt 3.

**Tagline:** sensors decide, cameras verify, cloud coordinates.

---

## Architecture

Three tiers. Do not collapse them — each exists for a specific reason.

### 1. Edge layer (per parking lot)
- **ESP32 + HC-SR04 ultrasonic sensors** — one per slot. Detects occupancy. Publishes to local MQTT.
- **Tapo Wi-Fi cameras** (C100/C200/C210) — entry/exit and audit. Accessed via RTSP (`rtsp://user:pass@<ip>:554/stream1`). The Tapo cloud API is unofficial and not used.
- **Raspberry Pi (or PC) gateway** — runs Mosquitto MQTT broker + a Python service. Subscribes to ESP32 messages, debounces, and pushes state to Supabase via the `report_slot_state` RPC. Buffers writes when offline.

### 2. Cloud layer
- **Supabase** — Postgres, Auth, Realtime, Storage. Single source of truth.
- Multi-tenancy enforced by RLS on `lot_id`. There is no `service_role` key on devices.

### 3. Client layer
- **User app** (`apps/web`, `apps/mobile`) — find lots, see live slot availability, view parking history.
- **Admin dashboard** (`apps/admin`) — lot config, slot map, sensor health, revenue (when added).
- All apps: **Nuxt 3** + **shadcn-vue** + **Tailwind CSS**.

---

## Critical design rules

These are non-negotiable. If a change would violate one, flag it instead of doing it.

1. **ESP32s never talk directly to Supabase.** They publish to the local MQTT broker on the Pi. The Pi mediates. This gives offline tolerance, debouncing, and lower write costs.

2. **Slot state changes go through the `report_slot_state` RPC.** Never `UPDATE slots SET current_state = ...` directly. The RPC atomically updates the slot, appends a `slot_events` row, and opens/closes a `parking_session`.

3. **Sensors decide, cameras verify.** Ultrasonic is the source of truth for occupancy. Camera/YOLO data enriches but does not override.

4. **Two-table state pattern.** `slots.current_state` is updated in place (one row per slot, what the user app reads). `slot_events` is append-only (audit + analytics). Never derive current state from event history at read time.

5. **Each Pi has its own Supabase auth user.** Registered in the `gateways` table linking `auth_user_id` to `lot_id`. RLS treats the Pi like any other authenticated client.

6. **Soft deletes only on `lots` and `slots`.** Use `deleted_at`, not `DELETE`. Historical events must continue to reference these rows.

7. **Multi-tenant from day one.** Every domain table has a `lot_id` column. Every query path is gated by RLS.

---

## Repo layout

```
/edge
  /firmware             — ESP32 PlatformIO project (C++/Arduino)
  /gateway              — Python service for the Pi (uv)
    /gateway
      config.py         — pydantic-settings; all constants live here
      mqtt_listener.py
      debouncer.py
      supabase_writer.py
      health_reporter.py
      /vision           — RTSP capture + YOLO inference (detector.py)
    /tests
    pyproject.toml
    Dockerfile
    .env.example
  docker-compose.yml    — Mosquitto + gateway service

/supabase
  /migrations           — versioned SQL (numbered, never edit applied ones)
  seed.sql

/apps
  /web                  — Nuxt 3 user-facing app
  /admin                — Nuxt 3 admin dashboard
  /mobile               — Nuxt 3 + Capacitor (iOS/Android)

/packages
  /types                — Supabase-generated TS types
  /ui                   — shared shadcn-vue component library
```

---

## Conventions

### General
- **Sentence case** for UI text. Not Title Case.
- **Async by default** in Python and TS.
- **All times are `timestamptz`.** Display in lot's timezone (`lots.timezone`).
- **All IDs are UUIDs** except `slot_events.id` (bigserial).
- **No emojis in code, comments, or commit messages.**

### Python (gateway)
- Python 3.11+. Type hints everywhere. `mypy --strict`.
- `httpx` not `requests`. `aiomqtt` for MQTT. `structlog` for logging.
- Config via `pydantic-settings` in `config.py`. No hardcoded constants elsewhere.
- One module per concern.

### TypeScript / Vue (apps)
- Nuxt 3. shadcn-vue via `shadcn-nuxt`. `@nuxtjs/supabase` for auth + Realtime.
- Pinia for global state. VeeValidate + Zod at trust boundaries.
- Shared types from `@smart-parking/types`. Shared primitives from `@smart-parking/ui`.

### SQL / Supabase
- Migrations are numbered and immutable once committed.
- RLS on every table, no exceptions.
- Indexes on every `(lot_id, ...)` query path.
- Soft deletes: `deleted_at timestamptz`.

---

## MQTT topic schema

```
parking/<lot_id>/slot/<slot_label>/state    — {"distance_cm": 42, "ts": "..."}
parking/<lot_id>/device/<mac>/health        — {"rssi": -67, "uptime": 12345}
parking/<lot_id>/gateway/heartbeat          — {"ts": "..."}
```

---

## Slot state machine

```
unknown → free → occupied → free → ...
                └─ disabled (admin override)
```

- `free → occupied` opens a `parking_session`.
- `occupied → free` closes it.

---

## Debounce rules (Pi gateway)

1. ESP32 samples at 1 Hz, sends every reading to MQTT.
2. Pi keeps a 5-reading rolling window per slot.
3. State change requires 3 consecutive agreeing readings.
4. `< 80 cm` = occupied, `> 120 cm` = free, in-between = ignored.
5. 10-second cooldown after a confirmed change.

Constants live in `edge/gateway/gateway/config.py`.

---

## Security

- No secrets in code or commits. `.env` files are git-ignored.
- The Pi never has the `service_role` key.
- Tapo camera credentials live in the Pi's `.env` only.
- RTSP streams stay on the local network.

---

## Useful commands

```bash
# Supabase local dev
supabase start
supabase db reset
supabase gen types typescript --local > packages/types/src/database.ts

# Gateway
cd edge/gateway
uv sync
uv run python -m gateway.vision.detector --lot <id> --model yolov8n.pt
uv run pytest
uv run mypy .

# Apps
bun --filter web dev
bun --filter admin dev
bun --filter mobile dev
bun run build
```
