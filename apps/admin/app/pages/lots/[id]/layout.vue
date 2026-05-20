<script setup lang="ts">
import { ArrowLeft, Save, AlertCircle } from "lucide-vue-next";
import type {
  LotElement,
  ParkingSlotEl,
  CameraEl,
  BoundaryEl,
} from "@smart-parking/types";
import { CANVAS_SIZE, SLOT_COLORS } from "@smart-parking/types";
import { useLotEditor } from "~/composables/useLotEditor";

// ── Setup ─────────────────────────────────────────────────────────────────────

const route = useRoute();
const client = useSupabaseClient<any>();
const lotId = route.params.id as string;

const editor = useLotEditor(lotId, client);
const {
  layout,
  elements,
  slots,
  roads,
  boundaries,
  markers,
  activeTool,
  selectedIds,
  selectedElement,
  setTool,
  selectElement,
  selectByRect,
  clearSelection,
  selectAll,
  addElement,
  updateElement,
  updateElements,
  removeElement,
  removeSelected,
  copySelected,
  paste,
  duplicate,
  newSlot,
  newEntrance,
  newExit,
  newCamera,
  newSensor,
  newRoad,
  newBoundary,
  newLabel,
  updateBackground,
  updateGrid,
  snapVal,
  snapPos,
  canUndo,
  canRedo,
  undo,
  redo,
  save,
  saveStatus,
  loadFromDb,
  exportJSON,
  importJSON,
} = editor;

// Lot meta
const lotName = ref("");

onMounted(async () => {
  await loadFromDb();
  const { data } = await client
    .from("lots")
    .select("name")
    .eq("id", lotId)
    .single();
  if (data) lotName.value = data.name;
  nextTick(fitToView);
});

useHead(() => ({
  title: lotName.value ? `Layout — ${lotName.value}` : "Layout",
}));

// ── DB slots (for property panel linking) ─────────────────────────────────────
const dbSlots = ref<Array<{ id: string; label: string; category: string }>>([]);
onMounted(async () => {
  const { data } = await client
    .from("slots")
    .select("id, label, category")
    .eq("lot_id", lotId)
    .is("deleted_at", null)
    .order("label");
  dbSlots.value = data ?? [];
});

// ── Konva refs ────────────────────────────────────────────────────────────────

const containerRef = useTemplateRef<HTMLDivElement>("container");
const stageRef = useTemplateRef<any>("stage");
const transformerRef = useTemplateRef<any>("transformer");

const stageW = ref(800);
const stageH = ref(600);
const zoom = ref(1);
const cursorPos = ref({ x: 0, y: 0 });

function getStage() {
  return stageRef.value?.getStage?.() ?? stageRef.value;
}

// ── Transformer ───────────────────────────────────────────────────────────────

watchEffect(() => {
  const tr = transformerRef.value?.getNode?.();
  if (!tr) return;
  const stage = getStage();
  if (!stage) return;
  const nodes = [...selectedIds.value]
    .map((id) => stage.findOne(`#${id}`))
    .filter((n: any): n is any => !!n);
  tr.nodes(nodes);
});

function onTransformEnd(e: any) {
  const updates: Array<{ id: string; patch: Partial<LotElement> }> = [];
  const tr = transformerRef.value?.getNode?.();
  if (!tr) return;
  for (const node of tr.nodes()) {
    const id = node.id();
    const el = elements.value.find((el) => el.id === id);
    if (!el) continue;
    const patch: Record<string, any> = { x: node.x(), y: node.y() };
    if ("width" in el) {
      patch.width = Math.max(50, node.width() * node.scaleX());
      patch.height = Math.max(50, node.height() * node.scaleY());
      node.scaleX(1);
      node.scaleY(1);
    }
    patch.rotation = node.rotation();
    updates.push({ id, patch: patch as Partial<LotElement> });
  }
  if (updates.length) updateElements(updates);
}

// ── Stage resize ──────────────────────────────────────────────────────────────

onMounted(() => {
  if (!containerRef.value) return;
  const ro = new ResizeObserver(([entry]) => {
    if (!entry) return;
    stageW.value = entry.contentRect.width;
    stageH.value = entry.contentRect.height;
    nextTick(fitToView);
  });
  ro.observe(containerRef.value);
  onUnmounted(() => ro.disconnect());
});

// ── Zoom / pan ────────────────────────────────────────────────────────────────

function onWheel(e: any) {
  e.evt.preventDefault();
  const stage = getStage();
  const old = stage.scaleX();
  const by = 1.1;
  const ptr = stage.getPointerPosition();
  const nxt = Math.max(
    0.05,
    Math.min(8, e.evt.deltaY < 0 ? old * by : old / by),
  );
  stage.scale({ x: nxt, y: nxt });
  stage.position({
    x: ptr.x - (ptr.x - stage.x()) * (nxt / old),
    y: ptr.y - (ptr.y - stage.y()) * (nxt / old),
  });
  zoom.value = nxt;
}

function fitToView() {
  const stage = getStage();
  if (!stage) return;
  const pad = 60;
  const cw = layout.value.canvas.width;
  const ch = layout.value.canvas.height;
  const sc = Math.min(
    (stageW.value - pad * 2) / cw,
    (stageH.value - pad * 2) / ch,
    1,
  );
  stage.scale({ x: sc, y: sc });
  stage.position({
    x: (stageW.value - cw * sc) / 2,
    y: (stageH.value - ch * sc) / 2,
  });
  zoom.value = sc;
}

