<script setup lang="ts">
import { Check, Download, Pencil, X } from "lucide-vue-next";

type SlotState = "free" | "occupied" | "unknown" | "reserved" | "disabled";

type SlotProp = {
  id: string;
  label: string;
  current_state: string;
  category: string;
  zone_id: string | null;
  zones: { name: string; sort_order: number } | null;
};

type SlotEvent = {
  id: number;
  previous_state: string | null;
  new_state: string;
  source: string;
  occurred_at: string;
};

type ActiveSession = {
  id: string;
  plate_number: string | null;
  started_at: string;
};

const props = defineProps<{
  slot: SlotProp | null;
  lotId: string;
}>();

const emit = defineEmits<{
  close: [];
  slotUpdated: [];
}>();

const client = useSupabaseClient();

const localSlot = ref<SlotProp | null>(null);
const slotEvents = ref<SlotEvent[]>([]);
const activeSession = ref<ActiveSession | null>(null);
const loading = ref(false);
const actionLoading = ref(false);
const exportLoading = ref(false);
const editingPlate = ref(false);
const plateInput = ref("");

watch(
  () => props.slot,
  async (slot) => {
    if (!slot) return;
    localSlot.value = slot;
    editingPlate.value = false;
    await loadDetail(slot.id);
  },
  { immediate: true },
);

async function loadDetail(slotId: string) {
  loading.value = true;

  const [{ data: events }, { data: session }] = await Promise.all([
    client
      .from("slot_events")
      .select("id, previous_state, new_state, source, occurred_at")
      .eq("slot_id", slotId)
      .order("occurred_at", { ascending: false })
      .limit(10),
    client
      .from("parking_sessions")
      .select("id, plate_number, started_at")
      .eq("slot_id", slotId)
      .is("ended_at", null)
      .maybeSingle(),
  ]);

  slotEvents.value = (events ?? []) as SlotEvent[];
  activeSession.value = session as ActiveSession | null;
  loading.value = false;
}

async function toggleDisable() {
  if (!localSlot.value) return;
  actionLoading.value = true;
  const newState = (
    localSlot.value.current_state === "disabled" ? "unknown" : "disabled"
  ) as SlotState;
  await client.rpc("report_slot_state", {
    p_slot_id: localSlot.value.id,
    p_new_state: newState,
    p_source: "manual",
  });
  localSlot.value = { ...localSlot.value, current_state: newState };
  await loadDetail(localSlot.value.id);
  emit("slotUpdated");
  actionLoading.value = false;
}

async function closeSession() {
  if (!localSlot.value || !activeSession.value) return;
  actionLoading.value = true;
  await client.rpc("report_slot_state", {
    p_slot_id: localSlot.value.id,
    p_new_state: "free",
    p_source: "manual",
  });
  localSlot.value = { ...localSlot.value, current_state: "free" };
  await loadDetail(localSlot.value.id);
  emit("slotUpdated");
  actionLoading.value = false;
}

function startEditPlate() {
  plateInput.value = activeSession.value?.plate_number ?? "";
  editingPlate.value = true;
}

async function savePlate() {
  if (!activeSession.value) return;
  const plate = plateInput.value.trim().toUpperCase() || null;
  await client
    .from("parking_sessions")
    .update({ plate_number: plate })
    .eq("id", activeSession.value.id);
  activeSession.value = { ...activeSession.value, plate_number: plate };
  editingPlate.value = false;
}

const stateVariant: Record<
  string,
  "default" | "secondary" | "destructive" | "outline"
> = {
  free: "secondary",
  occupied: "destructive",
  disabled: "outline",
  unknown: "outline",
  reserved: "default",
};

function formatDate(d: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(d));
}

async function exportCsv() {
  if (!localSlot.value) return;
  exportLoading.value = true;

  const { data } = await client
    .from("slot_events")
    .select("id, previous_state, new_state, source, occurred_at")
    .eq("slot_id", localSlot.value.id)
    .order("occurred_at", { ascending: false });

  const rows = data ?? [];
  const header = ["id", "previous_state", "new_state", "source", "occurred_at"];
  const csv = [
    header.join(","),
    ...rows.map((r) =>
      [r.id, r.previous_state ?? "", r.new_state, r.source, r.occurred_at].join(","),
    ),
  ].join("\n");

  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `slot_events_${localSlot.value.label}.csv`;
  a.click();
  URL.revokeObjectURL(url);

  exportLoading.value = false;
}
</script>

