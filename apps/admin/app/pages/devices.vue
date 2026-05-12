<script setup lang="ts">
import { Camera, Pencil, Plus, Radio, Server, Trash2 } from "lucide-vue-next";
import type { DeviceRow } from "~/composables/useDeviceActions";

const client = useSupabaseClient();

type Device = DeviceRow & {
  health: "online" | "degraded" | "offline";
  last_seen_at: string | null;
  lots: { name: string } | null;
  slots: { label: string } | null;
};

const {
  data: devices,
  status,
  refresh,
} = await useLazyAsyncData("devices", async () => {
  const { data } = await client
    .from("devices")
    .select(
      "id, kind, mac_or_serial, lot_id, slot_id, metadata, health, last_seen_at, lots(name), slots(label)",
    )
    .order("health")
    .order("last_seen_at", { ascending: false, nullsFirst: false });
  return (data ?? []) as Device[];
});

const { editingDevice, openEdit, closeEdit, deleteDevice } =
  useDeviceActions(refresh);

const showAdd = ref(false);

function onEditClose(v: boolean) {
  if (!v) closeEdit();
}

function onEditSaved() {
  closeEdit();
  refresh();
}

const kindIcon = { ultrasonic: Radio, camera: Camera, gateway: Server };

const healthVariant = {
  online: "default",
  degraded: "secondary",
  offline: "destructive",
} as const;

function formatDate(d: string | null) {
  if (!d) return "Never";
  return new Intl.RelativeTimeFormat(undefined, { numeric: "auto" }).format(
    Math.round((new Date(d).getTime() - Date.now()) / 60000),
    "minute",
  );
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex justify-end gap-2">
      <Button variant="outline" size="sm" @click="refresh">Refresh</Button>
      <Button size="sm" @click="showAdd = true">
        <Plus class="mr-1.5 size-4" />
        Add device
      </Button>
    </div>

    <Card class="p-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Kind</TableHead>
            <TableHead>MAC / Serial</TableHead>
            <TableHead>Lot</TableHead>
            <TableHead>Slot</TableHead>
            <TableHead>Health</TableHead>
            <TableHead>Last seen</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-if="status === 'pending'">
            <TableCell colspan="7">
              <div class="space-y-2 py-2">
                <Skeleton v-for="i in 5" :key="i" class="h-8 w-full" />
              </div>
            </TableCell>
          </TableRow>
          <TableEmpty v-else-if="!devices?.length" :colspan="7">
            No devices registered.
          </TableEmpty>
          <TableRow v-for="d in devices" v-else :key="d.id">
            <TableCell>
              <div class="flex items-center gap-2 capitalize">
                <component
                  :is="kindIcon[d.kind]"
                  class="text-muted-foreground size-4"
                />
                {{ d.kind }}
              </div>
            </TableCell>
            <TableCell class="font-mono text-xs">
              {{ d.mac_or_serial }}
            </TableCell>
            <TableCell class="text-muted-foreground">
              {{ d.lots?.name ?? "—" }}
            </TableCell>
            <TableCell class="text-muted-foreground">
              {{ d.slots?.label ?? "—" }}
            </TableCell>
            <TableCell>
              <Badge :variant="healthVariant[d.health]" class="capitalize">
                {{ d.health }}
              </Badge>
            </TableCell>
            <TableCell class="text-muted-foreground">
              {{ formatDate(d.last_seen_at) }}
            </TableCell>
            <TableCell class="text-right">
              <div class="flex items-center justify-end gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  class="size-7"
                  @click="openEdit(d)"
                >
                  <Pencil class="text-muted-foreground size-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  class="text-muted-foreground hover:text-destructive size-7"
                  @click="deleteDevice(d.id)"
                >
                  <Trash2 class="size-3.5" />
                </Button>
              </div>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </Card>
  </div>

  <!-- Add -->
  <AddDeviceDialog
    :open="showAdd"
    @update:open="showAdd = $event"
    @saved="refresh"
  />

  <!-- Edit -->
  <AddDeviceDialog
    :open="!!editingDevice"
    :device="editingDevice"
    @update:open="onEditClose"
    @saved="onEditSaved"
  />
</template>