// ── Grid lines ────────────────────────────────────────────────────────────────

const gridLines = computed(() => {
  if (!layout.value.grid.visible) return [];
  const g = layout.value.grid.size;
  const cw = layout.value.canvas.width;
  const ch = layout.value.canvas.height;
  // Keep grid lines at ~1px screen width regardless of zoom level.
  const sw = 1 / (zoom.value || 1);
  const lines: any[] = [];
  for (let x = 0; x <= cw; x += g)
    lines.push({
      points: [x, 0, x, ch],
      stroke: "#e5e7eb",
      strokeWidth: sw,
      listening: false,
    });
  for (let y = 0; y <= ch; y += g)
    lines.push({
      points: [0, y, cw, y],
      stroke: "#e5e7eb",
      strokeWidth: sw,
      listening: false,
    });
  return lines;
});

// ── Background image ──────────────────────────────────────────────────────────

const bgImageEl = ref<HTMLImageElement | null>(null);
const bgFileRef = useTemplateRef<HTMLInputElement>("bgFile");

watchEffect(() => {
  const url = layout.value.background.url;
  if (!url) {
    bgImageEl.value = null;
    return;
  }
  const img = new Image();
  img.onload = () => {
    bgImageEl.value = img;
  };
  img.onerror = () => {
    bgImageEl.value = null;
  };
  img.src = url;
});

async function handleBgUpload(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0];
  if (!file) return;
  // Use object URL for preview; production should upload to Supabase Storage
  const url = URL.createObjectURL(file);
  updateBackground({
    url,
    width: layout.value.canvas.width,
    height: layout.value.canvas.height,
  });
}

// ── Drawing state ─────────────────────────────────────────────────────────────

// Slot draw preview
const slotDraw = ref<{ x1: number; y1: number; x2: number; y2: number } | null>(
  null,
);
let slotDrawing = false;

// Road draw state
const roadPoints = ref<number[]>([]);
const roadCursor = ref({ x: 0, y: 0 });
const isDrawingRoad = computed(
  () => roadPoints.value.length > 0 && activeTool.value === "road",
);

// Boundary draw state
const boundaryPoints = ref<number[]>([]);
const boundaryCursor = ref({ x: 0, y: 0 });
const isDrawingBoundary = computed(
  () => boundaryPoints.value.length > 0 && activeTool.value === "boundary",
);

// Rubber-band selection
const selRect = ref<{ x1: number; y1: number; x2: number; y2: number } | null>(
  null,
);
let isRubberBanding = false;

// ── Canvas cursor ─────────────────────────────────────────────────────────────

const canvasCursor = computed(() => {
  if (activeTool.value === "delete") return "cell";
  if (activeTool.value === "select" && !isRubberBanding) return "default";
  if (
    [
      "slot",
      "road",
      "boundary",
      "entrance",
      "exit",
      "camera",
      "sensor",
      "label",
    ].includes(activeTool.value)
  )
    return "crosshair";
  return "default";
});

// ── Pointer helpers ───────────────────────────────────────────────────────────

function getPos() {
  const stage = getStage();
  return stage?.getRelativePointerPosition() ?? { x: 0, y: 0 };
}

function snappedPos() {
  return snapPos(getPos());
}

// ── Stage events ──────────────────────────────────────────────────────────────

function onStageMouseDown(e: any) {
  if (e.evt.button !== 0) return; // left button only
  const target = e.target;
  const isBackground = target?.attrs?.name === "bg" || target === getStage();
  const pos = getPos();
  const sp = snapPos(pos);

  switch (activeTool.value) {
    case "select":
      if (isBackground) {
        clearSelection();
        isRubberBanding = true;
        selRect.value = { x1: pos.x, y1: pos.y, x2: pos.x, y2: pos.y };
      }
      break;

    case "slot":
      slotDrawing = true;
      slotDraw.value = { x1: sp.x, y1: sp.y, x2: sp.x, y2: sp.y };
      break;

    case "entrance":
      addElement(newEntrance(sp.x, sp.y));
      break;
    case "exit":
      addElement(newExit(sp.x, sp.y));
      break;
    case "camera":
      addElement(newCamera(sp.x, sp.y));
      break;
    case "sensor":
      addElement(newSensor(sp.x, sp.y));
      break;
    case "label":
      addElement(newLabel(sp.x, sp.y));
      break;

    case "delete":
      if (!isBackground && target?.attrs?.name !== "bg") {
        const elId = target?.parent?.id?.() ?? target?.id?.();
        if (elId) removeElement(elId);
      }
      break;
  }
}

function onStageMouseMove(e: any) {
  const pos = getPos();
  const sp = snapPos(pos);
  cursorPos.value = { x: Math.round(pos.x), y: Math.round(pos.y) };

  if (slotDrawing && slotDraw.value) {
    slotDraw.value = { ...slotDraw.value, x2: sp.x, y2: sp.y };
  }

  if (isRubberBanding && selRect.value) {
    selRect.value = { ...selRect.value, x2: pos.x, y2: pos.y };
  }

  if (isDrawingRoad.value && roadPoints.value.length >= 2) {
    roadCursor.value = sp;
    roadPoints.value = [...roadPoints.value.slice(0, -2), sp.x, sp.y];
  }

  if (isDrawingBoundary.value && boundaryPoints.value.length >= 2) {
    boundaryCursor.value = sp;
    boundaryPoints.value = [...boundaryPoints.value.slice(0, -2), sp.x, sp.y];
  }
}

