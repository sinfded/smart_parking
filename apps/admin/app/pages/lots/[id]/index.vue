<script setup lang="ts">
import { ArrowLeft, Wifi, WifiOff } from "lucide-vue-next";

const route = useRoute();
const client = useSupabaseClient();
const lotId = route.params.id as string;

const { data: lot } = await useLazyAsyncData(`lot-${lotId}`, async () => {
  const { data } = await client
    .from("lots")
    .select("id, name, address, timezone")
    .eq("id", lotId)
    .is("deleted_at", null)
    .single();
  return data;
});

useHead(() => ({
  title: lot.value
    ? `${lot.value.name} — Smart Parking`
    : "Lot — Smart Parking",
}));

// ── Gateway health ─────────────────────────────────────────────────────────────
const { data: gateway } = await useLazyAsyncData(`gateway-${lotId}`, async () => {
  const { data } = await client
    .from("gateways")
    .select("id, name, last_seen_at")
    .eq("lot_id", lotId)
    .maybeSingle();
  return data;
});

const gatewayOnline = computed(() => {
  if (!gateway.value?.last_seen_at) return false;
  return (
    Date.now() - new Date(gateway.value.last_seen_at).getTime() < 5 * 60 * 1000
  );
});

// ── Slots ──────────────────────────────────────────────────────────────────────
type SlotRow = {
  id: string;
  label: string;
  current_state: string;
  category: string;
  zone_id: string | null;
  zones: { name: string; sort_order: number } | null;
};

const slots = ref<SlotRow[]>([]);
const slotsLoading = ref(true);

async function loadSlots() {
  slotsLoading.value = true;
  const { data } = await client
    .from("slots")
    .select("id, label, current_state, category, zone_id, zones(name, sort_order)")
    .eq("lot_id", lotId)
    .is("deleted_at", null)
    .order("label");
  slots.value = (data as SlotRow[]) ?? [];
  slotsLoading.value = false;
}

await loadSlots();

const groupedByZone = computed(() => {
  const groups: Record<
    string,
    { name: string; sortOrder: number; slots: SlotRow[] }
  > = {};
  for (const slot of slots.value) {
    const key = slot.zone_id ?? "__none__";
    if (!groups[key]) {
      groups[key] = {
        name: slot.zones?.name ?? "General",
        sortOrder: slot.zones?.sort_order ?? 999,
        slots: [],
      };
    }
    groups[key].slots.push(slot);
  }
  return Object.values(groups).sort((a, b) => a.sortOrder - b.sortOrder);
});

const stats = computed(() => ({
  free: slots.value.filter((s) => s.current_state === "free").length,
  occupied: slots.value.filter((s) => s.current_state === "occupied").length,
  total: slots.value.length,
}));

const stateClass: Record<string, string> = {
  free: "bg-emerald-50 border-emerald-200 text-emerald-700 dark:bg-emerald-950 dark:border-emerald-800 dark:text-emerald-300",
  occupied:
    "bg-red-50 border-red-200 text-red-700 dark:bg-red-950 dark:border-red-800 dark:text-red-300",
  reserved:
    "bg-blue-50 border-blue-200 text-blue-700 dark:bg-blue-950 dark:border-blue-800 dark:text-blue-300",
  unknown: "bg-muted/60 border-border text-muted-foreground",
  disabled: "bg-muted/30 border-border text-muted-foreground opacity-40",
};

// ── Slot detail sheet ──────────────────────────────────────────────────────────
const selectedSlot = ref<SlotRow | null>(null);

async function onSlotUpdated() {
  const prevId = selectedSlot.value?.id;
  await loadSlots();
  if (prevId) {
    selectedSlot.value = slots.value.find((s) => s.id === prevId) ?? null;
  }
}

// ── Realtime ───────────────────────────────────────────────────────────────────
let realtimeChannel: ReturnType<typeof client.channel> | null = null;

const CHANNEL_NAME = `slots-lot-${lotId}`;

onMounted(() => {
  // Remove any stale channel with the same name left over from a previous mount
  client.getChannels()
    .filter(ch => ch.topic === `realtime:${CHANNEL_NAME}`)
    .forEach(ch => client.removeChannel(ch));

  realtimeChannel = client
    .channel(CHANNEL_NAME)
    .on(
      "postgres_changes",
      {
        event: "UPDATE",
        schema: "public",
        table: "slots",
        filter: `lot_id=eq.${lotId}`,
      },
      (payload) => {
        const idx = slots.value.findIndex((s) => s.id === payload.new.id);
        if (idx !== -1) {
          slots.value[idx] = {
            ...slots.value[idx],
            ...(payload.new as SlotRow),
          };
          if (selectedSlot.value?.id === payload.new.id) {
            selectedSlot.value = { ...selectedSlot.value, ...(payload.new as SlotRow) };
          }
        }
      },
    )
    .subscribe();
});

