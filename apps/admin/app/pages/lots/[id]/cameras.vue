<script setup lang="ts">
import { ArrowLeft, Trash2 } from "lucide-vue-next";

const client = useSupabaseClient();

const route = useRoute();
const runtimeConfig = useRuntimeConfig();
const lotId = route.params.id as string;

const { data: lot } = await useLazyAsyncData(`lot-${lotId}`, async () => {
  const { data } = await client
    .from("lots")
    .select("id, name")
    .eq("id", lotId)
    .single();
  return data;
});
const gatewayUrl = runtimeConfig.public.gatewayUrl as string;

type Camera = {
  device_id: string;
  name: string;
  index: number;
  frame_width: number;
  frame_height: number;
};
type Slot = { id: string; label: string; current_state: string };
type Region = {
  slot_id: string;
  slot_label: string;
  polygon: [number, number][];
};

const { data: cameras, status: camStatus } = await useLazyAsyncData(
  `cameras-${lotId}`,
  async () => {
    if (!gatewayUrl) return [] as Camera[];
    return await $fetch<Camera[]>(`${gatewayUrl}/cameras`);
  },
);

const { data: slots } = await useLazyAsyncData(
  `slots-cam-${lotId}`,
  async () => {
    if (!gatewayUrl) return [] as Slot[];
    return await $fetch<Slot[]>(`${gatewayUrl}/slots`);
  },
);

const selectedCameraId = ref<string | null>(null);
const frameW = ref(800);
const frameH = ref(450);

watch(
  cameras,
  (cams) => {
    if (cams?.length && !selectedCameraId.value) {
      selectedCameraId.value = cams[0]?.device_id || null;
      frameW.value = cams[0]?.frame_width ?? 800;
      frameH.value = cams[0]?.frame_height ?? 450;
    }
  },
  { immediate: true },
);

const streamUrl = computed(() =>
  selectedCameraId.value
    ? `${gatewayUrl}/cameras/${selectedCameraId.value}/stream`
    : null,
);

// ── Regions ──────────────────────────────────────────────────────────────────
const regions = ref<Region[]>([]);

async function loadRegions() {
  if (!selectedCameraId.value || !gatewayUrl) return;
  regions.value = await $fetch<Region[]>(
    `${gatewayUrl}/cameras/${selectedCameraId.value}/regions`,
  );
}

watch(selectedCameraId, () => loadRegions(), { immediate: true });

async function deleteRegion(slotId: string) {
  if (!selectedCameraId.value) return;
  await $fetch(
    `${gatewayUrl}/cameras/${selectedCameraId.value}/regions/${slotId}`,
    {
      method: "DELETE",
    },
  );
  await loadRegions();
}

// ── Drawing state ─────────────────────────────────────────────────────────────
const currentPoints = ref<[number, number][]>([]);
const mousePos = ref<[number, number] | null>(null);
const nearFirst = ref(false);

function toSVGCoords(e: MouseEvent): [number, number] {
  const rect = (e.currentTarget as SVGElement).getBoundingClientRect();
  return [
    Math.round(((e.clientX - rect.left) / rect.width) * frameW.value),
    Math.round(((e.clientY - rect.top) / rect.height) * frameH.value),
  ];
}

function onMouseMove(e: MouseEvent) {
  mousePos.value = toSVGCoords(e);
  if (currentPoints.value.length < 3) {
    nearFirst.value = false;
    return;
  }
  const [fx, fy] = currentPoints.value[0] as [number, number];
  const rect = (e.currentTarget as SVGElement).getBoundingClientRect();
  const dx = (fx / frameW.value) * rect.width - (e.clientX - rect.left);
  const dy = (fy / frameH.value) * rect.height - (e.clientY - rect.top);
  nearFirst.value = Math.hypot(dx, dy) < 14;
}

function onSVGClick(e: MouseEvent) {
  if (nearFirst.value && currentPoints.value.length >= 3) {
    pendingPolygon.value = [...currentPoints.value];
    currentPoints.value = [];
    nearFirst.value = false;
    assignSlotId.value = assignableSlots.value[0]?.id ?? "";
    showAssign.value = true;
    return;
  }
  currentPoints.value.push(toSVGCoords(e));
}

function cancelDraw() {
  currentPoints.value = [];
  nearFirst.value = false;
}

// ── Assign dialog ─────────────────────────────────────────────────────────────
const showAssign = ref(false);
const pendingPolygon = ref<[number, number][]>([]);
const assignSlotId = ref("");

const assignableSlots = computed(() =>
  (slots.value ?? []).filter(
    (s) => !regions.value.some((r) => r.slot_id === s.id),
  ),
);

