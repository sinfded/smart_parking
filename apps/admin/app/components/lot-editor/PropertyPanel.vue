<script setup lang="ts">
import type {
  LotElement,
  ParkingSlotEl,
  RoadEl,
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
const asLabel  = computed(() => props.element?.type === 'label'  ? props.element as LabelEl : null);

function upd(patch: Partial<LotElement>) {
  if (props.element) emit('update', props.element.id, patch);
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