function onStageMouseUp() {
  if (slotDrawing && slotDraw.value) {
    const { x1, y1, x2, y2 } = slotDraw.value;
    const w = Math.abs(x2 - x1);
    const h = Math.abs(y2 - y1);
    if (w > 50 && h > 50) {
      addElement(newSlot(Math.min(x1, x2), Math.min(y1, y2), w, h));
    }
    slotDraw.value = null;
    slotDrawing = false;
  }

  if (isRubberBanding && selRect.value) {
    const { x1, y1, x2, y2 } = selRect.value;
    if (Math.abs(x2 - x1) > 5 || Math.abs(y2 - y1) > 5) {
      selectByRect(x1, y1, x2, y2);
    }
    selRect.value = null;
    isRubberBanding = false;
  }
}

function onStageDblClick() {
  if (activeTool.value === "road") {
    const pts = roadPoints.value.slice(0, -4);
    if (pts.length >= 4) addElement(newRoad(pts));
    roadPoints.value = [];
  }
  if (activeTool.value === "boundary") {
    const pts = boundaryPoints.value.slice(0, -4);
    if (pts.length >= 6) addElement(newBoundary(pts));
    boundaryPoints.value = [];
  }
}

// Click on an element (bubbles to stage, check target)
function onStageClick(e: any) {
  const target = e.target;
  const isBackground = target?.attrs?.name === "bg" || target === getStage();

  if (activeTool.value === "road") {
    const sp = snapPos(getPos());
    if (!roadPoints.value.length) {
      roadPoints.value = [sp.x, sp.y, sp.x, sp.y];
    } else {
      roadPoints.value = [
        ...roadPoints.value.slice(0, -2),
        sp.x,
        sp.y,
        sp.x,
        sp.y,
      ];
    }
    return;
  }

  if (activeTool.value === "boundary") {
    const sp = snapPos(getPos());
    if (!boundaryPoints.value.length) {
      boundaryPoints.value = [sp.x, sp.y, sp.x, sp.y];
    } else {
      boundaryPoints.value = [
        ...boundaryPoints.value.slice(0, -2),
        sp.x,
        sp.y,
        sp.x,
        sp.y,
      ];
    }
    return;
  }

  if (isBackground && activeTool.value === "select") clearSelection();
}

// ── Element drag ──────────────────────────────────────────────────────────────

function onElementDragMove(elId: string, e: any) {
  const node = e.target;
  node.x(Math.max(0, Math.min(layout.value.canvas.width, snapVal(node.x()))));
  node.y(Math.max(0, Math.min(layout.value.canvas.height, snapVal(node.y()))));
}

function onElementDragEnd(elId: string, e: any) {
  const el = elements.value.find((el) => el.id === elId);
  if (el && (el.type === "road" || el.type === "boundary")) {
    const dx = e.target.x();
    const dy = e.target.y();
    if (dx === 0 && dy === 0) return;
    const pts = (el as any).points as number[];
    const newPts = pts.map((v: number, i: number) =>
      i % 2 === 0 ? snapVal(v + dx) : snapVal(v + dy),
    );
    e.target.x(0);
    e.target.y(0);
    updateElement(elId, { points: newPts } as any);
  } else {
    updateElement(elId, { x: e.target.x(), y: e.target.y() } as any);
  }
}

// ── Click on element ──────────────────────────────────────────────────────────

function onElementClick(elId: string, e: any) {
  e.cancelBubble = true;
  if (activeTool.value === "delete") {
    removeElement(elId);
    return;
  }
  if (activeTool.value === "select") {
    selectElement(elId, e.evt?.shiftKey ?? false);
  }
}

// ── Keyboard shortcuts ────────────────────────────────────────────────────────

