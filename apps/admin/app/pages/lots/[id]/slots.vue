<script setup lang="ts">
import {
  ArrowLeft,
  Check,
  Download,
  Pencil,
  Plus,
  Trash2,
  X,
} from "lucide-vue-next";

const route = useRoute();
const client = useSupabaseClient();
const lotId = route.params.id as string;

type Zone = { id: string; name: string; sort_order: number };
type Slot = {
  id: string;
  zone_id: string | null;
  label: string;
  category: string;
  current_state: string;
};

const { data: lot } = await useLazyAsyncData(`lot-${lotId}`, async () => {
  const { data } = await client
    .from("lots")
    .select("id, name")
    .eq("id", lotId)
    .single();
  return data;
});

useHead(() => ({
  title: lot.value ? `Slots — ${lot.value.name}` : "Slots",
}));

const zones = ref<Zone[]>([]);
const slots = ref<Slot[]>([]);
const loading = ref(true);

async function load() {
  loading.value = true;
  const [{ data: z }, { data: s }] = await Promise.all([
    client
      .from("zones")
      .select("id, name, sort_order")
      .eq("lot_id", lotId)
      .order("sort_order"),
    client
      .from("slots")
      .select("id, zone_id, label, category, current_state")
      .eq("lot_id", lotId)
      .is("deleted_at", null)
      .order("label"),
  ]);
  zones.value = (z ?? []) as Zone[];
  slots.value = (s ?? []) as Slot[];
  loading.value = false;
}

await load();

function slotsForZone(zoneId: string | null) {
  if (zoneId === null) return slots.value.filter((s) => !s.zone_id);
  return slots.value.filter((s) => s.zone_id === zoneId);
}

// ── Zone management ───────────────────────────────────────────────────────────
const showAddZone = ref(false);
const editingZoneId = ref<string | null>(null);
const editingZoneName = ref("");

function startEditZone(zone: Zone) {
  editingZoneId.value = zone.id;
  editingZoneName.value = zone.name;
}

async function saveZoneName() {
  const id = editingZoneId.value;
  const name = editingZoneName.value.trim();
  if (!id || !name) {
    editingZoneId.value = null;
    return;
  }
  await client.from("zones").update({ name }).eq("id", id);
  editingZoneId.value = null;
  await load();
}

async function deleteZone(zoneId: string) {
  await client.from("zones").delete().eq("id", zoneId);
  await load();
}

// ── Slot management ───────────────────────────────────────────────────────────
const showSlotDialog = ref(false);
const editingSlot = ref<Slot | null>(null);
const slotDialogDefaultZoneId = ref<string | null>(null);

function openAddSlot(zoneId: string | null) {
  editingSlot.value = null;
  slotDialogDefaultZoneId.value = zoneId;
  showSlotDialog.value = true;
}

function openEditSlot(slot: Slot) {
  editingSlot.value = slot;
  slotDialogDefaultZoneId.value = null;
  showSlotDialog.value = true;
}

async function toggleDisable(slot: Slot) {
  const newState = slot.current_state === "disabled" ? "unknown" : "disabled";
  await client.rpc("report_slot_state", {
    p_slot_id: slot.id,
    p_new_state: newState as "disabled" | "unknown",
    p_source: "manual",
  });
  await load();
}

async function deleteSlot(slotId: string) {
  await client
    .from("slots")
    .update({ deleted_at: new Date().toISOString() })
    .eq("id", slotId);
  await load();
}

// ── CSV export ────────────────────────────────────────────────────────────────
const exportLoading = ref(false);

