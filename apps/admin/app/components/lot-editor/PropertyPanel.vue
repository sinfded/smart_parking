<script setup lang="ts">
import type {
  LotElement,
  ParkingSlotEl,
  RoadEl,
  BoundaryEl,
  EntranceEl,
  ExitEl,
  CameraEl,
  SensorEl,
  LabelEl,
  SlotCategory,
  RoadDir,
} from '@smart-parking/types';
import {
  Lock,
  Unlock,
  Eye,
  EyeOff,
  Trash2,
  Copy,
} from 'lucide-vue-next';

const props = defineProps<{
  element: LotElement | null;
  dbSlots: Array<{ id: string; label: string; category: string }>;
}>();

const emit = defineEmits<{
  update:    [id: string, patch: Partial<LotElement>];
  remove:    [id: string];
  duplicate: [id: string];
}>();

// Typed casts
const asSlot   = computed(() => props.element?.type === 'parking_slot' ? props.element as ParkingSlotEl : null);
const asRoad   = computed(() => props.element?.type === 'road'          ? props.element as RoadEl : null);
const asMarker = computed(() => {
  if (!props.element) return null;
  if (['entrance', 'exit'].includes(props.element.type)) return props.element as EntranceEl | ExitEl;
  return null;
});
const asCamera = computed(() => props.element?.type === 'camera' ? props.element as CameraEl : null);
const asSensor = computed(() => props.element?.type === 'sensor' ? props.element as SensorEl : null);
const asLabel    = computed(() => props.element?.type === 'label'    ? props.element as LabelEl    : null);
const asBoundary = computed(() => props.element?.type === 'boundary' ? props.element as BoundaryEl : null);

function upd(patch: Partial<LotElement>) {
  if (props.element) emit('update', props.element.id, patch);
}

// ── Boundary helpers ──────────────────────────────────────────────────────────

interface BoundarySegment {
  index:  number;
  x0: number; y0: number;
  x1: number; y1: number;
  lengthCm: number;
}

const boundarySegments = computed<BoundarySegment[]>(() => {
  const b = asBoundary.value;
  if (!b) return [];
  const n = b.points.length / 2;
  const out: BoundarySegment[] = [];
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    const x0 = b.points[i * 2]!;
    const y0 = b.points[i * 2 + 1]!;
    const x1 = b.points[j * 2]!;
    const y1 = b.points[j * 2 + 1]!;
    out.push({ index: i, x0, y0, x1, y1, lengthCm: Math.round(Math.hypot(x1 - x0, y1 - y0)) });
  }
  return out;
});

function updateSegmentLength(seg: BoundarySegment, newCm: number) {
  const b = asBoundary.value;
  if (!b || newCm <= 0) return;
  const dx = seg.x1 - seg.x0;
  const dy = seg.y1 - seg.y0;
  const len = Math.hypot(dx, dy);
  if (len === 0) return;
  const j = (seg.index + 1) % (b.points.length / 2);
  const newPts = [...b.points];
  newPts[j * 2]     = seg.x0 + (dx / len) * newCm;
  newPts[j * 2 + 1] = seg.y0 + (dy / len) * newCm;
  upd({ points: newPts } as any);
}

const CATEGORIES: Array<{ value: SlotCategory; label: string }> = [
  { value: 'standard',   label: 'Standard' },
  { value: 'compact',    label: 'Compact' },
  { value: 'motorcycle', label: 'Motorcycle' },
  { value: 'pwd',        label: 'PWD / Accessible' },
  { value: 'ev',         label: 'EV Charging' },
  { value: 'truck',      label: 'Truck / Large' },
  { value: 'vip',        label: 'VIP' },
];

const ROAD_DIRS: Array<{ value: RoadDir; label: string }> = [
  { value: 'two-way', label: 'Two-way' },
  { value: 'one-way', label: 'One-way' },
];

// ── Road helpers ──────────────────────────────────────────────────────────────

interface RoadSegment {
  index:  number;
  x0: number; y0: number;
  x1: number; y1: number;
  lengthCm: number;
}

const roadSegments = computed<RoadSegment[]>(() => {
  const r = asRoad.value;
  if (!r) return [];
  const n = r.points.length / 2;
  const out: RoadSegment[] = [];
  for (let i = 0; i < n - 1; i++) {
    const x0 = r.points[i * 2]!;
    const y0 = r.points[i * 2 + 1]!;
    const x1 = r.points[(i + 1) * 2]!;
    const y1 = r.points[(i + 1) * 2 + 1]!;
    out.push({ index: i, x0, y0, x1, y1, lengthCm: Math.round(Math.hypot(x1 - x0, y1 - y0)) });
  }
  return out;
});

