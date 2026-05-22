<script setup lang="ts">
import { ArrowLeft } from "lucide-vue-next";

const route = useRoute();
const client = useSupabaseClient();
const lotId = route.params.id as string;

const { data: lot, refresh: refreshLot } = await useLazyAsyncData(
  `lot-full-${lotId}`,
  async () => {
    const { data } = await client
      .from("lots")
      .select("id, name, address, timezone, is_public, location")
      .eq("id", lotId)
      .is("deleted_at", null)
      .single();
    return data;
  },
);

const { data: settings, refresh: refreshSettings } = await useLazyAsyncData(
  `lot-settings-${lotId}`,
  async () => {
    const { data } = await client
      .from("lot_settings")
      .select("*")
      .eq("lot_id", lotId)
      .maybeSingle();
    return data;
  },
);

useHead(() => ({
  title: lot.value ? `Settings — ${lot.value.name}` : "Settings",
}));

// ── Lot info form ─────────────────────────────────────────────────────────────
const lotForm = reactive({
  name: "",
  address: "",
  timezone: "Asia/Manila",
  is_public: true,
  lat: "" as string,
  lng: "" as string,
});

// PostgREST returns PostGIS geography as hex-encoded EWKB, not GeoJSON.
// Format: [1B endian][4B type (incl. SRID flag 0x20000000)][4B SRID?][8B lng][8B lat]
function decodeEWKBPoint(hex: string): { lat: number; lng: number } | null {
  try {
    if (hex.length < 42) return null;
    const bytes = new Uint8Array(hex.length / 2);
    for (let i = 0; i < bytes.length; i++)
      bytes[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
    const view = new DataView(bytes.buffer);
    const le = bytes[0] === 1;
    const wkbType = view.getUint32(1, le);
    const hasSRID = !!(wkbType & 0x20000000);
    const offset = 5 + (hasSRID ? 4 : 0);
    if (bytes.length < offset + 16) return null;
    return { lng: view.getFloat64(offset, le), lat: view.getFloat64(offset + 8, le) };
  } catch {
    return null;
  }
}

function parseLotLocation(location: unknown): { lat: string; lng: string } | null {
  if (!location) return null;
  if (typeof location === "string") {
    const coords = decodeEWKBPoint(location);
    if (coords) return { lat: String(coords.lat), lng: String(coords.lng) };
  }
  return null;
}

watch(
  lot,
  (v) => {
    if (!v) return;
    lotForm.name = v.name;
    lotForm.address = v.address ?? "";
    lotForm.timezone = v.timezone;
    lotForm.is_public = v.is_public;
    const coords = parseLotLocation(v.location);
    lotForm.lat = coords?.lat ?? "";
    lotForm.lng = coords?.lng ?? "";
  },
  { immediate: true },
);

const locating = ref(false);
function useMyLocation() {
  if (!navigator.geolocation) return;
  locating.value = true;
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      lotForm.lat = pos.coords.latitude.toFixed(7);
      lotForm.lng = pos.coords.longitude.toFixed(7);
      locating.value = false;
    },
    () => { locating.value = false; },
  );
}

const savingLot = ref(false);
async function saveLot() {
  savingLot.value = true;
  const lat = parseFloat(lotForm.lat);
  const lng = parseFloat(lotForm.lng);
  // PostGIS WKT: longitude first. null clears any existing location.
  const location = !isNaN(lat) && !isNaN(lng) ? `POINT(${lng} ${lat})` : null;
  await client
    .from("lots")
    .update({
      name: lotForm.name.trim(),
      address: lotForm.address.trim() || null,
      timezone: lotForm.timezone.trim(),
      is_public: lotForm.is_public,
      location,
    })
    .eq("id", lotId);
  await refreshLot();
  // Force-sync lat/lng in case the watch doesn't re-fire after a hydrated refresh
  const coords = parseLotLocation(lot.value?.location);
  lotForm.lat = coords?.lat ?? lotForm.lat;
  lotForm.lng = coords?.lng ?? lotForm.lng;
  savingLot.value = false;
}

