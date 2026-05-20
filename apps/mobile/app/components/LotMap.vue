<script setup lang="ts">
import type { LotMapConfig, LiveSlot, ParkingSlotEl, SlotStatus } from '@smart-parking/types';
import { STATUS_COLORS, SLOT_COLORS } from '@smart-parking/types';
import { useEventListener } from '@vueuse/core';

// ── Props ─────────────────────────────────────────────────────────────────────

const props = defineProps<{
  config:     LotMapConfig;
  liveSlots:  Map<string, SlotStatus>; // slotId → current status
  highlightId?: string | null;         // nearest available slot
}>();

const emit = defineEmits<{
  tapSlot: [slot: ParkingSlotEl];
}>();

// ── Derived data ──────────────────────────────────────────────────────────────

const cw = computed(() => props.config.canvas.width);
const ch = computed(() => props.config.canvas.height);

const parkingSlots = computed(() =>
  props.config.elements.filter((e): e is ParkingSlotEl => e.type === 'parking_slot' && e.visible)
);
const roads = computed(() =>
  props.config.elements.filter((e) => e.type === 'road' && e.visible)
);
const entrances = computed(() =>
  props.config.elements.filter((e) => e.type === 'entrance' && e.visible)
);
const exits = computed(() =>
  props.config.elements.filter((e) => e.type === 'exit' && e.visible)
);
const labels = computed(() =>
  props.config.elements.filter((e) => e.type === 'label' && e.visible)
);

function slotStatus(slot: ParkingSlotEl): SlotStatus {
  return slot.slotId ? (props.liveSlots.get(slot.slotId) ?? 'unknown') : 'unknown';
}

function slotFill(slot: ParkingSlotEl): string {
  const status = slotStatus(slot);
  if (status !== 'unknown' || !slot.slotId) return STATUS_COLORS[status];
  return SLOT_COLORS[slot.category] ?? '#6366f1';
}

function isHighlighted(slot: ParkingSlotEl): boolean {
  return !!props.highlightId && slot.id === props.highlightId;
}

// ── Touch zoom / pan ──────────────────────────────────────────────────────────

const wrapperRef = useTemplateRef<HTMLDivElement>('wrapper');
const svgRef     = useTemplateRef<SVGSVGElement>('svg');

const scale     = ref(1);
const panX      = ref(0);
const panY      = ref(0);
const minScale  = 0.3;
const maxScale  = 8;

// Pointer tracking
let pointers = new Map<number, { x: number; y: number }>();
let lastDist  = 0;
let lastMidX  = 0;
let lastMidY  = 0;
let isPanning  = false;

function clampScale(s: number) { return Math.max(minScale, Math.min(maxScale, s)); }

function dist(a: { x: number; y: number }, b: { x: number; y: number }) {
  return Math.hypot(b.x - a.x, b.y - a.y);
}

function onPointerDown(e: PointerEvent) {
  e.preventDefault();
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
  wrapperRef.value?.setPointerCapture(e.pointerId);

  if (pointers.size === 2) {
    const [a, b] = [...pointers.values()];
    lastDist = dist(a, b);
    lastMidX = (a.x + b.x) / 2;
    lastMidY = (a.y + b.y) / 2;
    isPanning = false;
  } else if (pointers.size === 1) {
    isPanning = true;
  }
}

function onPointerMove(e: PointerEvent) {
  if (!pointers.has(e.pointerId)) return;
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });

  if (pointers.size === 2) {
    const [a, b] = [...pointers.values()];
    const d     = dist(a, b);
    const midX  = (a.x + b.x) / 2;
    const midY  = (a.y + b.y) / 2;
    const rect  = wrapperRef.value!.getBoundingClientRect();

    const factor = d / (lastDist || d);
    const newScale = clampScale(scale.value * factor);

    // Zoom toward the pinch midpoint
    const ox = midX - rect.left;
    const oy = midY - rect.top;
    panX.value = ox - (ox - panX.value) * (newScale / scale.value);
    panY.value = oy - (oy - panY.value) * (newScale / scale.value);
    scale.value = newScale;

    // Pan
    panX.value += midX - lastMidX;
    panY.value += midY - lastMidY;

    lastDist = d;
    lastMidX = midX;
    lastMidY = midY;
  } else if (pointers.size === 1 && isPanning) {
    // Single-finger pan
    const prev = pointers.get(e.pointerId)!;
    panX.value += e.clientX - prev.x;
    panY.value += e.clientY - prev.y;
    // Update after using prev
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
  }
}

function onPointerUp(e: PointerEvent) {
  pointers.delete(e.pointerId);
  if (pointers.size < 2) isPanning = pointers.size === 1;
}