const roadTotalLength = computed(() =>
  roadSegments.value.reduce((sum, s) => sum + s.lengthCm, 0),
);

function updateRoadSegmentLength(seg: RoadSegment, newCm: number) {
  const r = asRoad.value;
  if (!r || newCm <= 0) return;
  const dx = seg.x1 - seg.x0;
  const dy = seg.y1 - seg.y0;
  const len = Math.hypot(dx, dy);
  if (len === 0) return;
  const newPts = [...r.points];
  newPts[(seg.index + 1) * 2]     = seg.x0 + (dx / len) * newCm;
  newPts[(seg.index + 1) * 2 + 1] = seg.y0 + (dy / len) * newCm;
  upd({ points: newPts } as any);
}
</script>

<template>
  <aside
    class="w-72 shrink-0 border-l bg-background flex flex-col overflow-hidden"
    :class="element ? '' : 'opacity-50 pointer-events-none'"
  >
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b">
      <p class="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {{ element ? element.type.replace('_', ' ') : 'Properties' }}
      </p>
      <div v-if="element" class="flex items-center gap-1">
        <Button size="icon" variant="ghost" class="size-7" :title="element.locked ? 'Unlock' : 'Lock'"
          @click="upd({ locked: !element.locked })">
          <Lock v-if="element.locked" class="size-3.5" />
          <Unlock v-else class="size-3.5" />
        </Button>
        <Button size="icon" variant="ghost" class="size-7" :title="element.visible ? 'Hide' : 'Show'"
          @click="upd({ visible: !element.visible })">
          <EyeOff v-if="!element.visible" class="size-3.5" />
          <Eye v-else class="size-3.5" />
        </Button>
        <Button size="icon" variant="ghost" class="size-7" title="Duplicate"
          @click="emit('duplicate', element.id)">
          <Copy class="size-3.5" />
        </Button>
        <Button size="icon" variant="ghost" class="size-7 text-destructive hover:text-destructive" title="Delete"
          @click="emit('remove', element.id)">
          <Trash2 class="size-3.5" />
        </Button>
      </div>
    </div>

    <!-- No selection -->
    <div v-if="!element" class="flex-1 flex items-center justify-center text-xs text-muted-foreground p-4 text-center">
      Select an element on the canvas to edit its properties.
    </div>

    <div v-else class="flex-1 overflow-y-auto">

      <!-- ── Parking slot ──────────────────────────────────────────────────── -->
      <template v-if="asSlot">
        <div class="p-4 space-y-4">
          <!-- Code -->
          <div class="space-y-1.5">
            <label class="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Slot code</label>
            <Input :model-value="asSlot.code" class="h-8 text-sm font-mono"
              @update:model-value="upd({ code: String($event) })" />
          </div>

          <!-- Category -->
          <div class="space-y-1.5">
            <label class="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Type</label>
            <select
              :value="asSlot.category"
              class="w-full h-8 rounded-md border border-input bg-background px-2 text-sm"
              @change="upd({ category: ($event.target as HTMLSelectElement).value as SlotCategory })"
            >
              <option v-for="c in CATEGORIES" :key="c.value" :value="c.value">{{ c.label }}</option>
            </select>
          </div>

          <!-- Link to DB slot -->
          <div class="space-y-1.5">
            <label class="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Linked sensor slot</label>
            <select
              :value="asSlot.slotId ?? ''"
              class="w-full h-8 rounded-md border border-input bg-background px-2 text-sm"
              @change="upd({ slotId: ($event.target as HTMLSelectElement).value || undefined })"
            >
              <option value="">— unlinked —</option>
              <option v-for="s in dbSlots" :key="s.id" :value="s.id">{{ s.label }} ({{ s.category }})</option>
            </select>
          </div>

          <Separator />

          <!-- Position -->
          <div class="space-y-1.5">
            <label class="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Position</label>
            <div class="grid grid-cols-2 gap-2">
              <div>
                <label class="text-[10px] text-muted-foreground">X</label>
                <Input type="number" :model-value="Math.round(asSlot.x)" class="h-7 text-xs"
                  @update:model-value="upd({ x: Number($event) })" />
              </div>
              <div>
                <label class="text-[10px] text-muted-foreground">Y</label>
                <Input type="number" :model-value="Math.round(asSlot.y)" class="h-7 text-xs"
                  @update:model-value="upd({ y: Number($event) })" />
              </div>
            </div>
          </div>

          <!-- Size -->
          <div class="space-y-1.5">
            <label class="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Size</label>
            <div class="grid grid-cols-2 gap-2">
              <div>
                <label class="text-[10px] text-muted-foreground">Width</label>
                <Input type="number" :model-value="Math.round(asSlot.width)" class="h-7 text-xs"
                  @update:model-value="upd({ width: Number($event) })" />
              </div>
              <div>
                <label class="text-[10px] text-muted-foreground">Height</label>
                <Input type="number" :model-value="Math.round(asSlot.height)" class="h-7 text-xs"
                  @update:model-value="upd({ height: Number($event) })" />
              </div>
            </div>
          </div>

          <!-- Rotation -->
          <div class="space-y-1.5">
            <label class="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Rotation (°)</label>
            <Input type="number" min="0" max="359" :model-value="Math.round(asSlot.rotation)" class="h-7 text-xs"
              @update:model-value="upd({ rotation: Number($event) % 360 })" />
          </div>

          <!-- Color override -->
          <div class="space-y-1.5">
            <label class="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Color override</label>
            <div class="flex gap-2 items-center">
              <input type="color" :value="asSlot.color ?? '#6366f1'" class="h-8 w-10 rounded border cursor-pointer p-0.5"
                @input="upd({ color: ($event.target as HTMLInputElement).value })" />
              <Button size="sm" variant="outline" class="h-7 text-xs flex-1"
                @click="upd({ color: undefined })">Reset</Button>
            </div>
          </div>
        </div>
      </template>

      <!-- ── Road ──────────────────────────────────────────────────────────── -->
      <template v-else-if="asRoad">
        <div class="p-4 space-y-4">
          <div class="space-y-1.5">
            <label class="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Direction</label>
            <select :value="asRoad.direction"
              class="w-full h-8 rounded-md border border-input bg-background px-2 text-sm"
              @change="upd({ direction: ($event.target as HTMLSelectElement).value as RoadDir })">
              <option v-for="d in ROAD_DIRS" :key="d.value" :value="d.value">{{ d.label }}</option>
            </select>
          </div>
          <div class="space-y-1.5">
            <label class="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Lane width</label>
            <Input type="number" min="100" max="2000" :model-value="asRoad.strokeWidth" class="h-7 text-xs"
              @update:model-value="upd({ strokeWidth: Number($event) })" />
          </div>
          <div class="space-y-1.5">
            <label class="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Color</label>
            <input type="color" :value="asRoad.color" class="h-8 w-10 rounded border cursor-pointer p-0.5"
              @input="upd({ color: ($event.target as HTMLInputElement).value })" />
          </div>

          <Separator />

          <!-- Segment lengths -->
          <div class="space-y-1.5">
            <div class="flex items-center justify-between">
              <label class="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Segment lengths (cm)</label>
              <span class="text-[10px] text-muted-foreground tabular-nums">Total: {{ roadTotalLength }} cm</span>
            </div>
            <p class="text-[10px] text-muted-foreground">Editing a segment moves its end point along the same direction.</p>
            <div class="space-y-2 mt-2">
              <div v-for="seg in roadSegments" :key="seg.index" class="flex items-center gap-2">
                <span class="text-[11px] text-muted-foreground w-14 shrink-0">Seg {{ seg.index + 1 }}</span>
                <Input
                  type="number"
                  min="1"
                  :model-value="seg.lengthCm"
                  class="h-7 text-xs"
                  @update:model-value="updateRoadSegmentLength(seg, Number($event))"
                />
                <span class="text-[10px] text-muted-foreground shrink-0">cm</span>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- ── Entrance / Exit ───────────────────────────────────────────────── -->
      <template v-else-if="asMarker">
        <div class="p-4 space-y-4">
          <div class="space-y-1.5">
            <label class="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Label</label>
            <Input :model-value="asMarker.label" class="h-8 text-sm"
              @update:model-value="upd({ label: String($event) })" />
          </div>
          <div class="space-y-1.5">
            <label class="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Rotation (°)</label>
            <Input type="number" min="0" max="359" :model-value="Math.round(asMarker.rotation)" class="h-7 text-xs"
              @update:model-value="upd({ rotation: Number($event) % 360 })" />
          </div>
        </div>
      </template>

      <!-- ── Camera ────────────────────────────────────────────────────────── -->
      <template v-else-if="asCamera">
        <div class="p-4 space-y-4">
          <div class="space-y-1.5">
            <label class="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Rotation (°)</label>
            <Input type="number" min="0" max="359" :model-value="Math.round(asCamera.rotation)" class="h-7 text-xs"
              @update:model-value="upd({ rotation: Number($event) % 360 })" />
          </div>
          <div class="space-y-1.5">
            <label class="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Field of view (°)</label>
            <Input type="number" min="10" max="180" :model-value="asCamera.fov" class="h-7 text-xs"
              @update:model-value="upd({ fov: Number($event) })" />
          </div>
          <div class="space-y-1.5">
            <label class="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Range (units)</label>
            <Input type="number" min="100" max="5000" :model-value="asCamera.range" class="h-7 text-xs"
              @update:model-value="upd({ range: Number($event) })" />
          </div>
        </div>
      </template>

      <!-- ── Sensor ─────────────────────────────────────────────────────────── -->
      <template v-else-if="asSensor">
        <div class="p-4 space-y-4">
          <div class="space-y-1.5">
            <label class="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Sensor code</label>
            <Input :model-value="asSensor.sensorCode" class="h-8 text-sm font-mono"
              @update:model-value="upd({ sensorCode: String($event) })" />
          </div>
          <div class="space-y-1.5">
            <label class="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Linked slot</label>
            <select :value="asSensor.slotId ?? ''"
              class="w-full h-8 rounded-md border border-input bg-background px-2 text-sm"
              @change="upd({ slotId: ($event.target as HTMLSelectElement).value || undefined })">
              <option value="">— unlinked —</option>
              <option v-for="s in dbSlots" :key="s.id" :value="s.id">{{ s.label }}</option>
            </select>
          </div>
        </div>
      </template>

      <!-- ── Boundary ─────────────────────────────────────────────────────── -->
      <template v-else-if="asBoundary">
        <div class="p-4 space-y-4">
          <!-- Appearance -->
          <div class="space-y-1.5">
            <label class="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Line color</label>
            <div class="flex items-center gap-2">
              <input type="color" :value="asBoundary.strokeColor" class="h-8 w-10 rounded border cursor-pointer p-0.5"
                @input="upd({ strokeColor: ($event.target as HTMLInputElement).value } as any)" />
              <span class="text-xs text-muted-foreground">{{ asBoundary.strokeColor }}</span>
            </div>
          </div>
          <div class="space-y-1.5">
            <label class="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Fill opacity</label>
            <div class="flex items-center gap-2">
              <input type="range" min="0" max="0.5" step="0.01" :value="asBoundary.fillOpacity" class="flex-1 h-2"
                @input="upd({ fillOpacity: Number(($event.target as HTMLInputElement).value) } as any)" />
              <span class="text-xs tabular-nums w-8 text-right">{{ Math.round(asBoundary.fillOpacity * 100) }}%</span>
            </div>
          </div>

          <Separator />

          <!-- Segment lengths -->
          <div class="space-y-1.5">
            <label class="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">
              Side lengths (cm)
            </label>
            <p class="text-[10px] text-muted-foreground">Changing a length moves the far endpoint along the same direction.</p>
            <div class="space-y-2 mt-2">
              <div v-for="seg in boundarySegments" :key="seg.index" class="flex items-center gap-2">
                <span class="text-[11px] text-muted-foreground w-10 shrink-0">Side {{ seg.index + 1 }}</span>
                <Input
                  type="number"
                  min="1"
                  :model-value="seg.lengthCm"
                  class="h-7 text-xs"
                  @update:model-value="updateSegmentLength(seg, Number($event))"
                />
                <span class="text-[10px] text-muted-foreground shrink-0">cm</span>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- ── Label ─────────────────────────────────────────────────────────── -->
      <template v-else-if="asLabel">
        <div class="p-4 space-y-4">
          <div class="space-y-1.5">
            <label class="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Text</label>
            <Input :model-value="asLabel.text" class="h-8 text-sm"
              @update:model-value="upd({ text: String($event) })" />
          </div>
          <div class="space-y-1.5">
            <label class="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Font size</label>
            <Input type="number" min="50" max="2000" :model-value="asLabel.fontSize" class="h-7 text-xs"
              @update:model-value="upd({ fontSize: Number($event) })" />
          </div>
          <div class="space-y-1.5">
            <label class="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Color</label>
            <input type="color" :value="asLabel.color" class="h-8 w-10 rounded border cursor-pointer p-0.5"
              @input="upd({ color: ($event.target as HTMLInputElement).value })" />
          </div>
          <div class="space-y-1.5">
            <label class="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">Rotation (°)</label>
            <Input type="number" min="0" max="359" :model-value="Math.round(asLabel.rotation)" class="h-7 text-xs"
              @update:model-value="upd({ rotation: Number($event) % 360 })" />
          </div>
        </div>
      </template>

    </div>

    <!-- Element ID (debug) -->
    <div v-if="element" class="px-4 py-2 border-t">
      <p class="text-[10px] text-muted-foreground font-mono truncate">id: {{ element.id }}</p>
    </div>
  </aside>
</template>