// ── Gateway settings form ─────────────────────────────────────────────────────
const gwForm = reactive({
  confidence: 0.50,
  debounce_frames: 4,
  debounce_frames_free: 6,
  window_size: 8,
  overlap_threshold: 0.40,
  clahe_clip_limit: 2.0,
  min_duration: 5,
  api_host: "0.0.0.0",
  api_port: 8000,
});

watch(
  settings,
  (v) => {
    if (!v) return;
    gwForm.confidence = v.confidence;
    gwForm.debounce_frames = v.debounce_frames;
    gwForm.debounce_frames_free = v.debounce_frames_free;
    gwForm.window_size = v.window_size;
    gwForm.overlap_threshold = v.overlap_threshold;
    gwForm.clahe_clip_limit = v.clahe_clip_limit;
    gwForm.min_duration = v.min_duration;
    gwForm.api_host = v.api_host;
    gwForm.api_port = v.api_port;
  },
  { immediate: true },
);

const savingGw = ref(false);
async function saveGateway() {
  savingGw.value = true;
  await client.from("lot_settings").upsert(
    {
      lot_id: lotId,
      confidence: gwForm.confidence,
      debounce_frames: gwForm.debounce_frames,
      debounce_frames_free: gwForm.debounce_frames_free,
      window_size: gwForm.window_size,
      overlap_threshold: gwForm.overlap_threshold,
      clahe_clip_limit: gwForm.clahe_clip_limit,
      min_duration: gwForm.min_duration,
      api_host: gwForm.api_host.trim(),
      api_port: gwForm.api_port,
      updated_at: new Date().toISOString(),
    },
    { onConflict: "lot_id" },
  );
  await refreshSettings();
  savingGw.value = false;
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center gap-2">
      <Button variant="ghost" size="icon" class="size-7" as-child>
        <NuxtLink to="/lots">
          <ArrowLeft class="size-4" />
        </NuxtLink>
      </Button>
      <Skeleton v-if="!lot" class="h-6 w-36" />
      <h2 v-else class="text-base font-semibold">{{ lot.name }}</h2>
    </div>

    <LotNav />

    <div class="grid gap-6 lg:grid-cols-2">
      <!-- Lot information -->
      <Card>
        <CardHeader>
          <CardTitle class="text-sm">Lot information</CardTitle>
          <CardDescription
            >Name, address, and visibility settings.</CardDescription
          >
        </CardHeader>
        <CardContent class="space-y-4">
          <div class="space-y-2">
            <Label for="lot-name">Name</Label>
            <Input id="lot-name" v-model="lotForm.name" />
          </div>
          <div class="space-y-2">
            <Label for="lot-address">Address</Label>
            <Input
              id="lot-address"
              v-model="lotForm.address"
              placeholder="123 Main St"
            />
          </div>
          <div class="space-y-2">
            <Label>GPS location</Label>
            <div class="flex gap-2">
              <Input
                v-model="lotForm.lat"
                placeholder="Latitude (e.g. 14.5995)"
                type="number"
                step="any"
              />
              <Input
                v-model="lotForm.lng"
                placeholder="Longitude (e.g. 120.9842)"
                type="number"
                step="any"
              />
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              :disabled="locating"
              @click="useMyLocation"
            >
              <Spinner v-if="locating" class="mr-2 size-3.5" />
              Use my location
            </Button>
          </div>

          <div class="space-y-2">
            <Label for="lot-tz">Timezone</Label>
            <Input
              id="lot-tz"
              v-model="lotForm.timezone"
              placeholder="Asia/Manila"
            />
          </div>
          <div class="space-y-2">
            <Label>Visibility</Label>
            <Select
              :model-value="lotForm.is_public ? 'true' : 'false'"
              @update:model-value="(v) => (lotForm.is_public = v === 'true')"
            >
              <SelectTrigger class="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="true"
                  >Public — listed in user app</SelectItem
                >
                <SelectItem value="false"
                  >Private — hidden from users</SelectItem
                >
              </SelectContent>
            </Select>
          </div>
        </CardContent>
        <CardFooter>
          <Button :disabled="savingLot" @click="saveLot">
            <Spinner v-if="savingLot" class="mr-2 size-4" />
            Save
          </Button>
        </CardFooter>
      </Card>

      <!-- Gateway / vision settings -->
      <Card>
        <CardHeader>
          <CardTitle class="text-sm">Gateway settings</CardTitle>
          <CardDescription
            >Vision detector thresholds and API config.</CardDescription
          >
        </CardHeader>
        <CardContent class="space-y-4">
          <div class="grid grid-cols-2 gap-4">
            <div class="space-y-2">
              <Label for="gw-confidence">Confidence</Label>
              <Input
                id="gw-confidence"
                v-model.number="gwForm.confidence"
                type="number"
                step="0.01"
                min="0"
                max="1"
              />
              <p class="text-muted-foreground text-xs">
                YOLO detection threshold (0–1)
              </p>
            </div>
            <div class="space-y-2">
              <Label for="gw-overlap">Overlap threshold</Label>
              <Input
                id="gw-overlap"
                v-model.number="gwForm.overlap_threshold"
                type="number"
                step="0.01"
                min="0"
                max="1"
              />
              <p class="text-muted-foreground text-xs">
                Min slot coverage to count as a hit (0–1)
              </p>
            </div>
            <div class="space-y-2">
              <Label for="gw-debounce">Debounce (occupied)</Label>
              <Input
                id="gw-debounce"
                v-model.number="gwForm.debounce_frames"
                type="number"
                min="1"
              />
              <p class="text-muted-foreground text-xs">
                Frames to confirm a car arrived
              </p>
            </div>
            <div class="space-y-2">
              <Label for="gw-debounce-free">Debounce (free)</Label>
              <Input
                id="gw-debounce-free"
                v-model.number="gwForm.debounce_frames_free"
                type="number"
                min="1"
              />
              <p class="text-muted-foreground text-xs">
                Frames to confirm a slot is empty
              </p>
            </div>
            <div class="space-y-2">
              <Label for="gw-window">Vote window</Label>
              <Input
                id="gw-window"
                v-model.number="gwForm.window_size"
                type="number"
                min="1"
              />
              <p class="text-muted-foreground text-xs">
                Rolling frame window for vote counts
              </p>
            </div>
            <div class="space-y-2">
              <Label for="gw-clahe">Shadow correction</Label>
              <Input
                id="gw-clahe"
                v-model.number="gwForm.clahe_clip_limit"
                type="number"
                step="0.1"
                min="0"
                max="10"
              />
              <p class="text-muted-foreground text-xs">
                CLAHE clip limit (0 = off, raise for heavy shadow)
              </p>
            </div>
            <div class="space-y-2">
              <Label for="gw-mindur">Min duration (s)</Label>
              <Input
                id="gw-mindur"
                v-model.number="gwForm.min_duration"
                type="number"
                min="0"
              />
              <p class="text-muted-foreground text-xs">
                Sessions shorter than this are dropped
              </p>
            </div>
            <div class="space-y-2">
              <Label for="gw-port">API port</Label>
              <Input
                id="gw-port"
                v-model.number="gwForm.api_port"
                type="number"
                min="1"
                max="65535"
              />
            </div>
          </div>
          <div class="space-y-2">
            <Label for="gw-host">API host</Label>
            <Input
              id="gw-host"
              v-model="gwForm.api_host"
              placeholder="0.0.0.0"
            />
          </div>
        </CardContent>
        <CardFooter>
          <Button :disabled="savingGw" @click="saveGateway">
            <Spinner v-if="savingGw" class="mr-2 size-4" />
            Save
          </Button>
        </CardFooter>
      </Card>
    </div>
  </div>
</template>