// Wheel zoom for desktop
function onWheel(e: WheelEvent) {
  e.preventDefault();
  const rect    = wrapperRef.value!.getBoundingClientRect();
  const by      = e.deltaY < 0 ? 1.12 : 1 / 1.12;
  const newSc   = clampScale(scale.value * by);
  const ox      = e.clientX - rect.left;
  const oy      = e.clientY - rect.top;
  panX.value    = ox - (ox - panX.value) * (newSc / scale.value);
  panY.value    = oy - (oy - panY.value) * (newSc / scale.value);
  scale.value   = newSc;
}

function resetView() {
  scale.value = 1;
  panX.value  = 0;
  panY.value  = 0;
}

// Mount touch/wheel listeners (non-passive to allow preventDefault)
onMounted(() => {
  const el = wrapperRef.value;
  if (!el) return;
  el.addEventListener('pointerdown', onPointerDown, { passive: false });
  el.addEventListener('pointermove', onPointerMove, { passive: false });
  el.addEventListener('pointerup',   onPointerUp,   { passive: false });
  el.addEventListener('wheel',       onWheel,       { passive: false });
  onUnmounted(() => {
    el.removeEventListener('pointerdown', onPointerDown);
    el.removeEventListener('pointermove', onPointerMove);
    el.removeEventListener('pointerup',   onPointerUp);
    el.removeEventListener('wheel',       onWheel);
  });
});

// ── Slot tap ──────────────────────────────────────────────────────────────────

function onSlotTap(slot: ParkingSlotEl) {
  emit('tapSlot', slot);
}

// ── Road polyline string ──────────────────────────────────────────────────────

function roadPolyline(points: number[]): string {
  const pairs: string[] = [];
  for (let i = 0; i < points.length - 1; i += 2) {
    pairs.push(`${points[i]},${points[i + 1]}`);
  }
  return pairs.join(' ');
}

// ── Canvas transform ──────────────────────────────────────────────────────────

const transform = computed(
  () => `translate(${panX.value}px, ${panY.value}px) scale(${scale.value})`
);
</script>

