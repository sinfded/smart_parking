<script setup lang="ts">
import {
  ChevronLeft,
  LayoutGrid,
  Map as MapIcon,
  Navigation,
} from "lucide-vue-next";
import type {
  LotMapConfig,
  ParkingSlotEl,
  SlotStatus,
} from "@smart-parking/types";
import { defaultConfig } from "@smart-parking/types";

// ── Types ─────────────────────────────────────────────────────────────────────

type DbSlotState = "free" | "occupied" | "unknown" | "reserved" | "disabled";

interface LotAvailability {
  lot_id: string;
  name: string;
  address: string | null;
  total_slots: number;
  free_slots: number;
  occupied_slots: number;
}

interface Zone {
  id: string;
  name: string;
  sort_order: number;
}

interface DbSlot {
  id: string;
  label: string;
  category: string;
  current_state: DbSlotState;
  zone_id: string | null;
  map_x: number | null;
  map_y: number | null;
}

// ── Setup ─────────────────────────────────────────────────────────────────────

const route = useRoute();
const id = route.params.id as string;
const client = useSupabaseClient<any>();

const lot = ref<LotAvailability | null>(null);
const zones = ref<Zone[]>([]);
const dbSlots = ref<DbSlot[]>([]);
const mapConfig = ref<LotMapConfig>(defaultConfig());
const loading = ref(true);
const view = ref<"grid" | "map">("map");

// ── Data loading ──────────────────────────────────────────────────────────────

async function loadData() {
  const [availRes, mapRes, zoneRes, slotRes] = await Promise.all([
    client.from("lot_availability").select("*").eq("lot_id", id).single(),
    client.from("lots").select("map_config").eq("id", id).single(),
    client
      .from("zones")
      .select("id, name, sort_order")
      .eq("lot_id", id)
      .order("sort_order"),
    client
      .from("slots")
      .select("id, label, category, current_state, zone_id, map_x, map_y")
      .eq("lot_id", id)
      .is("deleted_at", null)
      .order("label"),
  ]);

  lot.value = (availRes.data as LotAvailability) ?? null;
  zones.value = (zoneRes.data ?? []) as Zone[];
  dbSlots.value = (slotRes.data ?? []) as DbSlot[];

  const cfg = (mapRes.data as any)?.map_config;
  if (cfg?.version) mapConfig.value = cfg as LotMapConfig;

  loading.value = false;
}

// ── Live slot state map (slotId → status) ─────────────────────────────────────

const liveSlots = ref<Map<string, SlotStatus>>(new Map());

function buildLiveMap() {
  // Build a lookup from db slot id → current_state using layout slotId links
  const slotStateById = new Map(
    dbSlots.value.map((s) => [s.id, s.current_state as SlotStatus]),
  );
  const map = new Map<string, SlotStatus>();
  for (const el of mapConfig.value.elements) {
    if (el.type === "parking_slot" && el.slotId) {
      map.set(el.slotId, slotStateById.get(el.slotId) ?? "unknown");
    }
  }
  liveSlots.value = map;
}

watch([dbSlots, mapConfig], buildLiveMap, { immediate: true, deep: true });

// ── Realtime ──────────────────────────────────────────────────────────────────

onMounted(async () => {
  await loadData();
  buildLiveMap();

  const channel = client
    .channel(`lot-slots-${id}`)
    .on(
      "postgres_changes" as any,
      {
        event: "UPDATE",
        schema: "public",
        table: "slots",
        filter: `lot_id=eq.${id}`,
      },
      (payload: any) => {
        const idx = dbSlots.value.findIndex((s) => s.id === payload.new.id);
        if (idx >= 0) {
          dbSlots.value[idx] = { ...dbSlots.value[idx], ...payload.new };
        }
        buildLiveMap();
      },
    )
    .subscribe();

  onUnmounted(() => {
    client.removeChannel(channel);
  });
});

useHead({ title: computed(() => lot.value?.name ?? "Parking lot") });

// ── Stats ──────────────────────────────────────────────────────────────────────

const freeCount = computed(
  () => dbSlots.value.filter((s) => s.current_state === "free").length,
);
const totalCount = computed(() => dbSlots.value.length);
const occupancyPercent = computed(() =>
  totalCount.value > 0
    ? ((totalCount.value - freeCount.value) / totalCount.value) * 100
    : 0,
);

