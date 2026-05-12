<script setup lang="ts">
import { MapPin, Plus } from "lucide-vue-next"

const client = useSupabaseClient()

const { data: lots, status, refresh } = await useLazyAsyncData("lots", async () => {
  const { data } = await client.from("lot_availability").select("*")
  return data ?? []
})

const showCreate = ref(false)
const creating = ref(false)
const form = reactive({
  name: "",
  address: "",
  timezone: "UTC",
  is_public: true,
})

async function createLot() {
  if (!form.name.trim()) return
  creating.value = true
  await client.from("lots").insert({
    name: form.name.trim(),
    address: form.address.trim() || null,
    timezone: form.timezone,
    is_public: form.is_public,
  })
  creating.value = false
  showCreate.value = false
  form.name = ""
  form.address = ""
  await refresh()
}

function occupancyPercent(lot: { occupied_slots: number | null; total_slots: number | null }) {
  if (!lot.total_slots) return 0
  return Math.round(((lot.occupied_slots ?? 0) / lot.total_slots) * 100)
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <p class="text-muted-foreground text-sm">
        {{ lots?.length ?? 0 }} lot{{ lots?.length === 1 ? "" : "s" }} registered
      </p>
      <Dialog v-model:open="showCreate">
        <DialogTrigger as-child>
          <Button size="sm">
            <Plus class="mr-2 size-4" />
            New lot
          </Button>
        </DialogTrigger>
        <DialogContent class="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Create parking lot</DialogTitle>
            <DialogDescription>Add a new lot to the platform.</DialogDescription>
          </DialogHeader>
          <form class="space-y-4" @submit.prevent="createLot">
            <div class="space-y-2">
              <Label for="lot-name">Name</Label>
              <Input id="lot-name" v-model="form.name" placeholder="Central Parking A" required />
            </div>
            <div class="space-y-2">
              <Label for="lot-address">Address</Label>
              <Input id="lot-address" v-model="form.address" placeholder="123 Main St" />
            </div>
            <div class="space-y-2">
              <Label for="lot-tz">Timezone</Label>
              <Input id="lot-tz" v-model="form.timezone" placeholder="UTC" />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" @click="showCreate = false">Cancel</Button>
              <Button type="submit" :disabled="creating || !form.name.trim()">
                <Spinner v-if="creating" class="mr-2 size-4" />
                Create
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>

    <div v-if="status === 'pending'" class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <Skeleton v-for="i in 3" :key="i" class="h-40 rounded-xl" />
    </div>

    <div v-else-if="lots?.length" class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <NuxtLink
        v-for="lot in lots"
        :key="lot.lot_id!"
        :to="`/lots/${lot.lot_id}`"
        class="group"
      >
        <Card class="hover:border-ring/50 transition-colors">
          <CardHeader class="pb-3">
            <CardTitle class="text-base">{{ lot.name }}</CardTitle>
            <CardDescription v-if="lot.address" class="flex items-center gap-1">
              <MapPin class="size-3" />
              {{ lot.address }}
            </CardDescription>
          </CardHeader>
          <CardContent class="space-y-3">
            <div class="flex items-center justify-between text-sm">
              <span class="text-muted-foreground">Occupancy</span>
              <span class="font-medium">
                {{ lot.occupied_slots ?? 0 }} / {{ lot.total_slots ?? 0 }}
              </span>
            </div>
            <div class="bg-muted h-2 w-full overflow-hidden rounded-full">
              <div
                class="h-full rounded-full bg-primary transition-all"
                :style="{ width: `${occupancyPercent(lot)}%` }"
              />
            </div>
            <div class="flex gap-2">
              <Badge variant="secondary">{{ lot.free_slots ?? 0 }} free</Badge>
              <Badge v-if="(lot.occupied_slots ?? 0) > 0">{{ lot.occupied_slots }} occupied</Badge>
            </div>
          </CardContent>
        </Card>
      </NuxtLink>
    </div>

    <div v-else class="flex flex-col items-center justify-center py-20 text-center">
      <p class="text-muted-foreground text-sm">No lots yet. Create one to get started.</p>
    </div>
  </div>
</template>
