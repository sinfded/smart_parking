<script setup lang="ts">
import {
  Search,
  LocateFixed,
  Loader2,
  X,
  Car,
  List,
  Map as MapIcon,
} from "lucide-vue-next";

interface LotSummary {
  lot_id: string;
  name: string;
  address: string | null;
  total_slots: number;
  free_slots: number;
  occupied_slots: number;
  other_slots: number;
  distance_meters?: number;
  lat?: number | null;
  lng?: number | null;
}

const client = useSupabaseClient();
const { geocode } = useNominatim();
const route = useRoute();

const searchQuery = ref("");
const mode = ref<"all" | "nearby">("all");
const view = ref<"list" | "map">("list");
const lots = ref<LotSummary[]>([]);
const loading = ref(true);
const gpsLoading = ref(false);
const errorMsg = ref<string | null>(null);
const userLat = ref<number | null>(null);
const userLng = ref<number | null>(null);
const centerLat = ref<number | null>(null);
const centerLng = ref<number | null>(null);

async function fetchAll() {
  loading.value = true;
  errorMsg.value = null;
  const { data, error } = await client
    .from("lot_availability" as any)
    .select("*");
  loading.value = false;
  if (error) {
    errorMsg.value = error.message;
    return;
  }
  lots.value = (data ?? []) as unknown as LotSummary[];
}

async function fetchNearby(lat: number, lng: number) {
  loading.value = true;
  errorMsg.value = null;
  const { data, error } = await client.rpc(
    "lots_nearby" as any,
    {
      p_lat: lat,
      p_lng: lng,
      p_radius_meters: 5000,
    } as any,
  );
  loading.value = false;
  if (error) {
    errorMsg.value = error.message;
    return;
  }
  lots.value = (data ?? []) as unknown as LotSummary[];
}

async function onSearch() {
  if (!searchQuery.value.trim()) {
    mode.value = "all";
    await fetchAll();
    return;
  }
  loading.value = true;
  errorMsg.value = null;
  const coords = await geocode(searchQuery.value.trim()).catch(() => null);
  if (!coords) {
    loading.value = false;
    errorMsg.value = "Location not found. Try a different search.";
    return;
  }
  userLat.value = coords.lat;
  userLng.value = coords.lng;
  mode.value = "nearby";
  await fetchNearby(coords.lat, coords.lng);
}

function onGPS() {
  if (!navigator.geolocation) {
    errorMsg.value = "Geolocation is not supported by your browser.";
    return;
  }
  gpsLoading.value = true;
  errorMsg.value = null;
  navigator.geolocation.getCurrentPosition(
    async (pos) => {
      gpsLoading.value = false;
      userLat.value = pos.coords.latitude;
      userLng.value = pos.coords.longitude;
      mode.value = "nearby";
      searchQuery.value = "";
      await fetchNearby(pos.coords.latitude, pos.coords.longitude);
    },
    () => {
      gpsLoading.value = false;
      errorMsg.value =
        "Could not get your location. Allow location access and try again.";
    },
    { enableHighAccuracy: true, timeout: 10_000 },
  );
}

function onClear() {
  searchQuery.value = "";
  mode.value = "all";
  userLat.value = null;
  userLng.value = null;
  fetchAll();
}

const lotsWithLocation = computed(() =>
  lots.value.filter(
    (l): l is typeof l & { lat: number; lng: number } =>
      l.lat != null && l.lng != null,
  ),
);

const resultLabel = computed(() => {
  if (loading.value) return null;
  const n = lots.value.length;
  if (mode.value === "nearby")
    return `${n} lot${n !== 1 ? "s" : ""} within 5 km`;
  return `${n} parking lot${n !== 1 ? "s" : ""}`;
});

await fetchAll();

// Open map centered on a specific lot when navigated from the lot detail page
if (route.query.view === "map") {
  view.value = "map";
  const qLat = parseFloat(route.query.lat as string);
  const qLng = parseFloat(route.query.lng as string);
  if (!isNaN(qLat) && !isNaN(qLng)) {
    centerLat.value = qLat;
    centerLng.value = qLng;
  }
}
</script>

