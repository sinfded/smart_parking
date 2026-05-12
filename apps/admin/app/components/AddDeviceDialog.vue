<script setup lang="ts">
import type { DeviceRow, DeviceKind } from "~/composables/useDeviceActions";

const KINDS: DeviceKind[] = ["ultrasonic", "camera", "gateway"];

const props = defineProps<{
  open: boolean;
  device?: DeviceRow | null;
}>();

const emit = defineEmits<{
  "update:open": [value: boolean];
  saved: [];
}>();

const client = useSupabaseClient();

const { data: lots } = await useLazyAsyncData("add-device-lots", async () => {
  const { data } = await client
    .from("lots")
    .select("id, name")
    .is("deleted_at", null)
    .order("name");
  return data ?? [];
});

const slots = ref<{ id: string; label: string }[]>([]);
const pendingSlotId = ref<string | null>(null);

const form = reactive({
  kind: "ultrasonic" as DeviceKind,
  mac_or_serial: "",
  lot_id: "",
  slot_id: null as string | null,
  camera_name: "",
  camera_url: "",
});

const saving = ref(false);
const error = ref("");

// Fetch slots when lot changes; restore pendingSlotId after load (edit mode)
watch(
  () => form.lot_id,
  async (lotId) => {
    slots.value = [];
    if (!pendingSlotId.value) form.slot_id = null;
    if (!lotId || form.kind !== "ultrasonic") {
      pendingSlotId.value = null;
      return;
    }
    const { data } = await client
      .from("slots")
      .select("id, label")
      .eq("lot_id", lotId)
      .is("deleted_at", null)
      .order("label");
    slots.value = data ?? [];
    if (pendingSlotId.value) {
      form.slot_id = pendingSlotId.value;
      pendingSlotId.value = null;
    }
  },
);

// Re-fetch slots when kind switches back to ultrasonic
watch(
  () => form.kind,
  () => {
    form.slot_id = null;
    slots.value = [];
    if (form.kind === "ultrasonic" && form.lot_id) {
      const lotId = form.lot_id;
      form.lot_id = "";
      nextTick(() => { form.lot_id = lotId; });
    }
  },
);

// Populate form when a device is passed for editing
watch(
  () => props.device,
  (d) => {
    if (!d) return;
    form.kind = d.kind;
    form.mac_or_serial = d.mac_or_serial;
    form.camera_name = d.metadata?.name ?? "";
    form.camera_url = d.metadata?.url ?? "";
    pendingSlotId.value = d.slot_id;
    form.lot_id = d.lot_id;
  },
  { immediate: true },
);

// Reset when dialog closes in add mode
watch(
  () => props.open,
  (v) => { if (!v && !props.device) resetForm(); },
);

function resetForm() {
  form.kind = "ultrasonic";
  form.mac_or_serial = "";
  form.lot_id = "";
  form.slot_id = null;
  form.camera_name = "";
  form.camera_url = "";
  error.value = "";
  slots.value = [];
  pendingSlotId.value = null;
}

async function save() {
  if (!form.mac_or_serial.trim() || !form.lot_id) return;
  saving.value = true;
  error.value = "";

  const metadata: Record<string, string> = {};
  if (form.kind === "camera") {
    if (form.camera_url.trim()) metadata.url = form.camera_url.trim();
    if (form.camera_name.trim()) metadata.name = form.camera_name.trim();
  }

  const payload = {
    kind: form.kind,
    mac_or_serial: form.mac_or_serial.trim(),
    lot_id: form.lot_id,
    slot_id: form.kind === "ultrasonic" && form.slot_id ? form.slot_id : null,
    metadata,
  };

  const { error: dbError } = props.device
    ? await client.from("devices").update(payload).eq("id", props.device.id)
    : await client.from("devices").insert(payload);

  saving.value = false;

  if (dbError) {
    error.value = dbError.message.includes("unique")
      ? "A device with that MAC / serial already exists in this lot."
      : dbError.message;
    return;
  }

  emit("update:open", false);
  emit("saved");
}

const isEdit = computed(() => !!props.device);
const canSubmit = computed(
  () => !saving.value && !!form.mac_or_serial.trim() && !!form.lot_id,
);
</script>

<template>
  <Dialog :open="open" @update:open="(v) => emit('update:open', v)">
    <DialogContent class="sm:max-w-sm">
      <DialogHeader>
        <DialogTitle>{{ isEdit ? "Edit device" : "Add device" }}</DialogTitle>
        <DialogDescription v-if="!isEdit">
          Register a physical device to a parking lot.
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-4">
        <!-- Kind -->
        <div class="space-y-2">
          <Label>Kind</Label>
          <Select v-model="form.kind">
            <SelectTrigger class="w-full capitalize">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem
                v-for="k in KINDS"
                :key="k"
                :value="k"
                class="capitalize"
              >
                {{ k }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        <!-- MAC / Serial -->
        <div class="space-y-2">
          <Label>MAC / Serial</Label>
          <Input
            v-model="form.mac_or_serial"
            placeholder="AA:BB:CC:DD:EE:FF"
            class="font-mono"
            @keydown.enter="save"
          />
        </div>

        <!-- Lot -->
        <div class="space-y-2">
          <Label>Lot</Label>
          <Select v-model="form.lot_id">
            <SelectTrigger class="w-full">
              <SelectValue placeholder="Select a lot" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="lot in lots" :key="lot.id" :value="lot.id">
                {{ lot.name }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        <!-- Slot (ultrasonic only) -->
        <div v-if="form.kind === 'ultrasonic'" class="space-y-2">
          <Label>
            Slot
            <span class="text-muted-foreground text-xs">(optional)</span>
          </Label>
          <Select
            :model-value="form.slot_id ?? '__none__'"
            :disabled="!form.lot_id || !slots.length"
            @update:model-value="
              (v) => (form.slot_id = v === '__none__' ? null : (v as string))
            "
          >
            <SelectTrigger class="w-full">
              <SelectValue
                :placeholder="
                  form.lot_id ? 'Select a slot' : 'Select a lot first'
                "
              />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__none__">None</SelectItem>
              <SelectItem v-for="s in slots" :key="s.id" :value="s.id">
                {{ s.label }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        <!-- Camera fields -->
        <template v-if="form.kind === 'camera'">
          <div class="space-y-2">
            <Label>
              Camera name
              <span class="text-muted-foreground text-xs">(optional)</span>
            </Label>
            <Input v-model="form.camera_name" placeholder="Entry camera" />
          </div>
          <div class="space-y-2">
            <Label>
              RTSP URL
              <span class="text-muted-foreground text-xs">(optional)</span>
            </Label>
            <Input
              v-model="form.camera_url"
              placeholder="rtsp://user:pass@192.168.0.160:554/stream1"
              class="font-mono text-xs"
            />
          </div>
        </template>

        <p v-if="error" class="text-destructive text-sm">{{ error }}</p>
      </div>

      <DialogFooter>
        <Button variant="outline" @click="emit('update:open', false)">
          Cancel
        </Button>
        <Button :disabled="!canSubmit" @click="save">
          <Spinner v-if="saving" class="mr-2 size-4" />
          {{ isEdit ? "Save" : "Add device" }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
