<script setup lang="ts">
import { Search, LocateFixed, Loader2, X } from "lucide-vue-next";

interface LotSummary {
  lot_id: string;
  name: string;
  address: string | null;
  total_slots: number;
  free_slots: number;
  occupied_slots: number;
  other_slots: number;
  distance_meters?: number;
}

const client = useSupabaseClient();
const { geocode } = useNominatim();

const searchQuery = ref("");
const mode = ref<"all" | "nearby">("all");
const lots = ref<LotSummary[]>([]);
const loading = ref(true);
const gpsLoading = ref(false);
const errorMsg = ref<string | null>(null);

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
  const { data, error } = await client.rpc("lots_nearby" as any, {
    p_lat: lat,
    p_lng: lng,
    p_radius_meters: 5000,
  } as any);
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
  fetchAll();
}

await fetchAll();
</script>

<template>
  <NuxtLayout name="default">
    <template #title>Smart Parking</template>

    <!-- Search bar -->
    <div class="flex gap-2 mb-4">
      <div class="relative flex-1">
        <Search
          class="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground pointer-events-none"
        />
        <input
          v-model="searchQuery"
          type="search"
          placeholder="Search city or area..."
          class="w-full h-10 pl-9 pr-3 rounded-lg border border-input bg-background text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          @keyup.enter="onSearch"
        />
      </div>
      <button
        :disabled="gpsLoading"
        class="size-10 shrink-0 flex items-center justify-center rounded-lg border border-input bg-background hover:bg-accent transition-colors disabled:opacity-50"
        aria-label="Use my location"
        @click="onGPS"
      >
        <Loader2
          v-if="gpsLoading"
          class="size-4 animate-spin text-muted-foreground"
        />
        <LocateFixed v-else class="size-4 text-muted-foreground" />
      </button>
      <button
        v-if="mode === 'nearby'"
        class="size-10 shrink-0 flex items-center justify-center rounded-lg border border-input bg-background hover:bg-accent transition-colors"
        aria-label="Clear search"
        @click="onClear"
      >
        <X class="size-4 text-muted-foreground" />
      </button>
    </div>

    <!-- Context label -->
    <p class="text-xs text-muted-foreground mb-3">
      <template v-if="mode === 'nearby'">Parking lots within 5 km</template>
      <template v-else>All parking lots</template>
    </p>

    <!-- Error -->
    <p v-if="errorMsg" class="text-sm text-destructive mb-3">{{ errorMsg }}</p>

    <!-- Skeleton loading state -->
    <div v-if="loading" class="flex flex-col gap-3">
      <Skeleton v-for="n in 4" :key="n" class="h-25 w-full rounded-xl" />
    </div>

    <!-- Lot list -->
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
    <div v-else class="text-center py-20 text-muted-foreground">
      <LocateFixed class="size-8 mx-auto mb-3 opacity-30" />
      <p class="text-sm">No parking lots found.</p>
      <p v-if="mode === 'nearby'" class="text-xs mt-1">
        Try expanding your search area.
      </p>
    </div>
  </NuxtLayout>
</template>
