<script setup lang="ts">
import { LocateFixed } from 'lucide-vue-next'

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
    : 0
)

const availabilityLabel = computed(() => {
  if (props.totalSlots === 0) return 'No slots'
  if (props.freeSlots === 0) return 'Full'
  return `${props.freeSlots} free`
})

const availabilityClass = computed(() => {
  if (props.freeSlots === 0) return 'text-destructive border-destructive/30'
  const ratio = props.freeSlots / props.totalSlots
  if (ratio < 0.2) return 'text-amber-600 border-amber-300'
  return 'text-emerald-600 border-emerald-300'
})

function formatDistance(m: number) {
  return m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(1)} km`
}
</script>

<template>
  <NuxtLink :to="`/lots/${lotId}`" class="block">
    <Card class="transition-transform active:scale-[0.98] cursor-pointer hover:shadow-md">
      <CardHeader class="pb-2">
        <div class="flex items-start justify-between gap-2">
          <CardTitle class="text-base leading-snug">{{ name }}</CardTitle>
          <Badge variant="outline" :class="availabilityClass" class="shrink-0 text-xs font-semibold">
            {{ availabilityLabel }}
          </Badge>
        </div>
        <CardDescription v-if="address" class="text-xs line-clamp-1 mt-0.5">
          {{ address }}
        </CardDescription>
      </CardHeader>
      <CardContent class="pb-4">
        <Progress :model-value="occupancyPercent" class="h-1.5" />
        <div class="flex justify-between mt-1.5 text-xs text-muted-foreground">
          <span>{{ freeSlots }}/{{ totalSlots }} available</span>
          <span v-if="distanceMeters !== undefined" class="flex items-center gap-1">
            <LocateFixed class="size-3" />
            {{ formatDistance(distanceMeters) }}
          </span>
        </div>
      </CardContent>
    </Card>
  </NuxtLink>
</template>
