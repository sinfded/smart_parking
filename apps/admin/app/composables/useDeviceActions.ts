export type DeviceKind = "ultrasonic" | "camera" | "gateway";

export type DeviceRow = {
  id: string;
  kind: DeviceKind;
  mac_or_serial: string;
  lot_id: string;
  slot_id: string | null;
  metadata: Record<string, string>;
};

export function useDeviceActions(refresh: () => unknown) {
  const client = useSupabaseClient();
  const editingDevice = ref<DeviceRow | null>(null);

  function openEdit(d: DeviceRow) {
    editingDevice.value = { ...d };
  }

  function closeEdit() {
    editingDevice.value = null;
  }

  async function deleteDevice(id: string) {
    await client.from("devices").delete().eq("id", id);
    await refresh();
  }

  return { editingDevice, openEdit, closeEdit, deleteDevice };
}