<template>
  <div class="relative w-full overflow-hidden rounded-xl border border-border bg-muted/30 select-none"
    style="aspect-ratio: unset; min-height: 220px; height: 100%">

    <!-- Touch/scroll container -->
    <div
      ref="wrapper"
      class="absolute inset-0 touch-none overflow-hidden"
      style="cursor: grab"
    >
      <!-- Transformed SVG -->
      <div :style="{ transform, transformOrigin: '0 0', willChange: 'transform', position: 'absolute', inset: 0 }">
        <svg
          ref="svg"
          :viewBox="`0 0 ${cw} ${ch}`"
          :width="cw"
          :height="ch"
          class="block"
          style="max-width: none"
        >
          <!-- Background -->
          <rect :width="cw" :height="ch" fill="#f9fafb" />

          <!-- Background image if configured -->
          <image
            v-if="config.background.url"
            :href="config.background.url"
            :x="config.background.x"
            :y="config.background.y"
            :width="config.background.width"
            :height="config.background.height"
            :opacity="config.background.opacity"
          />

          <!-- Grid -->
          <template v-if="config.grid.visible">
            <defs>
              <pattern
                id="lot-map-grid"
                :width="config.grid.size"
                :height="config.grid.size"
                patternUnits="userSpaceOnUse"
              >
                <path
                  :d="`M ${config.grid.size} 0 L 0 0 0 ${config.grid.size}`"
                  fill="none"
                  stroke="#e5e7eb"
                  stroke-width="0.5"
                />
              </pattern>
            </defs>
            <rect :width="cw" :height="ch" fill="url(#lot-map-grid)" />
          </template>

          <!-- Roads -->
          <g v-for="road in roads" :key="road.id">
            <!-- Curb border -->
            <polyline
              :points="roadPolyline((road as any).points)"
              stroke="#6b7280"
              :stroke-width="(road as any).strokeWidth * 1.14"
              stroke-linecap="round" stroke-linejoin="round" fill="none"
            />
            <!-- Asphalt -->
            <polyline
              :points="roadPolyline((road as any).points)"
              :stroke="(road as any).color || '#374151'"
              :stroke-width="(road as any).strokeWidth"
              stroke-linecap="round" stroke-linejoin="round" fill="none"
            />
            <!-- Center lane marking -->
            <polyline
              :points="roadPolyline((road as any).points)"
              :stroke="(road as any).direction === 'one-way' ? 'rgba(255,255,255,0.7)' : '#fbbf24'"
              :stroke-width="(road as any).strokeWidth * 0.08"
              :stroke-dasharray="(road as any).direction === 'one-way' ? undefined : `${(road as any).strokeWidth * 0.7} ${(road as any).strokeWidth * 0.45}`"
              stroke-linecap="round" stroke-linejoin="round" fill="none"
            />
          </g>

          <!-- Parking slots -->
          <g
            v-for="slot in parkingSlots"
            :key="slot.id"
            :transform="`translate(${slot.x},${slot.y}) rotate(${slot.rotation} ${slot.width / 2} ${slot.height / 2})`"
            style="cursor: pointer"
            @click="onSlotTap(slot)"
          >
            <!-- Highlight ring for nearest slot -->
            <rect
              v-if="isHighlighted(slot)"
              :x="-12" :y="-12"
              :width="slot.width + 24"
              :height="slot.height + 24"
              rx="10"
              fill="none"
              stroke="#facc15"
              stroke-width="16"
              opacity="0.8"
            />
            <rect
              :width="slot.width"
              :height="slot.height"
              rx="6"
              :fill="slotFill(slot)"
              :stroke="isHighlighted(slot) ? '#facc15' : 'rgba(0,0,0,0.12)'"
              :stroke-width="isHighlighted(slot) ? 8 : 2"
            />
            <text
              :x="slot.width / 2"
              :y="slot.height / 2 + slot.height * 0.06"
              text-anchor="middle"
              :font-size="Math.min(slot.width, slot.height) * 0.28"
              font-family="ui-monospace, monospace"
              font-weight="700"
              fill="white"
            >{{ slot.code }}</text>
          </g>

          <!-- Entrances -->
          <g
            v-for="el in entrances"
            :key="el.id"
            :transform="`translate(${(el as any).x},${(el as any).y}) rotate(${(el as any).rotation})`"
          >
            <rect :width="(el as any).width" :height="(el as any).height" rx="6" fill="#16a34a" opacity="0.9" />
            <text
              :x="(el as any).width / 2" :y="(el as any).height * 0.5"
              text-anchor="middle"
              :font-size="(el as any).height * 0.28"
              font-family="ui-sans-serif, sans-serif"
              font-weight="700" fill="white"
            >▼ IN</text>
          </g>

          <!-- Exits -->
          <g
            v-for="el in exits"
            :key="el.id"
            :transform="`translate(${(el as any).x},${(el as any).y}) rotate(${(el as any).rotation})`"
          >
            <rect :width="(el as any).width" :height="(el as any).height" rx="6" fill="#dc2626" opacity="0.9" />
            <text
              :x="(el as any).width / 2" :y="(el as any).height * 0.5"
              text-anchor="middle"
              :font-size="(el as any).height * 0.28"
              font-family="ui-sans-serif, sans-serif"
              font-weight="700" fill="white"
            >▲ OUT</text>
          </g>

          <!-- Labels -->
          <text
            v-for="el in labels"
            :key="el.id"
            :x="(el as any).x"
            :y="(el as any).y"
            :font-size="(el as any).fontSize"
            :fill="(el as any).color"
            :transform="`rotate(${(el as any).rotation} ${(el as any).x} ${(el as any).y})`"
            font-family="ui-sans-serif, sans-serif"
          >{{ (el as any).text }}</text>

          <!-- Canvas border -->
          <rect :width="cw" :height="ch" fill="none" stroke="#d1d5db" stroke-width="4" />

          <!-- Empty state -->
          <template v-if="!parkingSlots.length">
            <text :x="cw / 2" :y="ch / 2 - 60" text-anchor="middle" font-size="200" fill="#9ca3af" font-family="ui-sans-serif, sans-serif">No layout configured.</text>
            <text :x="cw / 2" :y="ch / 2 + 80" text-anchor="middle" font-size="140" fill="#d1d5db" font-family="ui-sans-serif, sans-serif">Use the admin dashboard to design this lot's layout.</text>
          </template>
        </svg>
      </div>
    </div>

    <!-- Reset view button -->
    <button
      class="absolute top-2 right-2 bg-background/80 backdrop-blur border rounded-lg px-2 py-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
      @click="resetView"
    >
      Reset view
    </button>

    <!-- Legend -->
    <div class="absolute bottom-2 left-2 flex flex-col gap-1 bg-background/80 backdrop-blur rounded-lg p-2 border">
      <div class="flex items-center gap-1.5 text-[10px] text-foreground">
        <span class="size-2.5 rounded-full bg-emerald-500 shrink-0" />Free
      </div>
      <div class="flex items-center gap-1.5 text-[10px] text-foreground">
        <span class="size-2.5 rounded-full bg-red-500 shrink-0" />Occupied
      </div>
      <div class="flex items-center gap-1.5 text-[10px] text-foreground">
        <span class="size-2.5 rounded-full bg-blue-500 shrink-0" />Reserved
      </div>
      <div v-if="highlightId" class="flex items-center gap-1.5 text-[10px] text-yellow-500 font-medium">
        <span class="size-2.5 rounded-full bg-yellow-400 shrink-0" />Nearest
      </div>
    </div>
  </div>
</template>
