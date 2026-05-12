<script setup lang="ts">
import { Building2, Car, ParkingSquare, Wifi } from "lucide-vue-next"

const client = useSupabaseClient()

const { data: stats, status } = await useLazyAsyncData("dashboard-stats", async () => {
  const [lots, slots, occupied, sessions] = await Promise.all([
    client.from("lots").select("*", { count: "exact", head: true }).is("deleted_at", null),
    client.from("slots").select("*", { count: "exact", head: true }).is("deleted_at", null),
    client
      .from("slots")
      .select("*", { count: "exact", head: true })
      .eq("current_state", "occupied")
      .is("deleted_at", null),
    client.from("parking_sessions").select("*", { count: "exact", head: true }).is("ended_at", null),
  ])
  return {
    lots: lots.count ?? 0,
    slots: slots.count ?? 0,
    occupied: occupied.count ?? 0,
    activeSessions: sessions.count ?? 0,
  }
})

const statCards = computed(() => [
  {
    label: "Total lots",
    value: stats.value?.lots,
    icon: Building2,
    description: "Registered parking lots",
  },
  {
    label: "Total slots",
    value: stats.value?.slots,
    icon: ParkingSquare,
    description: "Across all lots",
  },
  {
    label: "Occupied now",
    value: stats.value?.occupied,
    icon: Car,
    description: "Slots with vehicles detected",
  },
  {
    label: "Active sessions",
    value: stats.value?.activeSessions,
    icon: Wifi,
    description: "Ongoing parking sessions",
  },
])
</script>

<template>
  <div class="space-y-6">
    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Card v-for="card in statCards" :key="card.label">
        <CardHeader class="flex flex-row items-center justify-between pb-2">
          <CardTitle class="text-sm font-medium text-muted-foreground">
            {{ card.label }}
          </CardTitle>
          <component :is="card.icon" class="size-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <Skeleton v-if="status === 'pending'" class="h-8 w-16" />
          <p v-else class="text-3xl font-semibold">{{ card.value }}</p>
          <p class="mt-1 text-xs text-muted-foreground">{{ card.description }}</p>
        </CardContent>
      </Card>
    </div>
  </div>
</template>
