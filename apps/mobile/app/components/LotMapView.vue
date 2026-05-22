<script setup lang="ts">
import { LocateFixed, Loader2 } from "lucide-vue-next";
import type { Map, Marker } from "leaflet";

interface LotPin {
  lot_id: string;
  name: string;
  address: string | null;
  total_slots: number;
  free_slots: number;
  lat: number | null;
  lng: number | null;
}

const props = defineProps<{
  lots: LotPin[];
  userLat?: number | null;
  userLng?: number | null;
  centerLat?: number | null;
  centerLng?: number | null;
}>();

// ── Leaflet instances (not reactive — plain refs avoid proxy overhead on maps) ─
const mapRef = useTemplateRef<HTMLDivElement>("mapEl");
let map: Map | null = null;
let leafletLib: typeof import("leaflet") | null = null;
let lotMarkers: Marker[] = [];
let userMarker: Marker | null = null;

// ── Locate me ─────────────────────────────────────────────────────────────────
const locating = ref(false);

function locateUser() {
  if (!navigator.geolocation || !map || !leafletLib) return;
  locating.value = true;
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      locating.value = false;
      placeUserMarker(leafletLib!, pos.coords.latitude, pos.coords.longitude);
      map!.setView([pos.coords.latitude, pos.coords.longitude], 17);
    },
    () => { locating.value = false; },
    { enableHighAccuracy: true, timeout: 10_000 },
  );
}

// ── Availability helpers ──────────────────────────────────────────────────────

function availColor(lot: LotPin): string {
  if (!lot.total_slots || lot.free_slots === 0) return "#ef4444";
  const ratio = lot.free_slots / lot.total_slots;
  if (ratio < 0.2) return "#f59e0b";
  return "#10b981";
}

function markerHtml(lot: LotPin): string {
  const color = availColor(lot);
  const label = lot.free_slots === 0 ? "FULL" : String(lot.free_slots);
  const fontSize = lot.free_slots === 0 ? "9px" : "15px";
  return `<div style="
    width:42px;height:42px;border-radius:50%;
    background:${color};color:#fff;
    display:flex;align-items:center;justify-content:center;
    font-size:${fontSize};font-weight:700;
    font-family:Outfit,ui-sans-serif,sans-serif;
    border:3px solid #fff;
    box-shadow:0 2px 10px rgba(0,0,0,0.28);">
    ${label}
  </div>`;
}

function popupHtml(lot: LotPin): string {
  const color = availColor(lot);
  const addr = lot.address
    ? `<p style="font-size:12px;color:#71717a;margin:0 0 8px;line-height:1.3">${lot.address}</p>`
    : "";
  return `
    <div style="font-family:Outfit,ui-sans-serif,sans-serif;min-width:190px;max-width:240px">
      <p style="font-weight:700;font-size:14px;margin:0 0 2px;line-height:1.3">${lot.name}</p>
      ${addr}
      <p style="font-size:13px;margin:0 0 10px">
        <strong style="color:${color}">${lot.free_slots}</strong>
        <span style="color:#71717a"> / ${lot.total_slots} available</span>
      </p>
      <a href="/lots/${lot.lot_id}"
         style="display:block;text-align:center;background:#2563eb;color:#fff;
                padding:8px 12px;border-radius:8px;text-decoration:none;
                font-size:13px;font-weight:600;">
        View lot
      </a>
    </div>`;
}

// ── Map lifecycle ─────────────────────────────────────────────────────────────

onMounted(async () => {
  const L = await import("leaflet");
  leafletLib = L;
  if (!mapRef.value) return;

  map = L.map(mapRef.value, { zoomControl: true });

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "© OpenStreetMap contributors",
    maxZoom: 19,
  }).addTo(map);

  renderLotMarkers(L);
  renderUserMarker(L);
  fitView(L);

  watch(
    () => props.lots,
    () => {
      clearLotMarkers();
      renderLotMarkers(L);
      fitView(L);
    },
  );

  watch(
    () => [props.userLat, props.userLng],
    () => {
      renderUserMarker(L);
      if (props.userLat != null && props.userLng != null) {
        map!.setView([props.userLat, props.userLng], 15);
      }
    },
  );
});

onUnmounted(() => {
  map?.remove();
  map = null;
  leafletLib = null;
});

// ── Rendering helpers ─────────────────────────────────────────────────────────

function clearLotMarkers() {
  lotMarkers.forEach((m) => m.remove());
  lotMarkers = [];
}

function placeUserMarker(L: typeof import("leaflet"), lat: number, lng: number) {
  userMarker?.remove();
  userMarker = null;
  const icon = L.divIcon({
    html: `<div style="
      width:16px;height:16px;border-radius:50%;
      background:#2563eb;border:3px solid #fff;
      box-shadow:0 0 0 4px rgba(37,99,235,0.25)"></div>`,
    className: "",
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  });
  userMarker = L.marker([lat, lng], { icon }).addTo(map!);
}

function renderLotMarkers(L: typeof import("leaflet")) {
  for (const lot of props.lots) {
    if (lot.lat == null || lot.lng == null) continue;
    const icon = L.divIcon({
      html: markerHtml(lot),
      className: "",
      iconSize: [42, 42],
      iconAnchor: [21, 21],
      popupAnchor: [0, -26],
    });
    const marker = L.marker([lot.lat, lot.lng], { icon })
      .bindPopup(popupHtml(lot), { maxWidth: 260 })
      .addTo(map!);
    lotMarkers.push(marker);
  }
}

function renderUserMarker(L: typeof import("leaflet")) {
  if (props.userLat == null || props.userLng == null) {
    userMarker?.remove();
    userMarker = null;
    return;
  }
  placeUserMarker(L, props.userLat, props.userLng);
}

function fitView(L: typeof import("leaflet")) {
  if (props.userLat != null && props.userLng != null) {
    map!.setView([props.userLat, props.userLng], 15);
    return;
  }
  if (props.centerLat != null && props.centerLng != null) {
    map!.setView([props.centerLat, props.centerLng], 17);
    return;
  }
  const valid = props.lots.filter((l) => l.lat != null && l.lng != null);
  if (!valid.length) {
    map!.setView([14.5995, 120.9842], 13);
    return;
  }
  if (valid.length === 1) {
    const pin = valid[0]!;
    map!.setView([pin.lat!, pin.lng!], 15);
    return;
  }
  const bounds = L.latLngBounds(
    valid.map((l) => [l.lat!, l.lng!] as [number, number]),
  );
  map!.fitBounds(bounds, { padding: [48, 48] });
}
</script>

<template>
  <div
    class="relative w-full rounded-xl overflow-hidden border border-border"
    style="height: calc(100dvh - 220px); min-height: 320px"
  >
    <div ref="mapEl" class="absolute inset-0" />

    <!-- Locate me button -->
    <button
      class="absolute bottom-4 right-4 z-1001 size-10 rounded-xl bg-background/90 backdrop-blur-sm border border-border shadow-md flex items-center justify-center text-foreground hover:bg-background transition-colors disabled:opacity-50"
      :disabled="locating"
      aria-label="Show my location"
      @click="locateUser"
    >
      <Loader2 v-if="locating" class="size-4 animate-spin text-muted-foreground" />
      <LocateFixed v-else class="size-4" />
    </button>
  </div>
</template>

<style>
/* Fix Leaflet popup close button color in light/dark mode */
.leaflet-popup-close-button {
  color: #71717a !important;
}
.leaflet-popup-content-wrapper {
  border-radius: 12px !important;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15) !important;
}
</style>
