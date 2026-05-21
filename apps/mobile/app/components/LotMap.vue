<script setup lang="ts">
import type {
  LotMapConfig,
  ParkingSlotEl,
  SlotStatus,
} from "@smart-parking/types";
import { STATUS_COLORS, SLOT_COLORS } from "@smart-parking/types";
import { MaximizeIcon } from "lucide-vue-next";

// ── Props ─────────────────────────────────────────────────────────────────────

const props = defineProps<{
  config: LotMapConfig;
  liveSlots: Map<string, SlotStatus>;
  highlightId?: string | null;
}>();

const emit = defineEmits<{
  tapSlot: [slot: ParkingSlotEl];
}>();

// ── Derived data ──────────────────────────────────────────────────────────────

const cw = computed(() => props.config.canvas.width);
const ch = computed(() => props.config.canvas.height);

const boundaries = computed(() =>
  props.config.elements.filter((e) => e.type === "boundary" && e.visible),
);

const parkingSlots = computed(() =>
  props.config.elements.filter(
    (e): e is ParkingSlotEl => e.type === "parking_slot" && e.visible,
  ),
);

const roads = computed(() =>
  props.config.elements.filter((e) => e.type === "road" && e.visible),
);
const entrances = computed(() =>
  props.config.elements.filter((e) => e.type === "entrance" && e.visible),
);
const exits = computed(() =>
  props.config.elements.filter((e) => e.type === "exit" && e.visible),
);
const labels = computed(() =>
  props.config.elements.filter((e) => e.type === "label" && e.visible),
);

// ── Slot state helpers ────────────────────────────────────────────────────────

function slotStatus(slot: ParkingSlotEl): SlotStatus {
  return slot.slotId
    ? (props.liveSlots.get(slot.slotId) ?? "unknown")
    : "unknown";
}

const STATUS_OPACITY: Record<SlotStatus, number> = {
  free: 0.32,
  occupied: 0.42,
  reserved: 0.38,
  disabled: 0.12,
  unknown: 0.18,
};

function slotOverlayOpacity(slot: ParkingSlotEl): number {
  return STATUS_OPACITY[slotStatus(slot)];
}

function slotStatusColor(slot: ParkingSlotEl): string {
  return STATUS_COLORS[slotStatus(slot)];
}

function slotCategoryColor(slot: ParkingSlotEl): string {
  return SLOT_COLORS[slot.category] ?? "#6366f1";
}

function isHighlighted(slot: ParkingSlotEl): boolean {
  return !!props.highlightId && slot.id === props.highlightId;
}

// ── Tapped slot (local selection feedback) ────────────────────────────────────

const tappedId = ref<string | null>(null);

function onSlotTap(slot: ParkingSlotEl) {
  tappedId.value = tappedId.value === slot.id ? null : slot.id;
  emit("tapSlot", slot);
}

// ── Touch zoom / pan ──────────────────────────────────────────────────────────

const wrapperRef = useTemplateRef<HTMLDivElement>("wrapper");

const scale = ref(1);
const panX = ref(0);
const panY = ref(0);
const minScale = 0.05;
const maxScale = 8;

let pointers = new Map<number, { x: number; y: number }>();
let lastDist = 0;
let lastMidX = 0;
let lastMidY = 0;
let isPanning = false;

function clampScale(s: number) {
  return Math.max(minScale, Math.min(maxScale, s));
}

function ptDist(a: { x: number; y: number }, b: { x: number; y: number }) {
  return Math.hypot(b.x - a.x, b.y - a.y);
}

function onPointerDown(e: PointerEvent) {
  e.preventDefault();
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
  wrapperRef.value?.setPointerCapture(e.pointerId);
  if (pointers.size === 2) {
    const [a, b] = [...pointers.values()] as [
      { x: number; y: number },
      { x: number; y: number },
    ];
    lastDist = ptDist(a, b);
    lastMidX = (a.x + b.x) / 2;
    lastMidY = (a.y + b.y) / 2;
    isPanning = false;
  } else if (pointers.size === 1) {
    isPanning = true;
  }
}