onUnmounted(() => {
  if (realtimeChannel) client.removeChannel(realtimeChannel);
});

// ── Helpers ────────────────────────────────────────────────────────────────────
function formatRelative(d: string) {
  const diff = Date.now() - new Date(d).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-start justify-between gap-4">
      <div class="space-y-1">
        <div class="flex items-center gap-2">
          <Button variant="ghost" size="icon" class="size-7" as-child>
            <NuxtLink to="/lots">
              <ArrowLeft class="size-4" />
            </NuxtLink>
          </Button>
          <Skeleton v-if="!lot" class="h-6 w-40" />
          <h2 v-else class="text-lg font-semibold">{{ lot.name }}</h2>
        </div>
        <p v-if="lot?.address" class="text-muted-foreground pl-9 text-sm">
          {{ lot.address }}
        </p>
      </div>
      <div
        class="flex items-center gap-1.5 text-xs"
        :class="gatewayOnline ? 'text-emerald-600' : 'text-muted-foreground'"
      >
        <component
          :is="gatewayOnline ? Wifi : WifiOff"
          class="size-3.5"
          :class="gatewayOnline ? 'animate-pulse' : ''"
        />
        <span>{{
          gatewayOnline ? "Live" : gateway ? "Gateway offline" : "No gateway"
        }}</span>
      </div>
    </div>

    <LotNav />

    <!-- Stats row -->
    <div class="grid grid-cols-3 gap-3">
      <Card class="p-0">
        <CardContent class="pt-4 pb-3 text-center">
          <p class="text-2xl font-semibold text-emerald-600">{{ stats.free }}</p>
          <p class="text-muted-foreground text-xs">Free</p>
        </CardContent>
      </Card>
      <Card class="p-0">
        <CardContent class="pt-4 pb-3 text-center">
          <p class="text-2xl font-semibold text-red-600">{{ stats.occupied }}</p>
          <p class="text-muted-foreground text-xs">Occupied</p>
        </CardContent>
      </Card>
      <Card class="p-0">
        <CardContent class="pt-4 pb-3 text-center">
          <p class="text-2xl font-semibold">{{ stats.total }}</p>
          <p class="text-muted-foreground text-xs">Total</p>
        </CardContent>
      </Card>
    </div>

    <!-- Gateway health -->
    <Card v-if="gateway" class="px-4 py-3">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <div
            class="size-2 rounded-full"
            :class="gatewayOnline ? 'bg-emerald-500' : 'bg-red-400'"
          />
          <span class="text-sm font-medium">{{ gateway.name }}</span>
        </div>
        <span class="text-muted-foreground text-xs">
          {{
            gateway.last_seen_at
              ? `Last seen ${formatRelative(gateway.last_seen_at)}`
              : "Never connected"
          }}
        </span>
      </div>
    </Card>

    <!-- Slot grid -->
    <div
      v-if="slotsLoading"
      class="grid grid-cols-4 gap-2 sm:grid-cols-6 lg:grid-cols-8"
    >
      <Skeleton v-for="i in 16" :key="i" class="h-14 rounded-lg" />
    </div>

    <div v-else-if="!slots.length" class="py-16 text-center">
      <p class="text-muted-foreground text-sm">
        No slots configured for this lot.
      </p>
    </div>

    <div v-else class="space-y-6">
      <div v-for="group in groupedByZone" :key="group.name">
        <p
          class="text-muted-foreground mb-2 text-xs font-medium uppercase tracking-wide"
        >
          {{ group.name }}
        </p>
        <div
          class="grid grid-cols-4 gap-2 sm:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10"
        >
          <button
            v-for="slot in group.slots"
            :key="slot.id"
            class="flex h-14 cursor-pointer flex-col items-center justify-center rounded-lg border text-xs font-medium transition-colors hover:ring-2 hover:ring-ring hover:ring-offset-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            :class="stateClass[slot.current_state] ?? stateClass.unknown"
            @click="selectedSlot = slot"
          >
            <span class="text-sm font-semibold leading-none">{{
              slot.label
            }}</span>
            <span class="mt-1 capitalize opacity-70">{{
              slot.current_state
            }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Legend -->
    <div class="flex flex-wrap items-center gap-4 pt-2">
      <p class="text-muted-foreground text-xs">Legend:</p>
      <div
        v-for="(cls, state) in stateClass"
        :key="state"
        class="flex items-center gap-1.5"
      >
        <div class="size-3 rounded border" :class="cls" />
        <span class="text-muted-foreground text-xs capitalize">{{ state }}</span>
      </div>
    </div>
  </div>

  <SlotDetailSheet
    :slot="selectedSlot"
    :lot-id="lotId"
    @close="selectedSlot = null"
    @slot-updated="onSlotUpdated"
  />
</template>
