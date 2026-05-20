#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS="$ROOT/.dev-logs"
mkdir -p "$LOGS"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${CYAN}[dev]${NC} $*"; }
ok()   { echo -e "${GREEN}[ok]${NC}  $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
die()  { echo -e "${RED}[err]${NC}  $*" >&2; exit 1; }

check_deps() {
  local missing=()
  for cmd in supabase docker bun; do
    command -v "$cmd" &>/dev/null || missing+=("$cmd")
  done
  [[ ${#missing[@]} -eq 0 ]] || die "Missing required tools: ${missing[*]}"
}

stop_all() {
  log "Stopping all services..."

  # Kill tracked background pids
  if [[ -f "$LOGS/pids" ]]; then
    while read -r pid; do
      kill "$pid" 2>/dev/null && echo "  killed $pid" || true
    done < "$LOGS/pids"
    rm -f "$LOGS/pids"
  fi

  # Stop edge docker stack
  if [[ -f "$ROOT/edge/docker-compose.yml" ]]; then
    docker compose -f "$ROOT/edge/docker-compose.yml" down 2>/dev/null || true
  fi

  ok "All services stopped."
}

trap 'echo; stop_all' INT TERM

# ── parse flags ────────────────────────────────────────────────────────────────
SKIP_EDGE=false
SKIP_APPS=false
STOP_MODE=false

for arg in "$@"; do
  case "$arg" in
    --stop)       STOP_MODE=true ;;
    --no-edge)    SKIP_EDGE=true ;;
    --no-apps)    SKIP_APPS=true ;;
    --help|-h)
      cat <<EOF
Usage: ./dev.sh [options]

Options:
  --stop      Stop all running dev services and exit
  --no-edge   Skip the edge Docker stack (Mosquitto + gateway)
  --no-apps   Skip Nuxt apps (web / admin / mobile)
  --help      Show this message

Logs are written to .dev-logs/
EOF
      exit 0
      ;;
  esac
done

if $STOP_MODE; then stop_all; exit 0; fi

check_deps

> "$LOGS/pids"

# ── 1. Supabase ────────────────────────────────────────────────────────────────
log "Starting Supabase..."
supabase start --workdir "$ROOT/supabase" 2>&1 | tee "$LOGS/supabase.log" | grep -E "API URL|anon key|Started" || true
ok "Supabase up"

# ── 2. Edge stack (Mosquitto + gateway) ───────────────────────────────────────
if ! $SKIP_EDGE; then
  if [[ -f "$ROOT/edge/gateway/.env" ]]; then
    log "Starting edge stack (Mosquitto + gateway)..."
    docker compose -f "$ROOT/edge/docker-compose.yml" up -d --build \
      >> "$LOGS/edge.log" 2>&1
    ok "Edge stack up  (logs: .dev-logs/edge.log)"
  else
    warn "edge/gateway/.env not found — skipping edge stack. Copy edge/gateway/.env.example to get started."
  fi
else
  warn "Skipping edge stack (--no-edge)"
fi

# ── 3. Nuxt apps ──────────────────────────────────────────────────────────────
if ! $SKIP_APPS; then
  for app in web admin mobile; do
    log "Starting $app app..."
    bun --filter "$app" dev \
      > "$LOGS/${app}.log" 2>&1 &
    echo $! >> "$LOGS/pids"
    ok "$app dev server started  (logs: .dev-logs/${app}.log)"
  done
fi

# ── summary ───────────────────────────────────────────────────────────────────
echo
echo -e "${GREEN}All services running.${NC} Press Ctrl+C to stop everything."
echo
echo "  Supabase Studio  → http://localhost:54323"
echo "  Web app          → http://localhost:3000"
echo "  Admin app        → http://localhost:3001"
echo "  Mobile app       → http://localhost:3002"
echo "  MQTT broker      → localhost:1883"
echo
echo "  Logs: .dev-logs/{supabase,edge,web,admin,mobile}.log"
echo

# Keep alive so Ctrl+C triggers the trap
wait
