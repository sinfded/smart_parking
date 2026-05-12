<script setup lang="ts">
import { Check, Pencil, X } from "lucide-vue-next";

export type SessionDetail = {
  id: string;
  slot_id: string;
  started_at: string;
  ended_at: string | null;
  duration_seconds: number | null;
  plate_number: string | null;
  slots: { label: string } | null;
  lots: { name: string } | null;
};

const props = defineProps<{
  session: SessionDetail | null;
}>();

const emit = defineEmits<{
  close: [];
  updated: [];
}>();

const client = useSupabaseClient();

const local = ref<SessionDetail | null>(null);
const actionLoading = ref(false);
const editingPlate = ref(false);
const plateInput = ref("");

watch(
  () => props.session,
  (s) => {
    local.value = s;
    editingPlate.value = false;
  },
  { immediate: true },
);

async function closeSession() {
  if (!local.value || local.value.ended_at) return;
  actionLoading.value = true;
  await client.rpc("report_slot_state", {
    p_slot_id: local.value.slot_id,
    p_new_state: "free",
    p_source: "manual",
  });
  emit("updated");
  emit("close");
  actionLoading.value = false;
}

function startEditPlate() {
  plateInput.value = local.value?.plate_number ?? "";
  editingPlate.value = true;
}

async function savePlate() {
  if (!local.value) return;
  const plate = plateInput.value.trim().toUpperCase() || null;
  await client
    .from("parking_sessions")
    .update({ plate_number: plate })
    .eq("id", local.value.id);
  local.value = { ...local.value, plate_number: plate };
  editingPlate.value = false;
  emit("updated");
}

function formatDate(d: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(d));
}

function formatDuration(seconds: number | null) {
  if (!seconds) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}
</script>

<template>
  <Sheet
    :open="!!session"
    @update:open="
      (v) => {
        if (!v) emit('close');
      }
    "
  >
    <SheetContent class="sm:max-w-sm overflow-y-auto p-4">
      <SheetHeader class="p-0">
        <SheetTitle>Session details</SheetTitle>
        <SheetDescription>
          {{ local?.slots?.label ?? "—" }} · {{ local?.lots?.name ?? "—" }}
        </SheetDescription>
      </SheetHeader>

      <div v-if="local" class="mt-6 space-y-6">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <p class="text-muted-foreground text-xs">Slot</p>
            <p class="font-medium">{{ local.slots?.label ?? "—" }}</p>
          </div>
          <div>
            <p class="text-muted-foreground text-xs">Lot</p>
            <p class="font-medium">{{ local.lots?.name ?? "—" }}</p>
          </div>

          <!-- Plate (editable) -->
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
              <p class="font-mono font-medium">
                {{ local.plate_number ?? "—" }}
              </p>
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

          <div>
            <p class="text-muted-foreground text-xs">Status</p>
            <Badge v-if="!local.ended_at">Active</Badge>
            <span v-else class="text-muted-foreground text-sm">Completed</span>
          </div>
          <div>
            <p class="text-muted-foreground text-xs">Started</p>
            <p class="text-sm">{{ formatDate(local.started_at) }}</p>
          </div>
          <div>
            <p class="text-muted-foreground text-xs">Ended</p>
            <p class="text-sm">
              {{ local.ended_at ? formatDate(local.ended_at) : "—" }}
            </p>
          </div>
          <div>
            <p class="text-muted-foreground text-xs">Duration</p>
            <p class="text-sm">{{ formatDuration(local.duration_seconds) }}</p>
          </div>
        </div>

        <!-- Actions (active only) -->
        <div v-if="!local.ended_at" class="space-y-2 border-t pt-4">
          <p
            class="text-muted-foreground text-xs font-medium uppercase tracking-wide"
          >
            Actions
          </p>
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
      </div>
    </SheetContent>
  </Sheet>
</template>
