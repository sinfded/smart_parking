<script setup lang="ts">
import { ChevronLeft } from 'lucide-vue-next'

type SlotState = 'free' | 'occupied' | 'disabled' | 'unknown' | 'reserved'

interface LotDetail {
  lot_id: string
  name: string
  address: string | null
  total_slots: number
  free_slots: number
  occupied_slots: number
}

interface Zone {
  id: string
  name: string
  sort_order: number
}

interface Slot {
  id: string
  label: string
  category: string
  current_state: SlotState
  zone_id: string | null
}

const route = useRoute()
const id = route.params.id as string
const client = useSupabaseClient()

const lot = ref<LotDetail | null>(null)
const zones = ref<Zone[]>([])
const slots = ref<Slot[]>([])
const loading = ref(true)

async function loadData() {
  const [lotRes, zoneRes, slotRes] = await Promise.all([
    client.from('lot_availability' as any).select('*').eq('lot_id', id).single(),
    client.from('zones').select('id, name, sort_order').eq('lot_id', id).order('sort_order'),
    client
      .from('slots')
      .select('id, label, category, current_state, zone_id')
      .eq('lot_id', id)
      .is('deleted_at', null)
      .order('label'),
  ])
  lot.value = lotRes.data as unknown as LotDetail
  zones.value = (zoneRes.data ?? []) as Zone[]
  slots.value = (slotRes.data ?? []) as Slot[]
  loading.value = false
}

function slotsForZone(zoneId: string) {
  return slots.value.filter(s => s.zone_id === zoneId)
}

const unzonedSlots = computed(() => slots.value.filter(s => s.zone_id === null))

const freeCount = computed(() => slots.value.filter(s => s.current_state === 'free').length)
const totalCount = computed(() => slots.value.length)
const occupancyPercent = computed(() =>
  totalCount.value > 0 ? ((totalCount.value - freeCount.value) / totalCount.value) * 100 : 0
)

onMounted(async () => {
  await loadData()

  const channel = client
    .channel(`lot-slots-${id}`)
    .on(
      'postgres_changes' as any,
      { event: 'UPDATE', schema: 'public', table: 'slots', filter: `lot_id=eq.${id}` },
      (payload: any) => {
        const idx = slots.value.findIndex(s => s.id === payload.new.id)
        if (idx >= 0) {
          slots.value[idx] = { ...slots.value[idx], ...payload.new }
        }
      }
    )
    .subscribe()

  onUnmounted(() => { client.removeChannel(channel) })
})

useHead({ title: computed(() => lot.value?.name ?? 'Parking lot') })
</script>

<template>
  <NuxtLayout name="default">
    <template #header-left>
      <NuxtLink
        to="/"
        class="size-8 flex items-center justify-center rounded-lg hover:bg-accent transition-colors -ml-1 shrink-0"
        aria-label="Back"
      >
        <ChevronLeft class="size-5" />
      </NuxtLink>
    </template>
    <template #title>
      <span class="truncate">{{ lot?.name ?? 'Parking lot' }}</span>
    </template>
    <template #header-right>
      <div class="flex items-center gap-1.5 text-xs text-emerald-500 font-medium pr-1">
        <span class="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
        Live
      </div>
    </template>

    <!-- Skeleton -->
    <div v-if="loading">
      <Skeleton class="h-20 rounded-xl mb-4" />
      <div class="grid grid-cols-5 gap-2">
        <Skeleton v-for="n in 20" :key="n" class="aspect-square rounded-md" />
      </div>
    </div>

    <template v-else-if="lot">
      <!-- Stats bar -->
      <div class="rounded-xl border border-border bg-card p-4 mb-5">
        <div class="flex justify-between items-baseline mb-2">
          <span class="text-sm text-muted-foreground">Available slots</span>
          <span class="font-bold text-lg tabular-nums">
            {{ freeCount }}
            <span class="text-sm font-normal text-muted-foreground">/ {{ totalCount }}</span>
          </span>
        </div>
        <Progress :model-value="occupancyPercent" class="h-2" />
        <p v-if="lot.address" class="text-xs text-muted-foreground mt-2 line-clamp-1">
          {{ lot.address }}
        </p>
      </div>

      <!-- Legend -->
      <div class="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted-foreground mb-4">
        <span class="flex items-center gap-1.5"><span class="size-2.5 rounded bg-emerald-500 inline-block" />Free</span>
        <span class="flex items-center gap-1.5"><span class="size-2.5 rounded bg-red-500 inline-block" />Occupied</span>
        <span class="flex items-center gap-1.5"><span class="size-2.5 rounded bg-amber-400 inline-block" />Unknown</span>
        <span class="flex items-center gap-1.5"><span class="size-2.5 rounded bg-zinc-200 inline-block border" />Disabled</span>
      </div>

      <!-- Zoned slots -->
      <template v-if="zones.length">
        <div v-for="zone in zones" :key="zone.id" class="mb-6">
          <div class="flex items-center gap-2 mb-2">
            <span class="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              {{ zone.name }}
            </span>
            <Separator class="flex-1" />
          </div>
          <div class="grid grid-cols-5 gap-2">
            <SlotCell
              v-for="slot in slotsForZone(zone.id)"
              :key="slot.id"
              :label="slot.label"
              :state="slot.current_state"
            />
          </div>
        </div>
      </template>

      <!-- Unzoned slots -->
      <div v-if="unzonedSlots.length" class="grid grid-cols-5 gap-2">
        <SlotCell
          v-for="slot in unzonedSlots"
          :key="slot.id"
          :label="slot.label"
          :state="slot.current_state"
        />
      </div>
    </template>

    <!-- Not found -->
    <div v-else class="text-center py-20 text-muted-foreground text-sm">
      Parking lot not found.
    </div>
  </NuxtLayout>
</template>