function handleKey(e: KeyboardEvent) {
  if (
    ["INPUT", "TEXTAREA", "SELECT"].includes((e.target as HTMLElement)?.tagName)
  )
    return;
  const ctrl = e.ctrlKey || e.metaKey;

  if (ctrl && e.key === "z" && !e.shiftKey) {
    e.preventDefault();
    undo();
  }
  if (ctrl && (e.key === "y" || (e.key === "z" && e.shiftKey))) {
    e.preventDefault();
    redo();
  }
  if (ctrl && e.key === "c") {
    e.preventDefault();
    copySelected();
  }
  if (ctrl && e.key === "v") {
    e.preventDefault();
    paste();
  }
  if (ctrl && e.key === "a") {
    e.preventDefault();
    selectAll();
  }
  if (ctrl && e.key === "d") {
    e.preventDefault();
    if (selectedElement.value) duplicate(selectedElement.value.id);
  }
  if (ctrl && e.key === "s") {
    e.preventDefault();
    save();
  }

  if (!ctrl) {
    if (e.key === "Delete" || e.key === "Backspace") removeSelected();
    if (e.key === "Enter" && activeTool.value === "road") {
      const pts = roadPoints.value.slice(0, -2);
      if (pts.length >= 4) addElement(newRoad(pts));
      roadPoints.value = [];
    }
    if (e.key === "Enter" && activeTool.value === "boundary") {
      const pts = boundaryPoints.value.slice(0, -2);
      if (pts.length >= 6) addElement(newBoundary(pts));
      boundaryPoints.value = [];
    }
    if (e.key === "Escape") {
      clearSelection();
      setTool("select");
      roadPoints.value = [];
      boundaryPoints.value = [];
    }
    if (e.key === "s") setTool("select");
    if (e.key === "p") setTool("slot");
    if (e.key === "r") setTool("road");
    if (e.key === "e") setTool("entrance");
    if (e.key === "x") setTool("exit");
    if (e.key === "c") setTool("camera");
    if (e.key === "u") setTool("sensor");
    if (e.key === "b") setTool("boundary");
    if (e.key === "l") setTool("label");
    if (e.key === "d") setTool("delete");
    if (e.key === "g") updateGrid({ visible: !layout.value.grid.visible });
    if (e.key === "0") fitToView();
    if (e.key === "=" || e.key === "+") zoomBy(1.2);
    if (e.key === "-") zoomBy(1 / 1.2);
  }
}

function zoomBy(factor: number) {
  const stage = getStage();
  if (!stage) return;
  const old = stage.scaleX();
  const nxt = Math.max(0.05, Math.min(8, old * factor));
  const cx = stageW.value / 2;
  const cy = stageH.value / 2;
  stage.scale({ x: nxt, y: nxt });
  stage.position({
    x: cx - (cx - stage.x()) * (nxt / old),
    y: cy - (cy - stage.y()) * (nxt / old),
  });
  zoom.value = nxt;
}

onMounted(() => window.addEventListener("keydown", handleKey));
onUnmounted(() => window.removeEventListener("keydown", handleKey));

// ── IO helpers ────────────────────────────────────────────────────────────────

const importFileRef = useTemplateRef<HTMLInputElement>("importFile");

function handleExportJSON() {
  const blob = new Blob([exportJSON()], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `lot-layout-${lotId}.json`;
  a.click();
}

function handleImportTrigger() {
  importFileRef.value?.click();
}

async function handleImportJSON(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0];
  if (!file) return;
  const text = await file.text();
  const ok = importJSON(text);
  if (!ok) alert("Invalid layout JSON.");
  (e.target as HTMLInputElement).value = "";
}

// ── Konva config helpers ──────────────────────────────────────────────────────

const SLOT_FILL_UNKNOWN = "#6366f1";

function slotFill(slot: ParkingSlotEl): string {
  return slot.color ?? SLOT_COLORS[slot.category] ?? SLOT_FILL_UNKNOWN;
}

function isSelected(id: string) {
  return selectedIds.value.has(id);
}

function elementDraggable(el: LotElement) {
  return !el.locked && activeTool.value === "select";
}

// Camera FOV wedge points (as a closed path polygon for v-line)
function cameraFovPoints(cam: CameraEl): number[] {
  const half = (cam.fov / 2) * (Math.PI / 180);
  const rotRad = cam.rotation * (Math.PI / 180);
  const r = cam.range;
  const lx = cam.x + Math.cos(rotRad - half) * r;
  const ly = cam.y + Math.sin(rotRad - half) * r;
  const rx = cam.x + Math.cos(rotRad + half) * r;
  const ry = cam.y + Math.sin(rotRad + half) * r;
  return [cam.x, cam.y, lx, ly, rx, ry, cam.x, cam.y];
}

// Slot preview rect
const slotPreviewConfig = computed(() => {
  if (!slotDraw.value) return null;
  const { x1, y1, x2, y2 } = slotDraw.value;
  return {
    x: Math.min(x1, x2),
    y: Math.min(y1, y2),
    width: Math.abs(x2 - x1),
    height: Math.abs(y2 - y1),
    fill: "rgba(99,102,241,0.1)",
    stroke: "#6366f1",
    strokeWidth: 2,
    dash: [40, 20],
    listening: false,
  };
});

// Rubber band rect
const selRectConfig = computed(() => {
  if (!selRect.value) return null;
  const { x1, y1, x2, y2 } = selRect.value;
  return {
    x: Math.min(x1, x2),
    y: Math.min(y1, y2),
    width: Math.abs(x2 - x1),
    height: Math.abs(y2 - y1),
    fill: "rgba(37,99,235,0.06)",
    stroke: "#2563eb",
    strokeWidth: 1,
    dash: [20, 10],
    listening: false,
  };
});

// Boundary preview
const boundaryPreviewConfig = computed(() => {
  if (!isDrawingBoundary.value || boundaryPoints.value.length < 2) return null;
  return {
    points: boundaryPoints.value,
    closed: true,
    fill: "rgba(249,115,22,0.08)",
    stroke: "#f97316",
    strokeWidth: 2 / (zoom.value || 1),
    dash: [40, 20],
    lineCap: "round" as const,
    lineJoin: "round" as const,
    listening: false,
    opacity: 0.85,
  };
});

