<script setup lang="ts">
import { MapPin } from 'lucide-vue-next'

interface Props {
  lotId: string
  name: string
  address: string | null
  totalSlots: number
  freeSlots: number
  distanceMeters?: number
}

const props = defineProps<Props>()

const occupancyPercent = computed(() =>
  props.totalSlots > 0
    ? Math.round(((props.totalSlots - props.freeSlots) / props.totalSlots) * 100)
    : 0,
)

const statusConfig = computed(() => {
  if (props.totalSlots === 0) return {
    label: 'No slots',
    border: 'border-l-zinc-300 dark:border-l-zinc-600',
    bar: 'bg-zinc-300',
    text: 'text-zinc-400',
  }
  if (props.freeSlots === 0) return {
    label: 'Full',
    border: 'border-l-red-500',
    bar: 'bg-red-500',
    text: 'text-red-500',
  }
  const ratio = props.freeSlots / props.totalSlots
  if (ratio < 0.2) return {
    label: 'Almost full',
    border: 'border-l-amber-500',
    bar: 'bg-amber-500',
    text: 'text-amber-600 dark:text-amber-400',
  }
  return {
    label: 'Available',
    border: 'border-l-emerald-500',
    bar: 'bg-emerald-500',
    text: 'text-emerald-600 dark:text-emerald-400',
  }
})

function formatDistance(m: number) {
  return m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(1)} km`
}
</script>

<template>
  <NuxtLink :to="`/lots/${lotId}`" class="block">
    <div
      class="rounded-xl border border-border bg-card overflow-hidden transition-all active:scale-[0.98] hover:shadow-md border-l-4"
      :class="statusConfig.border"
    >
      <div class="px-4 pt-3.5 pb-3.5">
        <!-- Name + free count -->
        <div class="flex items-start justify-between gap-3 mb-0.5">
          <span class="font-semibold text-[15px] leading-snug flex-1">{{ name }}</span>
          <div class="shrink-0 text-right leading-none">
            <span class="text-2xl font-bold tabular-nums" :class="statusConfig.text">
              {{ freeSlots }}
            </span>
            <span class="text-xs text-muted-foreground"> free</span>
          </div>
        </div>

        <!-- Address + distance -->
        <div class="flex items-center justify-between gap-2 mb-3 min-h-4.5">
          <p v-if="address" class="text-xs text-muted-foreground line-clamp-1 flex-1">
            {{ address }}
          </p>
          <span v-else class="flex-1" />
          <span
            v-if="distanceMeters !== undefined"
            class="flex items-center gap-1 text-xs text-muted-foreground shrink-0"
          >
            <MapPin class="size-3" />
            {{ formatDistance(distanceMeters) }}
          </span>
        </div>

        <!-- Progress bar -->
        <div class="h-2 rounded-full bg-muted overflow-hidden">
          <div
            class="h-full rounded-full transition-all duration-500"
            :class="statusConfig.bar"
            :style="{ width: `${occupancyPercent}%` }"
          />
        </div>

        <!-- Bar labels -->
        <div class="flex justify-between mt-1.5 text-xs">
          <span class="font-medium" :class="statusConfig.text">{{ statusConfig.label }}</span>
          <span class="text-muted-foreground tabular-nums">{{ freeSlots }} / {{ totalSlots }} available</span>
        </div>
      </div>
    </div>
  </NuxtLink>
</template>
