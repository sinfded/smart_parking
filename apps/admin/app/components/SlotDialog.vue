<script setup lang="ts">
type SlotCategory =
  | "standard"
  | "compact"
  | "motorcycle"
  | "pwd"
  | "ev"
  | "truck";

type SlotRow = {
  id: string;
  label: string;
  category: string;
  zone_id: string | null;
};

type Zone = { id: string; name: string };

const CATEGORIES: SlotCategory[] = [
  "standard",
  "compact",
  "motorcycle",
  "pwd",
  "ev",
  "truck",
];

const props = defineProps<{
  open: boolean;
  slot: SlotRow | null;
  defaultZoneId?: string | null;
  zones: Zone[];
  lotId: string;
}>();

const emit = defineEmits<{
  "update:open": [value: boolean];
  saved: [];
}>();

const client = useSupabaseClient();

const slotForm = reactive({
  label: "",
  category: "standard" as SlotCategory,
  zone_id: null as string | null,
});

watch(
  () => props.slot,
  (s) => {
    slotForm.label = s?.label ?? "";
    slotForm.category = ((s?.category ?? "standard") as SlotCategory);
    slotForm.zone_id = s ? s.zone_id : (props.defaultZoneId ?? null);
  },
  { immediate: true },
);

// Also update zone_id when defaultZoneId changes in add mode
watch(
  () => props.defaultZoneId,
  (v) => {
    if (!props.slot) slotForm.zone_id = v ?? null;
  },
);

async function save() {
  if (!slotForm.label.trim()) return;
  const label = slotForm.label.trim().toUpperCase();

  if (props.slot) {
    await client
      .from("slots")
      .update({
        label,
        category: slotForm.category,
        zone_id: slotForm.zone_id || null,
      })
      .eq("id", props.slot.id);
  } else {
    await client.from("slots").insert({
      lot_id: props.lotId,
      zone_id: slotForm.zone_id || null,
      label,
      category: slotForm.category,
    });
  }

  emit("update:open", false);
  emit("saved");
}

const title = computed(() => (props.slot ? "Edit slot" : "Add slot"));
const submitLabel = computed(() => (props.slot ? "Save" : "Add"));
</script>

<template>
  <Dialog :open="open" @update:open="(v) => emit('update:open', v)">
    <DialogContent class="sm:max-w-sm">
      <DialogHeader>
        <DialogTitle>{{ title }}</DialogTitle>
      </DialogHeader>
      <div class="space-y-4">
        <div class="space-y-2">
          <Label>Label</Label>
          <Input
            v-model="slotForm.label"
            placeholder="A-01"
            class="uppercase"
            @keydown.enter="save"
          />
        </div>
        <div class="space-y-2">
          <Label>Category</Label>
          <Select v-model="slotForm.category">
            <SelectTrigger class="w-full capitalize">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem
                v-for="cat in CATEGORIES"
                :key="cat"
                :value="cat"
                class="capitalize"
              >
                {{ cat }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="space-y-2">
          <Label>Zone</Label>
          <Select
            :model-value="slotForm.zone_id ?? '__none__'"
            @update:model-value="
              (v) =>
                (slotForm.zone_id = v === '__none__' ? null : (v as string))
            "
          >
            <SelectTrigger class="w-full">
              <SelectValue placeholder="None" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__none__">None (general)</SelectItem>
              <SelectItem v-for="z in zones" :key="z.id" :value="z.id">
                {{ z.name }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      <DialogFooter>
        <Button variant="outline" @click="emit('update:open', false)">
          Cancel
        </Button>
        <Button :disabled="!slotForm.label.trim()" @click="save">
          {{ submitLabel }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