// ── Grid helpers ──────────────────────────────────────────────────────────────

function slotsForZone(zoneId: string) {
  return dbSlots.value.filter((s) => s.zone_id === zoneId);
}

const unzonedSlots = computed(() =>
  dbSlots.value.filter((s) => s.zone_id === null),
);

// ── Map: nearest available slot ────────────────────────────────────────────────

const selectedSlot = ref<ParkingSlotEl | null>(null);
const selectedStatus = computed<SlotStatus | null>(() =>
  selectedSlot.value?.slotId
    ? (liveSlots.value.get(selectedSlot.value.slotId) ?? null)
    : null,
);

/** ID of the free slot closest to the first entrance in the layout */
const nearestFreeId = computed<string | null>(() => {
  const entrance = mapConfig.value.elements.find((e) => e.type === "entrance");
  if (!entrance) return null;
  const ex = (entrance as any).x as number;
  const ey = (entrance as any).y as number;

  let nearest: { id: string; dist: number } | null = null;
  for (const el of mapConfig.value.elements) {
    if (el.type !== "parking_slot" || !el.slotId) continue;
    if (liveSlots.value.get(el.slotId) !== "free") continue;
    const d = Math.hypot(el.x - ex, el.y - ey);
    if (!nearest || d < nearest.dist) nearest = { id: el.id, dist: d };
  }
  return nearest?.id ?? null;
});

/** Approximate distance in metres from entrance to the selected slot */
const distanceM = computed<number | null>(() => {
  if (!selectedSlot.value) return null;
  const entrance = mapConfig.value.elements.find((e) => e.type === "entrance");
  if (!entrance) return null;
  const ex = Number((entrance as any).x);
  const ey = Number((entrance as any).y);
  if (!isFinite(ex) || !isFinite(ey)) return null;
  // 1 canvas unit = 1 cm → divide by 100 for metres
  const metres = Math.hypot(selectedSlot.value.x - ex, selectedSlot.value.y - ey) / 100;
  return isFinite(metres) ? Math.round(metres) : null;
});

function onSlotTap(slot: ParkingSlotEl) {
  selectedSlot.value = selectedSlot.value?.id === slot.id ? null : slot;
}

function highlightNearest() {
  if (!nearestFreeId.value) return;
  const el = mapConfig.value.elements.find((e) => e.id === nearestFreeId.value);
  if (el) selectedSlot.value = el as ParkingSlotEl;
  view.value = "map";
}
</script>

