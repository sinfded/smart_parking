<script setup lang="ts">
const props = defineProps<{
  open: boolean;
  lotId: string;
}>();

const emit = defineEmits<{
  "update:open": [value: boolean];
  created: [];
}>();

const client = useSupabaseClient();

const newZoneName = ref("");

watch(
  () => props.open,
  (v) => { if (!v) newZoneName.value = ""; },
);

async function addZone() {
  const name = newZoneName.value.trim();
  if (!name) return;

  const { data: maxRow } = await client
    .from("zones")
    .select("sort_order")
    .eq("lot_id", props.lotId)
    .order("sort_order", { ascending: false })
    .limit(1)
    .maybeSingle();

  await client.from("zones").insert({
    lot_id: props.lotId,
    name,
    sort_order: (maxRow?.sort_order ?? 0) + 1,
  });

  emit("update:open", false);
  emit("created");
}
</script>

<template>
  <Dialog :open="open" @update:open="(v) => emit('update:open', v)">
    <DialogContent class="sm:max-w-sm">
      <DialogHeader>
        <DialogTitle>Add zone</DialogTitle>
        <DialogDescription>
          Zones group slots into sections (e.g. "Level 1", "Section A").
        </DialogDescription>
      </DialogHeader>
      <div class="space-y-2">
        <Label>Zone name</Label>
        <Input
          v-model="newZoneName"
          placeholder="Level 1"
          @keydown.enter="addZone"
        />
      </div>
      <DialogFooter>
        <Button variant="outline" @click="emit('update:open', false)">
          Cancel
        </Button>
        <Button :disabled="!newZoneName.trim()" @click="addZone">Create</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