async function saveRegion() {
  if (!assignSlotId.value || !selectedCameraId.value) return;
  await $fetch(`${gatewayUrl}/cameras/${selectedCameraId.value}/regions`, {
    method: "POST",
    body: { slot_id: assignSlotId.value, polygon: pendingPolygon.value },
  });
  showAssign.value = false;
  pendingPolygon.value = [];
  await loadRegions();
}

const lastPoint = computed(
  (): [number, number] => currentPoints.value.at(-1) ?? [0, 0],
);

// ── Helpers ───────────────────────────────────────────────────────────────────
function polygonCenter(pts: [number, number][]): [number, number] {
  return [
    pts.reduce((s, [x]) => s + x, 0) / pts.length,
    pts.reduce((s, [, y]) => s + y, 0) / pts.length,
  ];
}

function toSVGPoints(pts: [number, number][]) {
  return pts.map(([x, y]) => `${x},${y}`).join(" ");
}

const slotStateMap = computed(() =>
  Object.fromEntries((slots.value ?? []).map((s) => [s.id, s.current_state])),
);

function regionColors(slotId: string) {
  const state = slotStateMap.value[slotId];
  if (state === "free")
    return { fill: "rgba(34,197,94,0.18)", stroke: "#22c55e", textStroke: "#14532d" };
  if (state === "occupied")
    return { fill: "rgba(239,68,68,0.18)", stroke: "#ef4444", textStroke: "#7f1d1d" };
  return { fill: "rgba(59,130,246,0.18)", stroke: "#3b82f6", textStroke: "#1e3a8a" };
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center gap-2">
      <Button variant="ghost" size="icon" class="size-7" as-child>
        <NuxtLink to="/lots">
          <ArrowLeft class="size-4" />
        </NuxtLink>
      </Button>
      <Skeleton v-if="!lot" class="h-6 w-36" />
      <h2 v-else class="text-base font-semibold">{{ lot.name }}</h2>
    </div>

    <LotNav />

    <Alert v-if="!gatewayUrl" variant="destructive">
      <AlertTitle>Gateway not configured</AlertTitle>
      <AlertDescription>
        Set <code class="font-mono text-xs">NUXT_PUBLIC_GATEWAY_URL</code> to
        the Pi address, e.g.
        <code class="font-mono text-xs">http://192.168.1.10:8000</code>.
      </AlertDescription>
    </Alert>

    <template v-else>
      <Skeleton v-if="camStatus === 'pending'" class="h-9 w-56" />

      <Alert v-else-if="!cameras?.length" variant="default">
        <AlertDescription>
          No cameras found. Make sure the gateway is running with
          <code class="font-mono text-xs">--lot {{ lotId }}</code> and cameras
          are registered in the database.
        </AlertDescription>
      </Alert>

      <template v-else>
        <!-- Camera tabs -->
        <Tabs
          :model-value="selectedCameraId ?? undefined"
          @update:model-value="selectedCameraId = $event as string"
        >
          <TabsList>
            <TabsTrigger
              v-for="cam in cameras"
              :key="cam.device_id"
              :value="cam.device_id"
            >
              {{ cam.name }}
            </TabsTrigger>
          </TabsList>
        </Tabs>

        <!-- Feed + sidebar -->
        <div class="grid gap-4 lg:grid-cols-[1fr_260px]">
          <!-- Camera feed with SVG overlay -->
          <Card class="overflow-hidden p-0 gap-0">
            <div class="relative bg-black">
              <img
                v-if="streamUrl"
                :src="streamUrl"
                class="block w-full"
                style="aspect-ratio: 16/9; object-fit: contain"
                draggable="false"
              />
              <div v-else class="flex aspect-video items-center justify-center">
                <p class="text-muted-foreground text-sm">No stream</p>
              </div>

              <svg
                v-if="streamUrl"
                :viewBox="`0 0 ${frameW} ${frameH}`"
                preserveAspectRatio="none"
                class="absolute inset-0 h-full w-full select-none"
                :class="
                  currentPoints.length > 0 || nearFirst
                    ? 'cursor-crosshair'
                    : 'cursor-crosshair'
                "
                @click="onSVGClick"
                @mousemove="onMouseMove"
                @mouseleave="
                  mousePos = null;
                  nearFirst = false;
                "
              >
                <!-- Saved regions -->
                <g v-for="region in regions" :key="region.slot_id">
                  <polygon
                    :points="toSVGPoints(region.polygon)"
                    :fill="regionColors(region.slot_id).fill"
                    :stroke="regionColors(region.slot_id).stroke"
                    stroke-width="2.5"
                  />
                  <text
                    :x="polygonCenter(region.polygon)[0]"
                    :y="polygonCenter(region.polygon)[1]"
                    text-anchor="middle"
                    dominant-baseline="middle"
                    fill="white"
                    font-size="24"
                    font-weight="700"
                    paint-order="stroke"
                    :stroke="regionColors(region.slot_id).textStroke"
                    stroke-width="6"
                  >
                    {{ region.slot_label }}
                  </text>
                </g>

                <!-- Polygon in progress -->
                <polygon
                  v-if="currentPoints.length >= 2"
                  :points="
                    toSVGPoints([
                      ...currentPoints,
                      ...(mousePos ? [mousePos] : []),
                    ])
                  "
                  fill="rgba(234,179,8,0.15)"
                  stroke="#eab308"
                  stroke-width="2"
                  stroke-dasharray="8,4"
                />
                <!-- Ghost edge from last point to cursor -->
                <line
                  v-if="currentPoints.length >= 1 && mousePos"
                  :x1="lastPoint[0]"
                  :y1="lastPoint[1]"
                  :x2="mousePos[0]"
                  :y2="mousePos[1]"
                  stroke="#eab308"
                  stroke-width="1.5"
                  stroke-dasharray="5,3"
                  opacity="0.6"
                />
                <!-- Vertex dots -->
                <circle
                  v-for="([x, y], i) in currentPoints"
                  :key="i"
                  :cx="x"
                  :cy="y"
                  r="8"
                  :fill="
                    i === 0 && nearFirst
                      ? '#22c55e'
                      : i === 0
                        ? '#f97316'
                        : '#eab308'
                  "
                  stroke="white"
                  stroke-width="2.5"
                />
              </svg>
            </div>

            <!-- Hint bar -->
            <div class="flex items-center justify-between border-t px-4 py-2">
              <p class="text-muted-foreground text-xs">
                <template v-if="currentPoints.length === 0">
                  Click on the feed to start drawing a slot region.
                </template>
                <template v-else>
                  <span class="text-foreground font-medium">{{
                    currentPoints.length
                  }}</span>
                  {{ currentPoints.length === 1 ? "point" : "points" }} — click
                  the
                  <span class="font-medium text-orange-500">orange dot</span>
                  to close the polygon.
                </template>
              </p>
              <Button
                v-if="currentPoints.length > 0"
                variant="ghost"
                size="sm"
                class="h-6 text-xs"
                @click="cancelDraw"
              >
                Cancel
              </Button>
            </div>
          </Card>

          <!-- Region list -->
          <div class="space-y-3">
            <p
              class="text-muted-foreground text-xs font-medium uppercase tracking-wide"
            >
              Regions ({{ regions.length }})
            </p>
            <div v-if="regions.length" class="space-y-2">
              <Card
                v-for="region in regions"
                :key="region.slot_id"
                class="px-3 py-2.5"
              >
                <div class="flex items-center justify-between">
                  <span class="text-sm font-medium"
                    >Slot {{ region.slot_label }}</span
                  >
                  <Button
                    variant="ghost"
                    size="icon"
                    class="text-muted-foreground hover:text-destructive size-7"
                    @click="deleteRegion(region.slot_id)"
                  >
                    <Trash2 class="size-3.5" />
                  </Button>
                </div>
                <p class="text-muted-foreground text-xs">
                  {{ region.polygon.length }} vertices
                </p>
              </Card>
            </div>
            <p v-else class="text-muted-foreground text-xs">
              No regions yet. Draw a polygon on the feed.
            </p>
          </div>
        </div>
      </template>
    </template>

    <!-- Slot assignment dialog -->
    <Dialog v-model:open="showAssign">
      <DialogContent class="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Assign slot to region</DialogTitle>
          <DialogDescription>
            Which parking slot does this polygon cover?
          </DialogDescription>
        </DialogHeader>
        <div class="space-y-2">
          <Label>Slot</Label>
          <Select v-model="assignSlotId">
            <SelectTrigger class="w-full">
              <SelectValue placeholder="Select a slot" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem
                v-for="slot in assignableSlots"
                :key="slot.id"
                :value="slot.id"
              >
                {{ slot.label }}
              </SelectItem>
            </SelectContent>
          </Select>
          <p
            v-if="!assignableSlots.length"
            class="text-muted-foreground text-xs"
          >
            All slots already have regions on this camera.
          </p>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            @click="
              showAssign = false;
              pendingPolygon = [];
            "
          >
            Cancel
          </Button>
          <Button :disabled="!assignSlotId" @click="saveRegion">
            Save region
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