function onPointerMove(e: PointerEvent) {
  if (!pointers.has(e.pointerId)) return;
  const prev = pointers.get(e.pointerId)!;
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });

  if (pointers.size === 2) {
    const [a, b] = [...pointers.values()] as [
      { x: number; y: number },
      { x: number; y: number },
    ];
    const d = ptDist(a, b);
    const midX = (a.x + b.x) / 2;
    const midY = (a.y + b.y) / 2;
    const rect = wrapperRef.value!.getBoundingClientRect();
    const factor = d / (lastDist || d);
    const newSc = clampScale(scale.value * factor);
    const ox = midX - rect.left;
    const oy = midY - rect.top;
    panX.value =
      ox - (ox - panX.value) * (newSc / scale.value) + (midX - lastMidX);
    panY.value =
      oy - (oy - panY.value) * (newSc / scale.value) + (midY - lastMidY);
    scale.value = newSc;
    lastDist = d;
    lastMidX = midX;
    lastMidY = midY;
  } else if (pointers.size === 1 && isPanning) {
    panX.value += e.clientX - prev.x;
    panY.value += e.clientY - prev.y;
  }
}

function onPointerUp(e: PointerEvent) {
  pointers.delete(e.pointerId);
  if (pointers.size < 2) isPanning = pointers.size === 1;
}

function onWheel(e: WheelEvent) {
  e.preventDefault();
  const rect = wrapperRef.value!.getBoundingClientRect();
  const by = e.deltaY < 0 ? 1.12 : 1 / 1.12;
  const newSc = clampScale(scale.value * by);
  const ox = e.clientX - rect.left;
  const oy = e.clientY - rect.top;
  panX.value = ox - (ox - panX.value) * (newSc / scale.value);
  panY.value = oy - (oy - panY.value) * (newSc / scale.value);
  scale.value = newSc;
}

function fitToContent() {
  const el = wrapperRef.value;
  if (!el) return;

  let minX = Infinity,
    minY = Infinity,
    maxX = -Infinity,
    maxY = -Infinity;
  let hasBounds = false;

  // Prefer boundary bounding box
  const bList = boundaries.value;
  if (bList.length) {
    for (const b of bList) {
      const pts = (b as any).points as number[];
      for (let i = 0; i + 1 < pts.length; i += 2) {
        minX = Math.min(minX, pts[i]!);
        minY = Math.min(minY, pts[i + 1]!);
        maxX = Math.max(maxX, pts[i]!);
        maxY = Math.max(maxY, pts[i + 1]!);
      }
    }
    hasBounds = true;
  } else if (parkingSlots.value.length) {
    for (const s of parkingSlots.value) {
      minX = Math.min(minX, s.x);
      minY = Math.min(minY, s.y);
      maxX = Math.max(maxX, s.x + s.width);
      maxY = Math.max(maxY, s.y + s.height);
    }
    hasBounds = true;
  }

  if (!hasBounds) {
    minX = 0;
    minY = 0;
    maxX = cw.value;
    maxY = ch.value;
  }

  const pad = hasBounds
    ? Math.min((maxX - minX) * 0.05, (maxY - minY) * 0.05, 150)
    : 0;
  minX -= pad;
  minY -= pad;
  maxX += pad;
  maxY += pad;

  const bboxW = maxX - minX;
  const bboxH = maxY - minY;
  const rect = el.getBoundingClientRect();
  const newScale = clampScale(
    Math.min(rect.width / bboxW, rect.height / bboxH),
  );
  panX.value = (rect.width - bboxW * newScale) / 2 - minX * newScale;
  panY.value = (rect.height - bboxH * newScale) / 2 - minY * newScale;
  scale.value = newScale;
}

function resetView() {
  fitToContent();
}

let fittedOnce = false;

onMounted(() => {
  const el = wrapperRef.value;
  if (!el) return;
  el.addEventListener("pointerdown", onPointerDown, { passive: false });
  el.addEventListener("pointermove", onPointerMove, { passive: false });
  el.addEventListener("pointerup", onPointerUp, { passive: false });
  el.addEventListener("wheel", onWheel, { passive: false });
  onUnmounted(() => {
    el.removeEventListener("pointerdown", onPointerDown);
    el.removeEventListener("pointermove", onPointerMove);
    el.removeEventListener("pointerup", onPointerUp);
    el.removeEventListener("wheel", onWheel);
  });

  // Fit immediately if slots are already available, otherwise wait for first load
  nextTick(() => {
    if (parkingSlots.value.length) {
      fitToContent();
      fittedOnce = true;
    }
  });
});

