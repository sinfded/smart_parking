<script setup lang="ts">
type SlotState = 'free' | 'occupied' | 'disabled' | 'unknown' | 'reserved'

const props = defineProps<{ label: string; state: SlotState }>()

const cellClass = computed(() => {
  const map: Record<SlotState, string> = {
    free:     'bg-emerald-500 text-white',
    occupied: 'bg-red-500 text-white',
    disabled: 'bg-zinc-200 text-zinc-400 dark:bg-zinc-700 dark:text-zinc-500',
    unknown:  'bg-amber-400 text-white',
    reserved: 'bg-blue-500 text-white',
  }
  return map[props.state] ?? 'bg-zinc-200 text-zinc-400'
})
</script>

<template>
  <div
    :class="cellClass"
    class="flex items-center justify-center rounded-md aspect-square text-[10px] font-bold leading-none select-none"
  >
    {{ label }}
  </div>
</template>