<template>
  <Sheet
    :open="!!slot"
    @update:open="
      (v) => {
        if (!v) emit('close');
      }
    "
  >
    <SheetContent class="sm:max-w-sm overflow-y-auto p-4">
      <SheetHeader class="p-0">
        <SheetTitle class="font-mono text-lg">{{
          localSlot?.label
        }}</SheetTitle>
        <SheetDescription class="capitalize">{{
          localSlot?.category
        }}</SheetDescription>
      </SheetHeader>

      <div v-if="loading" class="space-y-3">
        <Skeleton v-for="i in 5" :key="i" class="h-8 w-full" />
      </div>

      <div v-else class="space-y-6">
        <!-- State -->
        <div class="flex items-center justify-between">
          <span class="text-muted-foreground text-sm">Current state</span>
          <Badge
            :variant="
              stateVariant[localSlot?.current_state ?? 'unknown'] ?? 'outline'
            "
            class="capitalize"
          >
            {{ localSlot?.current_state }}
          </Badge>
        </div>

        <!-- Active session -->
        <div v-if="activeSession" class="space-y-3 rounded-lg border p-3">
          <p class="text-sm font-medium">Active session</p>
          <div class="grid grid-cols-2 gap-3 text-sm">
            <div>
              <p class="text-muted-foreground text-xs">Started</p>
              <p class="mt-0.5">{{ formatDate(activeSession.started_at) }}</p>
            </div>
            <div>
              <p class="text-muted-foreground text-xs">Plate</p>
              <div v-if="editingPlate" class="mt-0.5 flex items-center gap-1">
                <Input
                  v-model="plateInput"
                  class="h-7 w-24 text-xs uppercase"
                  @keydown.enter="savePlate"
                  @keydown.escape="editingPlate = false"
                />
                <Button
                  variant="ghost"
                  size="icon"
                  class="size-7 shrink-0"
                  @click="savePlate"
                >
                  <Check class="size-3.5 text-emerald-600" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  class="size-7 shrink-0"
                  @click="editingPlate = false"
                >
                  <X class="size-3.5" />
                </Button>
              </div>
              <div v-else class="mt-0.5 flex items-center gap-1">
                <span class="font-mono text-sm">{{
                  activeSession.plate_number ?? "—"
                }}</span>
                <Button
                  variant="ghost"
                  size="icon"
                  class="size-6"
                  @click="startEditPlate"
                >
                  <Pencil class="text-muted-foreground size-3" />
                </Button>
              </div>
            </div>
          </div>
          <Button
            variant="destructive"
            size="sm"
            class="w-full"
            :disabled="actionLoading"
            @click="closeSession"
          >
            <Spinner v-if="actionLoading" class="mr-2 size-4" />
            Close session manually
          </Button>
        </div>

        <!-- Slot actions -->
        <div class="space-y-2">
          <p
            class="text-muted-foreground text-xs font-medium uppercase tracking-wide"
          >
            Actions
          </p>
          <Button
            variant="outline"
            size="sm"
            class="w-full"
            :disabled="actionLoading"
            @click="toggleDisable"
          >
            <Spinner v-if="actionLoading" class="mr-2 size-4" />
            {{
              localSlot?.current_state === "disabled"
                ? "Enable slot"
                : "Disable slot"
            }}
          </Button>
        </div>

        <!-- Event history -->
        <div class="space-y-2">
          <div class="flex items-center justify-between">
            <p
              class="text-muted-foreground text-xs font-medium uppercase tracking-wide"
            >
              Recent events
            </p>
            <Button
              variant="ghost"
              size="icon"
              class="size-6"
              :disabled="exportLoading"
              @click="exportCsv"
            >
              <Download class="text-muted-foreground size-3.5" />
            </Button>
          </div>
          <p v-if="!slotEvents.length" class="text-muted-foreground text-xs">
            No events recorded.
          </p>
          <div v-else class="space-y-2">
            <div
              v-for="ev in slotEvents"
              :key="ev.id"
              class="flex items-center justify-between text-xs"
            >
              <div class="flex min-w-0 items-center gap-1.5">
                <span class="text-muted-foreground shrink-0 capitalize">{{
                  ev.previous_state ?? "—"
                }}</span>
                <span class="text-muted-foreground shrink-0">→</span>
                <span class="shrink-0 font-medium capitalize">{{
                  ev.new_state
                }}</span>
                <Badge
                  variant="outline"
                  class="h-4 shrink-0 px-1 text-[10px]"
                  >{{ ev.source }}</Badge
                >
              </div>
              <span class="text-muted-foreground ml-2 shrink-0">{{
                formatDate(ev.occurred_at)
              }}</span>
            </div>
          </div>
        </div>
      </div>
    </SheetContent>
  </Sheet>
</template>