<template>
  <NuxtLayout name="default">
    <template #title>Smart Parking</template>

    <!-- Search bar -->
    <div class="flex gap-2 mb-3">
      <div class="relative flex-1">
        <Search
          class="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground pointer-events-none"
        />
        <input
          v-model="searchQuery"
          type="search"
          placeholder="Search city or area..."
          class="w-full h-11 pl-9 pr-3 rounded-xl border border-input bg-background text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          @keyup.enter="onSearch"
        />
      </div>
      <button
        :disabled="gpsLoading"
        class="size-11 shrink-0 flex items-center justify-center rounded-xl border border-input bg-background hover:bg-accent transition-colors disabled:opacity-50"
        aria-label="Use my location"
        @click="onGPS"
      >
        <Loader2
          v-if="gpsLoading"
          class="size-4 animate-spin text-muted-foreground"
        />
        <LocateFixed v-else class="size-4 text-muted-foreground" />
      </button>
    </div>

    <!-- Mode tabs + view toggle -->
    <div class="flex gap-2 mb-4">
      <div class="flex gap-2 flex-1">
        <button
          class="flex-1 h-9 rounded-lg text-sm font-medium transition-colors"
          :class="
            mode === 'all'
              ? 'bg-primary text-primary-foreground'
              : 'bg-muted text-muted-foreground hover:text-foreground'
          "
          @click="onClear"
        >
          All lots
        </button>
        <button
          class="flex-1 h-9 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-1.5"
          :class="
            mode === 'nearby'
              ? 'bg-primary text-primary-foreground'
              : 'bg-muted text-muted-foreground hover:text-foreground'
          "
          :disabled="gpsLoading"
          @click="mode !== 'nearby' && onGPS()"
        >
          <Loader2 v-if="gpsLoading" class="size-3.5 animate-spin" />
          <LocateFixed v-else class="size-3.5" />
          Nearby
        </button>
      </div>

      <!-- List / Map toggle -->
      <div
        class="flex rounded-lg border border-border overflow-hidden shrink-0"
      >
        <button
          class="size-9 flex items-center justify-center transition-colors"
          :class="
            view === 'list'
              ? 'bg-primary text-primary-foreground'
              : 'bg-background text-muted-foreground hover:bg-muted'
          "
          aria-label="List view"
          @click="view = 'list'"
        >
          <List class="size-4" />
        </button>
        <button
          class="size-9 flex items-center justify-center border-l border-border transition-colors"
          :class="
            view === 'map'
              ? 'bg-primary text-primary-foreground'
              : 'bg-background text-muted-foreground hover:bg-muted'
          "
          aria-label="Map view"
          @click="view = 'map'"
        >
          <MapIcon class="size-4" />
        </button>
      </div>
    </div>

    <!-- Error -->
    <div
      v-if="errorMsg"
      class="rounded-xl bg-destructive/10 border border-destructive/20 px-3.5 py-2.5 mb-3"
    >
      <p class="text-sm text-destructive">{{ errorMsg }}</p>
    </div>

    <!-- ── Map view ──────────────────────────────────────────────────────── -->
    <template v-if="view === 'map'">
      <div
        v-if="loading"
        class="rounded-xl border border-border bg-muted animate-pulse"
        style="height: calc(100dvh - 220px); min-height: 320px"
      />
      <div
        v-else-if="!lotsWithLocation.length"
        class="text-center py-16 text-muted-foreground"
      >
        <MapIcon class="size-10 mx-auto mb-3 opacity-25" />
        <p class="text-sm font-medium">No lots with location data</p>
        <p class="text-xs mt-1 opacity-70">
          Lot coordinates haven't been set yet.
        </p>
      </div>
      <ClientOnly v-else>
        <LotMapView
          :lots="lotsWithLocation"
          :user-lat="userLat"
          :user-lng="userLng"
          :center-lat="centerLat"
          :center-lng="centerLng"
        />
        <template #fallback>
          <div
            class="rounded-xl border border-border bg-muted animate-pulse"
            style="height: calc(100dvh - 220px); min-height: 320px"
          />
        </template>
      </ClientOnly>
    </template>

    <!-- ── List view ─────────────────────────────────────────────────────── -->
    <template v-else>
      <!-- Result count + clear -->
      <div class="flex items-center justify-between mb-3">
        <p v-if="resultLabel" class="text-xs text-muted-foreground">
          {{ resultLabel }}
        </p>
        <button
          v-if="mode === 'nearby'"
          class="text-xs text-muted-foreground flex items-center gap-1 hover:text-foreground ml-auto transition-colors"
          @click="onClear"
        >
          <X class="size-3" /> Clear
        </button>
      </div>

      <!-- Skeletons -->
      <div v-if="loading" class="flex flex-col gap-3">
        <Skeleton v-for="n in 4" :key="n" class="h-24 w-full rounded-xl" />
      </div>

      <!-- Lot cards -->
      <div v-else-if="lots.length" class="flex flex-col gap-3">
        <LotCard
          v-for="lot in lots"
          :key="lot.lot_id"
          :lot-id="lot.lot_id"
          :name="lot.name"
          :address="lot.address"
          :total-slots="Number(lot.total_slots)"
          :free-slots="Number(lot.free_slots)"
          :distance-meters="lot.distance_meters"
        />
      </div>

      <!-- Empty state -->
      <div v-else class="text-center py-16 text-muted-foreground">
        <Car class="size-10 mx-auto mb-3 opacity-25" />
        <p class="text-sm font-medium">No parking lots found</p>
        <p v-if="mode === 'nearby'" class="text-xs mt-1 opacity-70">
          Try expanding your search area or switch to all lots.
        </p>
        <p v-else class="text-xs mt-1 opacity-70">
          No lots have been added yet.
        </p>
      </div>
    </template>
  </NuxtLayout>
</template>