async function exportCsv() {
  if (!slots.value.length) return;
  exportLoading.value = true;

  const slotIds = slots.value.map((s) => s.id);
  const labelById = Object.fromEntries(slots.value.map((s) => [s.id, s.label]));
  const slotLabels = slots.value.map((s) => s.label).sort();

  const { data } = await client
    .from("slot_events")
    .select("slot_id, new_state, occurred_at")
    .in("slot_id", slotIds)
    .order("occurred_at", { ascending: true });

  const rows = data ?? [];

  // pivot: { occurred_at → { slot_label → new_state } }
  const pivot = new Map<string, Record<string, string>>();
  for (const r of rows) {
    if (!pivot.has(r.occurred_at)) pivot.set(r.occurred_at, {});
    const state = r.new_state === "occupied" ? "1" : r.new_state === "free" ? "0" : "";
    pivot.get(r.occurred_at)![labelById[r.slot_id] ?? r.slot_id] = state;
  }

  // forward-fill: carry each slot's last known value into rows where it has no event
  const lastKnown: Record<string, string> = {};
  for (const cells of pivot.values()) {
    for (const label of slotLabels) {
      if (cells[label] !== undefined && cells[label] !== "") {
        lastKnown[label] = cells[label];
      } else if (lastKnown[label] !== undefined) {
        cells[label] = lastKnown[label];
      }
    }
  }

  const header = ["occurred_at", ...slotLabels];
  const csvRows = [header.join(",")];
  for (const [ts, cells] of pivot) {
    csvRows.push([ts, ...slotLabels.map((l) => cells[l] ?? "")].join(","));
  }

  const url = URL.createObjectURL(new Blob([csvRows.join("\n")], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `slot_events_${lot.value?.name ?? lotId}.csv`;
  a.click();
  URL.revokeObjectURL(url);

  exportLoading.value = false;
}

// ── State badge ───────────────────────────────────────────────────────────────
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
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <Button variant="ghost" size="icon" class="size-7" as-child>
          <NuxtLink to="/lots">
            <ArrowLeft class="size-4" />
          </NuxtLink>
        </Button>
        <Skeleton v-if="!lot" class="h-6 w-36" />
        <h2 v-else class="text-base font-semibold">{{ lot.name }}</h2>
      </div>
      <div class="flex items-center gap-2">
        <Button
          size="sm"
          variant="outline"
          :disabled="exportLoading || !slots.length"
          @click="exportCsv"
        >
          <Download class="mr-2 size-4" />
          Export
        </Button>
        <Button size="sm" variant="outline" @click="showAddZone = true">
          <Plus class="mr-2 size-4" />
          Add zone
        </Button>
      </div>
    </div>

    <LotNav />

    <div v-if="loading" class="space-y-4">
      <Skeleton v-for="i in 3" :key="i" class="h-32 w-full" />
    </div>

    <template v-else>
      <!-- One card per zone -->
      <Card
        v-for="zone in zones"
        :key="zone.id"
        class="overflow-hidden p-0 gap-0"
      >
        <div class="flex items-center justify-between border-b px-4 py-2.5">
          <div class="flex items-center gap-2">
            <template v-if="editingZoneId === zone.id">
              <Input
                v-model="editingZoneName"
                class="h-7 w-40 text-sm"
                @keydown.enter="saveZoneName"
                @keydown.escape="editingZoneId = null"
              />
              <Button
                variant="ghost"
                size="icon"
                class="size-7"
                @click="saveZoneName"
              >
                <Check class="size-3.5 text-emerald-600" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                class="size-7"
                @click="editingZoneId = null"
              >
                <X class="size-3.5" />
              </Button>
            </template>
            <template v-else>
              <span class="text-sm font-medium">{{ zone.name }}</span>
              <Button
                variant="ghost"
                size="icon"
                class="size-7"
                @click="startEditZone(zone)"
              >
                <Pencil class="text-muted-foreground size-3.5" />
              </Button>
            </template>
          </div>
          <div class="flex items-center gap-1">
            <span class="text-muted-foreground text-xs">
              {{ slotsForZone(zone.id).length }} slots
            </span>
            <Button
              variant="ghost"
              size="icon"
              class="text-muted-foreground hover:text-destructive size-7"
              @click="deleteZone(zone.id)"
            >
              <Trash2 class="size-3.5" />
            </Button>
          </div>
        </div>

        <Table v-if="slotsForZone(zone.id).length">
          <TableBody>
            <TableRow v-for="slot in slotsForZone(zone.id)" :key="slot.id">
              <TableCell class="w-24 font-mono text-sm font-semibold">
                {{ slot.label }}
              </TableCell>
              <TableCell class="text-muted-foreground capitalize">
                {{ slot.category }}
              </TableCell>
              <TableCell>
                <Badge
                  :variant="stateVariant[slot.current_state] ?? 'outline'"
                  class="capitalize"
                >
                  {{ slot.current_state }}
                </Badge>
              </TableCell>
              <TableCell class="text-right">
                <div class="flex items-center justify-end gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    class="size-7"
                    @click="openEditSlot(slot)"
                  >
                    <Pencil class="text-muted-foreground size-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    class="h-7 text-xs"
                    @click="toggleDisable(slot)"
                  >
                    {{
                      slot.current_state === "disabled" ? "Enable" : "Disable"
                    }}
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    class="text-muted-foreground hover:text-destructive size-7"
                    @click="deleteSlot(slot.id)"
                  >
                    <Trash2 class="size-3.5" />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
        <p v-else class="text-muted-foreground px-4 py-3 text-xs">
          No slots in this zone.
        </p>

        <div class="border-t px-4 py-2">
          <Button
            variant="ghost"
            size="sm"
            class="text-muted-foreground h-7 text-xs"
            @click="openAddSlot(zone.id)"
          >
            <Plus class="mr-1 size-3.5" />
            Add slot
          </Button>
        </div>
      </Card>

      <!-- Unzoned slots -->
      <Card
        v-if="slotsForZone(null).length || !zones.length"
        class="overflow-hidden p-0 gap-0"
      >
        <div class="flex items-center justify-between border-b px-4 py-2.5">
          <span
            class="text-muted-foreground text-xs font-medium uppercase tracking-wide"
          >
            General
          </span>
          <span class="text-muted-foreground text-xs">
            {{ slotsForZone(null).length }} slots
          </span>
        </div>

        <Table v-if="slotsForZone(null).length">
          <TableBody>
            <TableRow v-for="slot in slotsForZone(null)" :key="slot.id">
              <TableCell class="w-24 font-mono text-sm font-semibold">
                {{ slot.label }}
              </TableCell>
              <TableCell class="text-muted-foreground capitalize">
                {{ slot.category }}
              </TableCell>
              <TableCell>
                <Badge
                  :variant="stateVariant[slot.current_state] ?? 'outline'"
                  class="capitalize"
                >
                  {{ slot.current_state }}
                </Badge>
              </TableCell>
              <TableCell class="text-right">
                <div class="flex items-center justify-end gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    class="size-7"
                    @click="openEditSlot(slot)"
                  >
                    <Pencil class="text-muted-foreground size-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    class="h-7 text-xs"
                    @click="toggleDisable(slot)"
                  >
                    {{
                      slot.current_state === "disabled" ? "Enable" : "Disable"
                    }}
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    class="text-muted-foreground hover:text-destructive size-7"
                    @click="deleteSlot(slot.id)"
                  >
                    <Trash2 class="size-3.5" />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
        <p v-else class="text-muted-foreground px-4 py-3 text-xs">
          No slots yet.
        </p>

        <div class="border-t px-4 py-2">
          <Button
            variant="ghost"
            size="sm"
            class="text-muted-foreground h-7 text-xs"
            @click="openAddSlot(null)"
          >
            <Plus class="mr-1 size-3.5" />
            Add slot
          </Button>
        </div>
      </Card>

      <div v-if="!zones.length && !slots.length" class="py-12 text-center">
        <p class="text-muted-foreground text-sm">
          No slots yet. Add a zone or a slot to get started.
        </p>
      </div>
    </template>
  </div>

  <AddZoneDialog v-model:open="showAddZone" :lot-id="lotId" @created="load" />

  <SlotDialog
    v-model:open="showSlotDialog"
    :slot="editingSlot"
    :default-zone-id="slotDialogDefaultZoneId"
    :zones="zones"
    :lot-id="lotId"
    @saved="load"
  />
</template>