// Road preview — returns [curb, asphalt, center] configs
const roadPreviewConfigs = computed(() => {
  if (!isDrawingRoad.value || roadPoints.value.length < 2) return null;
  const pts = roadPoints.value;
  const sw = layout.value.grid.size * 3;
  const base = {
    points: pts,
    lineCap: "butt" as const,
    lineJoin: "miter" as const,
    listening: false,
    opacity: 0.7,
  };
  return [
    { ...base, stroke: "#6b7280", strokeWidth: sw * 1.14 },
    {
      ...base,
      stroke: "#374151",
      strokeWidth: sw,
      dash: [sw * 0.7, sw * 0.35],
    },
    { ...base, stroke: "#fbbf24", strokeWidth: sw * 0.08 },
  ];
});

// Status label
const saveLabel = computed(() => {
  if (saveStatus.value === "saving") return "Saving…";
  if (saveStatus.value === "saved") return "Saved";
  if (saveStatus.value === "error") return "Save failed";
  return null;
});
</script>

<template>
  <div class="flex flex-col h-screen overflow-hidden">
    <!-- Header -->
    <div class="shrink-0 flex flex-col gap-4 pb-4 space-y-2">
      <!-- Top bar -->
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <Button variant="ghost" size="icon" class="size-7" as-child>
            <NuxtLink to="/lots">
              <ArrowLeft class="size-4" />
            </NuxtLink>
          </Button>
          <Skeleton v-if="!lotName" class="h-6 w-36" />
          <h2 v-else class="text-base font-semibold">{{ lotName }}</h2>
        </div>

        <div class="flex items-center gap-2">
          <span
            v-if="saveLabel"
            class="text-xs text-muted-foreground flex items-center gap-1.5"
          >
            <AlertCircle
              v-if="saveStatus === 'error'"
              class="size-3 text-destructive"
            />
            {{ saveLabel }}
          </span>
          <Button size="sm" variant="outline" @click="save">
            <Save class="mr-1.5 size-3.5" /> Save now
          </Button>
        </div>
      </div>

      <LotNav />
    </div>

    <!-- Editor body -->
    <div class="flex flex-col flex-1 min-h-0 overflow-hidden">
      <!-- Tool palette -->
      <LotEditorToolPalette
        :active-tool="activeTool"
        :grid-visible="layout.grid.visible"
        :snap-enabled="layout.grid.snap"
        :can-undo="canUndo"
        :can-redo="canRedo"
        @set-tool="setTool"
        @undo="undo"
        @redo="redo"
        @toggle-grid="updateGrid({ visible: !layout.grid.visible })"
        @toggle-snap="updateGrid({ snap: !layout.grid.snap })"
        @fit-to-view="fitToView"
        @export-j-s-o-n="handleExportJSON"
        @import-j-s-o-n="handleImportTrigger"
        @upload-bg="bgFileRef?.click()"
      />

      <div class="flex flex-1 min-h-0 overflow-hidden">
        <!-- Canvas -->
        <div
          ref="container"
          class="flex-1 overflow-hidden bg-zinc-100 dark:bg-zinc-900 relative"
          :style="{ cursor: canvasCursor }"
        >
          <client-only>
            <v-stage
              ref="stage"
              :config="{
                width: stageW,
                height: stageH,
                draggable: activeTool === 'select' && !isRubberBanding,
              }"
              @wheel="onWheel"
              @mousedown="onStageMouseDown"
              @mousemove="onStageMouseMove"
              @mouseup="onStageMouseUp"
              @dblclick="onStageDblClick"
              @click="onStageClick"
            >
              <!-- ── Background image ─────────────────────────────────────── -->
              <v-layer :config="{ listening: false }">
                <v-rect
                  :config="{
                    name: 'bg',
                    width: layout.canvas.width,
                    height: layout.canvas.height,
                    fill: '#ffffff',
                    listening: false,
                  }"
                />
                <v-image
                  v-if="bgImageEl"
                  :config="{
                    image: bgImageEl,
                    x: layout.background.x,
                    y: layout.background.y,
                    width: layout.background.width,
                    height: layout.background.height,
                    opacity: layout.background.opacity,
                    listening: false,
                  }"
                />
              </v-layer>

              <!-- ── Grid ────────────────────────────────────────────────── -->
              <v-layer :config="{ listening: false }">
                <v-line v-for="(ln, i) in gridLines" :key="i" :config="ln" />
                <!-- Canvas border -->
                <v-rect
                  :config="{
                    width: layout.canvas.width,
                    height: layout.canvas.height,
                    fill: 'transparent',
                    stroke: '#d1d5db',
                    strokeWidth: 2,
                    listening: false,
                  }"
                />
              </v-layer>

              <!-- ── Property boundaries ────────────────────────────────── -->
              <v-layer>
                <v-group
                  v-for="b in boundaries"
                  :key="b.id"
                  :config="{
                    id: b.id,
                    opacity: b.visible ? 1 : 0.3,
                    draggable: elementDraggable(b),
                  }"
                  @click="onElementClick(b.id, $event)"
                  @dragend="onElementDragEnd(b.id, $event)"
                >
                  <!-- Invisible wide hit area so the boundary is clickable/deletable -->
                  <v-line
                    :config="{
                      points: b.points,
                      closed: true,
                      fill: 'rgba(0,0,0,0)',
                      stroke: 'transparent',
                      strokeWidth: 80 / (zoom || 1),
                      hitStrokeWidth: 80 / (zoom || 1),
                    }"
                  />
                  <!-- Fill -->
                  <v-line
                    :config="{
                      points: b.points,
                      closed: true,
                      fill: `rgba(249,115,22,${b.fillOpacity})`,
                      stroke: 'transparent',
                      strokeWidth: 0,
                      listening: false,
                    }"
                  />
                  <!-- Dashed border -->
                  <v-line
                    :config="{
                      points: b.points,
                      closed: true,
                      fill: 'transparent',
                      stroke: isSelected(b.id) ? '#2563eb' : b.strokeColor,
                      strokeWidth: isSelected(b.id)
                        ? (b.strokeWidth * 1.5) / (zoom || 1)
                        : b.strokeWidth / (zoom || 1),
                      dash: [60, 30],
                      lineCap: 'round',
                      lineJoin: 'round',
                      listening: false,
                    }"
                  />
                  <!-- Corner dots -->
                  <v-circle
                    v-for="(_, pi) in Array.from({
                      length: b.points.length / 2,
                    })"
                    :key="pi"
                    :config="{
                      x: b.points[pi * 2],
                      y: b.points[pi * 2 + 1],
                      radius: 6 / (zoom || 1),
                      fill: isSelected(b.id) ? '#2563eb' : b.strokeColor,
                      listening: false,
                    }"
                  />
                </v-group>
              </v-layer>

              <!-- ── Roads ───────────────────────────────────────────────── -->
              <v-layer>
                <v-group
                  v-for="road in roads"
                  :key="road.id"
                  :config="{
                    id: road.id,
                    opacity: road.visible ? 1 : 0.3,
                    draggable: elementDraggable(road),
                  }"
                  @click="onElementClick(road.id, $event)"
                  @dragend="onElementDragEnd(road.id, $event)"
                >
                  <!-- Invisible hit area -->
                  <v-line
                    :config="{
                      points: road.points,
                      stroke: 'transparent',
                      strokeWidth: road.strokeWidth * 1.2,
                      hitStrokeWidth: road.strokeWidth * 1.2,
                      lineCap: 'butt',
                      lineJoin: 'miter',
                    }"
                  />
                  <!-- Curb / edge border -->
                  <v-line
                    :config="{
                      points: road.points,
                      stroke: isSelected(road.id) ? '#93c5fd' : '#6b7280',
                      strokeWidth: road.strokeWidth * 1.14,
                      lineCap: 'butt',
                      lineJoin: 'miter',
                      listening: false,
                    }"
                  />
                  <!-- Asphalt surface -->
                  <v-line
                    :config="{
                      points: road.points,
                      stroke: isSelected(road.id)
                        ? '#3b82f6'
                        : road.color || '#374151',
                      strokeWidth: road.strokeWidth,
                      lineCap: 'butt',
                      lineJoin: 'miter',
                      listening: false,
                    }"
                  />
                  <!-- Center lane marking -->
                  <v-line
                    :config="{
                      points: road.points,
                      stroke:
                        road.direction === 'one-way'
                          ? 'rgba(255,255,255,0.7)'
                          : '#fbbf24',
                      strokeWidth: road.strokeWidth * 0.08,
                      lineCap: 'butt',
                      lineJoin: 'miter',
                      dash:
                        road.direction === 'one-way'
                          ? undefined
                          : [road.strokeWidth * 0.7, road.strokeWidth * 0.45],
                      listening: false,
                    }"
                  />
                </v-group>
              </v-layer>

              <!-- ── Parking slots ────────────────────────────────────────── -->
              <v-layer>
                <v-group
                  v-for="slot in slots"
                  :key="slot.id"
                  :config="{
                    id: slot.id,
                    x: slot.x,
                    y: slot.y,
                    rotation: slot.rotation,
                    draggable: elementDraggable(slot),
                    opacity: slot.visible ? 1 : 0.3,
                  }"
                  @click="onElementClick(slot.id, $event)"
                  @dragmove="onElementDragMove(slot.id, $event)"
                  @dragend="onElementDragEnd(slot.id, $event)"
                >
                  <!-- Asphalt base -->
                  <v-rect
                    :config="{
                      width: slot.width,
                      height: slot.height,
                      fill: '#1e2330',
                      stroke: isSelected(slot.id) ? '#2563eb' : '#111827',
                      strokeWidth: isSelected(slot.id) ? 3 : 1,
                    }"
                  />
                  <!-- Selection glow -->
                  <v-rect
                    v-if="isSelected(slot.id)"
                    :config="{
                      width: slot.width,
                      height: slot.height,
                      fill: 'rgba(37,99,235,0.12)',
                      listening: false,
                    }"
                  />
                  <!-- Left painted line -->
                  <v-line
                    :config="{
                      points: [5, 0, 5, slot.height],
                      stroke: 'rgba(255,255,255,0.85)',
                      strokeWidth: 3,
                      listening: false,
                    }"
                  />
                  <!-- Right painted line -->
                  <v-line
                    :config="{
                      points: [slot.width - 5, 0, slot.width - 5, slot.height],
                      stroke: 'rgba(255,255,255,0.85)',
                      strokeWidth: 3,
                      listening: false,
                    }"
                  />
                  <!-- Category color stripe at top (like a curb marking) -->
                  <v-rect
                    :config="{
                      x: 5,
                      y: 0,
                      width: slot.width - 10,
                      height: Math.max(6, Math.round(slot.height * 0.07)),
                      fill: slotFill(slot),
                      listening: false,
                    }"
                  />
                  <!-- Slot code — floor lettering style -->
                  <v-text
                    :config="{
                      text: slot.code,
                      width: slot.width,
                      height: slot.height,
                      align: 'center',
                      verticalAlign: 'middle',
                      fontSize: Math.min(slot.width, slot.height) * 0.3,
                      fontFamily: 'ui-monospace, monospace',
                      fontStyle: 'bold',
                      fill: 'rgba(255,255,255,0.88)',
                      listening: false,
                    }"
                  />
                  <!-- Category label at bottom -->
                  <v-text
                    :config="{
                      text: slot.category.toUpperCase(),
                      y:
                        slot.height -
                        Math.min(slot.width, slot.height) * 0.2 -
                        6,
                      width: slot.width,
                      align: 'center',
                      fontSize: Math.min(slot.width, slot.height) * 0.14,
                      fontFamily: 'ui-sans-serif, sans-serif',
                      fill: 'rgba(255,255,255,0.4)',
                      listening: false,
                    }"
                  />
                </v-group>
              </v-layer>

              <!-- ── Markers (entrance / exit / camera / sensor / label) ─── -->
              <v-layer>
                <template v-for="el in markers" :key="el.id">
                  <!-- Entrance -->
                  <v-group
                    v-if="el.type === 'entrance'"
                    :config="{
                      id: el.id,
                      x: el.x,
                      y: el.y,
                      rotation: el.rotation,
                      draggable: elementDraggable(el),
                      opacity: el.visible ? 1 : 0.3,
                    }"
                    @click="onElementClick(el.id, $event)"
                    @dragmove="onElementDragMove(el.id, $event)"
                    @dragend="onElementDragEnd(el.id, $event)"
                  >
                    <v-rect
                      :config="{
                        width: el.width,
                        height: el.height,
                        fill: '#16a34a',
                        cornerRadius: 6,
                        stroke: isSelected(el.id) ? '#1d4ed8' : 'transparent',
                        strokeWidth: 3,
                      }"
                    />
                    <v-text
                      :config="{
                        text: '▼ IN',
                        width: el.width,
                        height: el.height * 0.55,
                        align: 'center',
                        verticalAlign: 'middle',
                        fontSize: el.height * 0.28,
                        fill: '#ffffff',
                        fontStyle: 'bold',
                        listening: false,
                      }"
                    />
                    <v-text
                      :config="{
                        text: el.label,
                        y: el.height * 0.55,
                        width: el.width,
                        height: el.height * 0.45,
                        align: 'center',
                        verticalAlign: 'middle',
                        fontSize: el.height * 0.2,
                        fill: 'rgba(255,255,255,0.85)',
                        listening: false,
                      }"
                    />
                  </v-group>

                  <!-- Exit -->
                  <v-group
                    v-else-if="el.type === 'exit'"
                    :config="{
                      id: el.id,
                      x: el.x,
                      y: el.y,
                      rotation: el.rotation,
                      draggable: elementDraggable(el),
                      opacity: el.visible ? 1 : 0.3,
                    }"
                    @click="onElementClick(el.id, $event)"
                    @dragmove="onElementDragMove(el.id, $event)"
                    @dragend="onElementDragEnd(el.id, $event)"
                  >
                    <v-rect
                      :config="{
                        width: el.width,
                        height: el.height,
                        fill: '#dc2626',
                        cornerRadius: 6,
                        stroke: isSelected(el.id) ? '#1d4ed8' : 'transparent',
                        strokeWidth: 3,
                      }"
                    />
                    <v-text
                      :config="{
                        text: '▲ OUT',
                        width: el.width,
                        height: el.height * 0.55,
                        align: 'center',
                        verticalAlign: 'middle',
                        fontSize: el.height * 0.28,
                        fill: '#ffffff',
                        fontStyle: 'bold',
                        listening: false,
                      }"
                    />
                    <v-text
                      :config="{
                        text: el.label,
                        y: el.height * 0.55,
                        width: el.width,
                        height: el.height * 0.45,
                        align: 'center',
                        verticalAlign: 'middle',
                        fontSize: el.height * 0.2,
                        fill: 'rgba(255,255,255,0.85)',
                        listening: false,
                      }"
                    />
                  </v-group>

                  <!-- Camera: FOV cone + body -->
                  <v-group
                    v-else-if="el.type === 'camera'"
                    :config="{
                      id: el.id,
                      draggable: elementDraggable(el),
                      opacity: el.visible ? 1 : 0.3,
                    }"
                    @click="onElementClick(el.id, $event)"
                    @dragmove="onElementDragMove(el.id, $event)"
                    @dragend="onElementDragEnd(el.id, $event)"
                  >
                    <v-line
                      :config="{
                        points: cameraFovPoints(el as CameraEl),
                        closed: true,
                        fill: 'rgba(251,191,36,0.12)',
                        stroke: 'rgba(251,191,36,0.5)',
                        strokeWidth: 2,
                        listening: false,
                      }"
                    />
                    <v-circle
                      :config="{
                        id: el.id,
                        x: el.x,
                        y: el.y,
                        radius: 80,
                        fill: isSelected(el.id) ? '#fbbf24' : '#f59e0b',
                        stroke: isSelected(el.id) ? '#1d4ed8' : '#78350f',
                        strokeWidth: isSelected(el.id) ? 3 : 1.5,
                      }"
                    />
                    <v-text
                      :config="{
                        x: el.x - 50,
                        y: el.y - 40,
                        text: '📷',
                        fontSize: 80,
                        listening: false,
                      }"
                    />
                  </v-group>

                  <!-- Sensor -->
                  <v-group
                    v-else-if="el.type === 'sensor'"
                    :config="{
                      id: el.id,
                      draggable: elementDraggable(el),
                      opacity: el.visible ? 1 : 0.3,
                    }"
                    @click="onElementClick(el.id, $event)"
                    @dragmove="onElementDragMove(el.id, $event)"
                    @dragend="onElementDragEnd(el.id, $event)"
                  >
                    <v-circle
                      :config="{
                        id: el.id,
                        x: el.x,
                        y: el.y,
                        radius: 70,
                        fill: isSelected(el.id) ? '#38bdf8' : '#0ea5e9',
                        stroke: isSelected(el.id) ? '#1d4ed8' : '#0369a1',
                        strokeWidth: isSelected(el.id) ? 3 : 1.5,
                      }"
                    />
                    <v-text
                      :config="{
                        x: el.x - 40,
                        y: el.y - 28,
                        text: 'S',
                        fontSize: 60,
                        fill: '#ffffff',
                        fontStyle: 'bold',
                        fontFamily: 'ui-monospace, monospace',
                        listening: false,
                      }"
                    />
                  </v-group>

                  <!-- Label -->
                  <v-text
                    v-else-if="el.type === 'label'"
                    :config="{
                      id: el.id,
                      x: el.x,
                      y: el.y,
                      text: el.text,
                      fontSize: el.fontSize,
                      fill: isSelected(el.id) ? '#2563eb' : el.color,
                      rotation: el.rotation,
                      draggable: elementDraggable(el),
                      opacity: el.visible ? 1 : 0.3,
                    }"
                    @click="onElementClick(el.id, $event)"
                    @dragmove="onElementDragMove(el.id, $event)"
                    @dragend="onElementDragEnd(el.id, $event)"
                  />
                </template>
              </v-layer>

              <!-- ── Draw preview ─────────────────────────────────────────── -->
              <v-layer :config="{ listening: false }">
                <v-rect v-if="slotPreviewConfig" :config="slotPreviewConfig" />
                <template v-if="roadPreviewConfigs">
                  <v-line
                    v-for="(cfg, i) in roadPreviewConfigs"
                    :key="i"
                    :config="cfg"
                  />
                </template>
                <v-line
                  v-if="boundaryPreviewConfig"
                  :config="boundaryPreviewConfig"
                />
                <v-rect v-if="selRectConfig" :config="selRectConfig" />
              </v-layer>

              <!-- ── Transformer (resize / rotate handles) ───────────────── -->
              <v-layer>
                <v-transformer
                  ref="transformer"
                  :config="{
                    rotateEnabled: true,
                    keepRatio: false,
                    enabledAnchors: [
                      'top-left',
                      'top-right',
                      'bottom-left',
                      'bottom-right',
                      'middle-left',
                      'middle-right',
                      'top-center',
                      'bottom-center',
                    ],
                    anchorSize: 10,
                    borderStroke: '#2563eb',
                    anchorStroke: '#2563eb',
                    anchorFill: '#ffffff',
                  }"
                  @transformend="onTransformEnd"
                />
              </v-layer>
            </v-stage>

            <template #fallback>
              <div
                class="flex items-center justify-center h-full text-sm text-muted-foreground"
              >
                Loading canvas…
              </div>
            </template>
          </client-only>

          <!-- Status bar -->
          <div
            class="absolute bottom-0 left-0 right-0 flex items-center justify-between px-3 py-1 text-[11px] text-muted-foreground bg-background/80 backdrop-blur border-t select-none pointer-events-none"
          >
            <span>
              {{ activeTool }} tool
              <span v-if="isDrawingRoad">
                — double-click or Enter to finish road</span
              >
              <span v-if="isDrawingBoundary">
                — double-click or Enter to close boundary</span
              >
            </span>
            <span class="tabular-nums">
              {{ Math.round(zoom * 100) }}% &nbsp;·&nbsp; x:{{
                cursorPos.x
              }}
              y:{{ cursorPos.y }} &nbsp;·&nbsp; {{ elements.length }} elements
              &nbsp;·&nbsp; {{ selectedIds.size }} selected
            </span>
          </div>
        </div>

        <!-- Property panel -->
        <LotEditorPropertyPanel
          :element="selectedElement"
          :db-slots="dbSlots"
          @update="updateElement"
          @remove="removeElement"
          @duplicate="duplicate"
        />
      </div>
    </div>

    <!-- Hidden file inputs -->
    <input
      ref="bgFile"
      type="file"
      accept="image/*"
      class="hidden"
      @change="handleBgUpload"
    />
    <input
      ref="importFile"
      type="file"
      accept=".json,application/json"
      class="hidden"
      @change="handleImportJSON"
    />
  </div>
</template>
