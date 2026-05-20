<script setup lang="ts">
import type { ParkingSlotEl, SlotStatus } from "@smart-parking/types";
import { STATUS_COLORS, SLOT_COLORS } from "@smart-parking/types";
import { X } from "lucide-vue-next";

const props = defineProps<{
  slot: ParkingSlotEl | null;
  status: SlotStatus | null;
  /** Approximate walking distance in metres, if known */
  distanceM?: number | null;
}>();

const emit = defineEmits<{ close: [] }>();

const isOpen = computed(() => !!props.slot);

const statusLabel: Record<SlotStatus, string> = {
  free: "Available",
  occupied: "Occupied",
  reserved: "Reserved",
  disabled: "Disabled",
  unknown: "Unknown",
};

const categoryLabel: Record<string, string> = {
  standard: "Standard",
  compact: "Compact",
  motorcycle: "Motorcycle",
  pwd: "PWD / Accessible",
  ev: "EV Charging",
  truck: "Truck / Large",
  vip: "VIP",
};

const statusColor = computed(() =>
  props.status ? STATUS_COLORS[props.status] : "#d1d5db",
);

const categoryColor = computed(() =>
  props.slot ? (SLOT_COLORS[props.slot.category] ?? "#6366f1") : "#6366f1",
);
</script>

<template>
  <!-- Backdrop -->
  <Transition name="fade">
    <div
      v-if="isOpen"
      class="fixed inset-0 z-40 bg-black/30"
      @click="emit('close')"
    />
  </Transition>

  <!-- Bottom sheet -->
  <Transition name="slide-up">
    <div
      v-if="isOpen && slot"
      class="fixed bottom-0 left-0 right-0 z-50 rounded-t-2xl border-t bg-background shadow-xl"
    >
      <!-- Handle -->
      <div class="flex justify-center pt-3 pb-1">
        <div class="w-10 h-1 rounded-full bg-muted-foreground/30" />
      </div>

      <!-- Header -->
      <div class="flex items-start justify-between px-5 pt-2 pb-4">
        <div class="flex items-center gap-3">
          <!-- Category color dot -->
          <div
            class="size-12 rounded-xl flex items-center justify-center text-white font-mono font-bold text-base shrink-0"
            :style="{ background: categoryColor }"
          >
            {{ slot.code }}
          </div>
          <div>
            <p class="font-semibold text-base">Slot {{ slot.code }}</p>
            <p class="text-sm text-muted-foreground">
              {{ categoryLabel[slot.category] ?? slot.category }}
            </p>
          </div>
        </div>
        <button
          class="size-8 flex items-center justify-center rounded-full hover:bg-muted text-muted-foreground transition-colors"
          @click="emit('close')"
        >
          <X class="size-4" />
        </button>
      </div>

      <!-- Status -->
      <div class="px-5 pb-4">
        <div
          class="flex items-center gap-2.5 rounded-xl px-4 py-3"
          :style="{ background: statusColor + '20' }"
        >
          <span
            class="size-3 rounded-full shrink-0"
            :style="{ background: statusColor }"
          />
          <span class="font-semibold text-sm" :style="{ color: statusColor }">
            {{ status ? statusLabel[status] : "Unknown" }}
          </span>
        </div>
      </div>

      <!-- Details -->
      <div class="px-5 pb-6 space-y-3">
        <div v-if="distanceM != null" class="flex justify-between text-sm">
          <span class="text-muted-foreground">Distance from entrance</span>
          <span class=""
            >~<span class="font-medium">{{ distanceM }} m</span></span
          >
        </div>
        <div class="flex justify-between text-sm">
          <span class="text-muted-foreground">Type</span>
          <span class="font-medium">{{
            categoryLabel[slot.category] ?? slot.category
          }}</span>
        </div>
        <div class="flex justify-between text-sm">
          <span class="text-muted-foreground">Dimensions</span>
          <span class="font-medium tabular-nums"
            >{{ Math.round(slot.width / 100) / 10 }} ×
            {{ Math.round(slot.height / 100) / 10 }} m</span
          >
        </div>
        <div v-if="slot.zoneId" class="flex justify-between text-sm">
          <span class="text-muted-foreground">Zone</span>
          <span class="font-medium">{{ slot.zoneId }}</span>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-up-enter-active {
  transition: transform 0.25s cubic-bezier(0.32, 0.72, 0, 1);
}
.slide-up-leave-active {
  transition: transform 0.2s ease-in;
}
.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(100%);
}
</style>