<template>
  <NuxtLayout name="default">
    <template #header-left>
      <NuxtLink
        to="/"
        class="size-8 flex items-center justify-center rounded-lg hover:bg-accent transition-colors -ml-1 shrink-0"
        aria-label="Back"
      >
        <ChevronLeft class="size-5" />
      </NuxtLink>
    </template>
    <template #title>
      <span class="truncate">{{ lot?.name ?? "Parking lot" }}</span>
    </template>
    <template #header-right>
      <div
        class="flex items-center gap-1.5 text-xs text-emerald-500 font-medium pr-1"
      >
        <span class="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
        Live
      </div>
    </template>

    <!-- Skeleton -->
    <div v-if="loading">
      <Skeleton class="h-20 rounded-xl mb-4" />
      <div class="grid grid-cols-5 gap-2">
        <Skeleton v-for="n in 20" :key="n" class="aspect-square rounded-md" />
      </div>
    </div>

    <template v-else-if="lot">
      <!-- Stats hero -->
      <div class="rounded-xl border border-border bg-card px-4 pt-3.5 pb-3 mb-3">
        <div class="grid grid-cols-3 divide-x divide-border text-center mb-3">
          <div class="pr-4">
            <p class="text-2xl font-bold tabular-nums text-emerald-500">{{ freeCount }}</p>
            <p class="text-xs text-muted-foreground mt-0.5">Free</p>
          </div>
          <div class="px-4">
            <p class="text-2xl font-bold tabular-nums text-red-500">{{ totalCount - freeCount }}</p>
            <p class="text-xs text-muted-foreground mt-0.5">Occupied</p>
          </div>
          <div class="pl-4">
            <p class="text-2xl font-bold tabular-nums">{{ totalCount }}</p>
            <p class="text-xs text-muted-foreground mt-0.5">Total</p>
          </div>
        </div>
        <Progress :model-value="occupancyPercent" class="h-2" />
        <p v-if="lot.address" class="text-xs text-muted-foreground mt-2 line-clamp-1">
          {{ lot.address }}
        </p>
      </div>

      <!-- View toggle -->
      <div class="flex gap-1.5 p-1 rounded-xl bg-muted mb-3">
        <button
          class="flex-1 flex items-center justify-center gap-1.5 py-1.5 text-sm font-medium rounded-lg transition-all"
          :class="
            view === 'map'
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground'
          "
          @click="view = 'map'"
        >
          <MapIcon class="size-4" /> Map
        </button>
        <button
          class="flex-1 flex items-center justify-center gap-1.5 py-1.5 text-sm font-medium rounded-lg transition-all"
          :class="
            view === 'grid'
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground'
          "
          @click="view = 'grid'"
        >
          <LayoutGrid class="size-4" /> Grid
        </button>
      </div>

      <!-- ── Map view ─────────────────────────────────────────────────────── -->
      <template v-if="view === 'map'">
        <!-- Map fills remaining space; Find nearest floats over it -->
        <div class="relative">
          <LotMap
            :config="mapConfig"
            :live-slots="liveSlots"
            :highlight-id="nearestFreeId"
            class="h-[72vh]"
            @tap-slot="onSlotTap"
          />

          <!-- Floating "Find nearest" pill -->
          <div
            class="absolute top-3 left-1/2 -translate-x-1/2 z-10 pointer-events-none flex justify-center"
          >
            <button
              v-if="nearestFreeId"
              class="pointer-events-auto flex items-center gap-2 px-4 py-2 rounded-full bg-emerald-500 text-white text-xs font-semibold shadow-lg shadow-emerald-900/40 hover:bg-emerald-400 active:scale-95 transition-all"
              @click="highlightNearest"
            >
              <Navigation class="size-3.5" />
              Find nearest free slot
            </button>
            <span
              v-else
              class="px-3 py-1.5 rounded-full bg-zinc-900/80 backdrop-blur text-zinc-400 text-xs border border-zinc-700"
            >
              No free slots
            </span>
          </div>
        </div>
      </template>

      <!-- ── Grid view ────────────────────────────────────────────────────── -->
      <template v-else>
        <!-- Legend -->
        <div
          class="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted-foreground mb-4"
        >
          <span class="flex items-center gap-1.5"
            ><span
              class="size-2.5 rounded bg-emerald-500 inline-block"
            />Free</span
          >
          <span class="flex items-center gap-1.5"
            ><span
              class="size-2.5 rounded bg-red-500 inline-block"
            />Occupied</span
          >
          <span class="flex items-center gap-1.5"
            ><span
              class="size-2.5 rounded bg-amber-400 inline-block"
            />Unknown</span
          >
          <span class="flex items-center gap-1.5"
            ><span
              class="size-2.5 rounded bg-zinc-200 border inline-block"
            />Disabled</span
          >
        </div>

        <!-- Zoned slots -->
        <template v-if="zones.length">
          <div v-for="zone in zones" :key="zone.id" class="mb-6">
            <div class="flex items-center gap-2 mb-2">
              <span
                class="text-xs font-semibold text-muted-foreground uppercase tracking-wider"
                >{{ zone.name }}</span
              >
              <Separator class="flex-1" />
            </div>
            <div class="grid grid-cols-5 gap-2">
              <SlotCell
                v-for="slot in slotsForZone(zone.id)"
                :key="slot.id"
                :label="slot.label"
                :state="slot.current_state"
              />
            </div>
          </div>
        </template>

        <!-- Unzoned -->
        <div v-if="unzonedSlots.length" class="grid grid-cols-5 gap-2">
          <SlotCell
            v-for="slot in unzonedSlots"
            :key="slot.id"
            :label="slot.label"
            :state="slot.current_state"
          />
        </div>
      </template>
    </template>

    <!-- Not found -->
    <div v-else class="text-center py-20 text-muted-foreground text-sm">
      Parking lot not found.
    </div>

    <!-- Slot detail bottom sheet -->
    <SlotDetailSheet
      :slot="selectedSlot"
      :status="selectedStatus"
      :distance-m="distanceM"
      :lot-address="lot?.address ?? null"
      @close="selectedSlot = null"
    />
  </NuxtLayout>
</template>