watch([parkingSlots, boundaries], () => {
  if (!fittedOnce && (parkingSlots.value.length || boundaries.value.length)) {
    nextTick(fitToContent);
    fittedOnce = true;
  }
});

// ── Road polyline ─────────────────────────────────────────────────────────────

function roadPolyline(points: number[]): string {
  const pairs: string[] = [];
  for (let i = 0; i + 1 < points.length; i += 2) {
    pairs.push(`${points[i]},${points[i + 1]}`);
  }
  return pairs.join(" ");
}

// ── Canvas transform ──────────────────────────────────────────────────────────

const transform = computed(
  () => `translate(${panX.value}px, ${panY.value}px) scale(${scale.value})`,
);
</script>

<template>
  <div
    class="relative w-full overflow-hidden rounded-xl border border-border select-none"
    style="min-height: 220px"
  >
    <!-- Touch / scroll container -->
    <div
      ref="wrapper"
      class="absolute inset-0 touch-none overflow-hidden"
      style="cursor: grab; background: #111827"
    >
      <!-- Transformed SVG -->
      <div
        :style="{
          transform,
          transformOrigin: '0 0',
          willChange: 'transform',
          position: 'absolute',
          inset: 0,
        }"
      >
        <svg
          :viewBox="`0 0 ${cw} ${ch}`"
          :width="cw"
          :height="ch"
          class="block"
          style="max-width: none"
        >
          <defs>
            <!-- Asphalt grain pattern -->
            <pattern
              id="asphalt-bg"
              :width="config.grid.size"
              :height="config.grid.size"
              patternUnits="userSpaceOnUse"
            >
              <rect
                :width="config.grid.size"
                :height="config.grid.size"
                fill="#1f2937"
              />
              <line :x2="config.grid.size" stroke="#243044" stroke-width="1" />
              <line :y2="config.grid.size" stroke="#243044" stroke-width="1" />
            </pattern>
            <!-- Slot glow filter -->
            <filter id="slot-glow" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="40" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          <!-- ── Dark asphalt background ───────────────────────────────── -->
          <rect :width="cw" :height="ch" fill="url(#asphalt-bg)" />

          <!-- Background image overlay -->
          <image
            v-if="config.background.url"
            :href="config.background.url"
            :x="config.background.x"
            :y="config.background.y"
            :width="config.background.width"
            :height="config.background.height"
            :opacity="config.background.opacity"
          />

          <!-- ── Property boundaries ──────────────────────────────────── -->
          <g v-for="b in boundaries" :key="b.id">
            <polygon
              :points="
                (b as any).points.reduce(
                  (acc: string, v: number, i: number) =>
                    i % 2 === 0 ? acc + (acc ? ' ' : '') + v : acc + ',' + v,
                  '',
                )
              "
              :fill="`rgba(249,115,22,${(b as any).fillOpacity})`"
              :stroke="(b as any).strokeColor"
              :stroke-width="(b as any).strokeWidth"
              stroke-dasharray="60 30"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </g>

          <!-- ── Roads ─────────────────────────────────────────────────── -->
          <g v-for="road in roads" :key="road.id">
            <!-- Curb edge -->
            <polyline
              :points="roadPolyline((road as any).points)"
              :stroke="
                (road as any).color === '#374151' ? '#374151' : '#4b5563'
              "
              :stroke-width="(road as any).strokeWidth * 1.2"
              stroke-linecap="butt"
              stroke-linejoin="miter"
              fill="none"
            />
            <!-- Asphalt surface -->
            <polyline
              :points="roadPolyline((road as any).points)"
              :stroke="(road as any).color || '#374151'"
              :stroke-width="(road as any).strokeWidth"
              stroke-linecap="butt"
              stroke-linejoin="miter"
              fill="none"
            />
            <!-- Lane marking -->
            <polyline
              :points="roadPolyline((road as any).points)"
              :stroke="
                (road as any).direction === 'one-way'
                  ? 'rgba(255,255,255,0.55)'
                  : '#fbbf24'
              "
              :stroke-width="(road as any).strokeWidth * 0.07"
              :stroke-dasharray="
                (road as any).direction === 'one-way'
                  ? undefined
                  : `${(road as any).strokeWidth * 0.6} ${(road as any).strokeWidth * 0.4}`
              "
              stroke-linecap="butt"
              stroke-linejoin="miter"
              fill="none"
            />
          </g>

          <!-- ── Parking slots ──────────────────────────────────────────── -->
          <g
            v-for="slot in parkingSlots"
            :key="slot.id"
            :transform="`translate(${slot.x},${slot.y}) rotate(${slot.rotation})`"
            style="cursor: pointer"
            @click="onSlotTap(slot)"
          >
            <!-- Nearest-slot pulsing glow ring (behind everything) -->
            <rect
              v-if="isHighlighted(slot)"
              :x="-20"
              :y="-20"
              :width="slot.width + 40"
              :height="slot.height + 40"
              rx="14"
              fill="none"
              stroke="#facc15"
              stroke-width="24"
              class="slot-highlight-glow"
            />

            <!-- Asphalt base -->
            <rect
              :width="slot.width"
              :height="slot.height"
              fill="#111827"
              stroke="#0d1017"
              stroke-width="2"
            />

            <!-- Status color overlay -->
            <rect
              :width="slot.width"
              :height="slot.height"
              :fill="slotStatusColor(slot)"
              :opacity="slotOverlayOpacity(slot)"
            />

            <!-- Left painted boundary line -->
            <line
              x1="5"
              y1="0"
              x2="5"
              :y2="slot.height"
              stroke="rgba(255,255,255,0.75)"
              stroke-width="5"
            />
            <!-- Right painted boundary line -->
            <line
              :x1="slot.width - 5"
              y1="0"
              :x2="slot.width - 5"
              :y2="slot.height"
              stroke="rgba(255,255,255,0.75)"
              stroke-width="5"
            />

            <!-- Category color stripe at head of stall -->
            <rect
              x="5"
              y="0"
              :width="slot.width - 10"
              :height="Math.max(8, Math.round(slot.height * 0.07))"
              :fill="slotCategoryColor(slot)"
            />

            <!-- Slot code — floor lettering -->
            <text
              :x="slot.width / 2"
              :y="slot.height * 0.46"
              text-anchor="middle"
              dominant-baseline="middle"
              :font-size="Math.min(slot.width, slot.height) * 0.27"
              font-family="ui-monospace, monospace"
              font-weight="700"
              fill="rgba(255,255,255,0.92)"
            >
              {{ slot.code }}
            </text>

            <!-- Status indicator dot -->
            <circle
              :cx="slot.width / 2"
              :cy="slot.height * 0.75"
              :r="Math.min(slot.width, slot.height) * 0.08"
              :fill="slotStatusColor(slot)"
            />

            <!-- Nearest-slot bright border -->
            <rect
              v-if="isHighlighted(slot)"
              :width="slot.width"
              :height="slot.height"
              fill="none"
              stroke="#facc15"
              stroke-width="12"
              class="slot-highlight-border"
            />

            <!-- Tapped / selected slot border -->
            <rect
              v-if="tappedId === slot.id"
              :width="slot.width"
              :height="slot.height"
              fill="rgba(59,130,246,0.08)"
              stroke="#3b82f6"
              stroke-width="14"
            />
          </g>

          <!-- ── Entrances ───────────────────────────────────────────────── -->
          <g
            v-for="el in entrances"
            :key="el.id"
            :transform="`translate(${(el as any).x},${(el as any).y}) rotate(${(el as any).rotation})`"
          >
            <rect
              :width="(el as any).width"
              :height="(el as any).height"
              rx="8"
              fill="#14532d"
              stroke="#16a34a"
              stroke-width="6"
            />
            <!-- Arrow chevron pointing down (enter) -->
            <polyline
              :points="`
                ${(el as any).width * 0.3},${(el as any).height * 0.28}
                ${(el as any).width * 0.5},${(el as any).height * 0.52}
                ${(el as any).width * 0.7},${(el as any).height * 0.28}
              `"
              fill="none"
              stroke="#4ade80"
              stroke-width="28"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
            <text
              :x="(el as any).width / 2"
              :y="(el as any).height * 0.82"
              text-anchor="middle"
              dominant-baseline="middle"
              :font-size="(el as any).height * 0.22"
              font-family="ui-sans-serif, sans-serif"
              font-weight="700"
              fill="#4ade80"
              letter-spacing="4"
            >
              IN
            </text>
          </g>

          <!-- ── Exits ──────────────────────────────────────────────────── -->
          <g
            v-for="el in exits"
            :key="el.id"
            :transform="`translate(${(el as any).x},${(el as any).y}) rotate(${(el as any).rotation})`"
          >
            <rect
              :width="(el as any).width"
              :height="(el as any).height"
              rx="8"
              fill="#450a0a"
              stroke="#dc2626"
              stroke-width="6"
            />
            <!-- Arrow chevron pointing up (exit) -->
            <polyline
              :points="`
                ${(el as any).width * 0.3},${(el as any).height * 0.52}
                ${(el as any).width * 0.5},${(el as any).height * 0.28}
                ${(el as any).width * 0.7},${(el as any).height * 0.52}
              `"
              fill="none"
              stroke="#f87171"
              stroke-width="28"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
            <text
              :x="(el as any).width / 2"
              :y="(el as any).height * 0.82"
              text-anchor="middle"
              dominant-baseline="middle"
              :font-size="(el as any).height * 0.22"
              font-family="ui-sans-serif, sans-serif"
              font-weight="700"
              fill="#f87171"
              letter-spacing="4"
            >
              OUT
            </text>
          </g>

          <!-- ── Labels ─────────────────────────────────────────────────── -->
          <text
            v-for="el in labels"
            :key="el.id"
            :x="(el as any).x"
            :y="(el as any).y"
            :font-size="(el as any).fontSize"
            fill="rgba(209,213,219,0.85)"
            :transform="`rotate(${(el as any).rotation} ${(el as any).x} ${(el as any).y})`"
            font-family="ui-sans-serif, sans-serif"
            font-weight="600"
          >
            {{ (el as any).text }}
          </text>

          <!-- Canvas border -->
          <rect
            :width="cw"
            :height="ch"
            fill="none"
            stroke="#374151"
            stroke-width="6"
          />

          <!-- Empty state -->
          <template v-if="!parkingSlots.length">
            <text
              :x="cw / 2"
              :y="ch / 2 - 80"
              text-anchor="middle"
              font-size="200"
              fill="#374151"
              font-family="ui-sans-serif, sans-serif"
            >
              No layout yet
            </text>
            <text
              :x="cw / 2"
              :y="ch / 2 + 100"
              text-anchor="middle"
              font-size="130"
              fill="#4b5563"
              font-family="ui-sans-serif, sans-serif"
            >
              Design this lot in the admin dashboard
            </text>
          </template>
        </svg>
      </div>
    </div>

    <!-- Reset view button -->
    <button
      class="absolute top-3 right-3 bg-zinc-800/90 backdrop-blur border border-zinc-700 rounded-lg p-1.5 text-[11px] text-zinc-300 hover:text-white hover:border-zinc-500 transition-colors"
      @click="resetView"
    >
      <MaximizeIcon class="size-4" />
    </button>

    <!-- Legend -->
    <div
      class="absolute bottom-2 left-2 flex flex-col gap-1.5 bg-zinc-900/90 backdrop-blur rounded-xl p-2.5 border border-zinc-700/60"
    >
      <div
        class="flex items-center gap-2 text-[10px] font-medium text-zinc-200"
      >
        <span class="size-2.5 rounded-full bg-emerald-500 shrink-0" />Free
      </div>
      <div
        class="flex items-center gap-2 text-[10px] font-medium text-zinc-200"
      >
        <span class="size-2.5 rounded-full bg-red-500 shrink-0" />Occupied
      </div>
      <div
        class="flex items-center gap-2 text-[10px] font-medium text-zinc-200"
      >
        <span class="size-2.5 rounded-full bg-blue-500 shrink-0" />Reserved
      </div>
      <div
        class="flex items-center gap-2 text-[10px] font-medium text-zinc-200"
      >
        <span class="size-2.5 rounded-full bg-amber-400 shrink-0" />Unknown
      </div>
      <div
        v-if="highlightId"
        class="flex items-center gap-2 text-[10px] font-semibold text-yellow-400 border-t border-zinc-700 pt-1.5 mt-0.5"
      >
        <span class="size-2.5 rounded-full bg-yellow-400 shrink-0" />Nearest
        free
      </div>
    </div>
  </div>
</template>

<style scoped>
.slot-highlight-glow {
  animation: highlight-pulse 1.6s ease-in-out infinite;
}
.slot-highlight-border {
  animation: border-pulse 1.6s ease-in-out infinite;
}

@keyframes highlight-pulse {
  0%,
  100% {
    opacity: 0.7;
  }
  50% {
    opacity: 0.15;
  }
}
@keyframes border-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.35;
  }
}
</style>
