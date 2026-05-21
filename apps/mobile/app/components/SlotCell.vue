<script setup lang="ts">
type SlotState = "free" | "occupied" | "disabled" | "unknown" | "reserved";

const props = defineProps<{ label: string; state: SlotState }>();

const cellClass = computed(() => {
  const map: Record<SlotState, string> = {
    free: "bg-emerald-500 text-white ring-2 ring-emerald-400/40",
    occupied: "bg-red-500 text-white",
    disabled: "bg-zinc-100 text-zinc-400 dark:bg-zinc-800 dark:text-zinc-600",
    unknown: "bg-amber-400 text-white",
    reserved: "bg-blue-500 text-white",
  };
  return map[props.state] ?? "bg-zinc-200 text-zinc-400";
});
</script>

<template>
  <div
    :class="cellClass"
    class="flex items-center justify-center rounded-lg aspect-square text-[10px] font-bold leading-none select-none transition-colors"
  >
    {{ label }}
  </div>
</template>
