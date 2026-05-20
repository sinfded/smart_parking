<script setup lang="ts">
import type { ToolType } from "@smart-parking/types";
import {
  MousePointer2,
  Square,
  Minus,
  LogIn,
  LogOut,
  Camera,
  Radio,
  Type,
  Trash2,
  Undo2,
  Redo2,
  Grid3x3,
  Magnet,
  Maximize2,
  Download,
  Upload,
  Image as ImageIcon,
} from "lucide-vue-next";

const props = defineProps<{
  activeTool: ToolType;
  gridVisible: boolean;
  snapEnabled: boolean;
  canUndo: boolean;
  canRedo: boolean;
}>();

const emit = defineEmits<{
  setTool: [tool: ToolType];
  undo: [];
  redo: [];
  toggleGrid: [];
  toggleSnap: [];
  fitToView: [];
  exportJSON: [];
  importJSON: [];
  uploadBg: [];
}>();

interface ToolDef {
  tool: ToolType;
  icon: any;
  label: string;
  shortcut: string;
}

const tools: ToolDef[] = [
  { tool: "select", icon: MousePointer2, label: "Select", shortcut: "S" },
  { tool: "slot", icon: Square, label: "Slot", shortcut: "P" },
  { tool: "road", icon: Minus, label: "Road", shortcut: "R" },
  { tool: "entrance", icon: LogIn, label: "Entrance", shortcut: "E" },
  { tool: "exit", icon: LogOut, label: "Exit", shortcut: "X" },
  { tool: "camera", icon: Camera, label: "Camera", shortcut: "C" },
  { tool: "sensor", icon: Radio, label: "Sensor", shortcut: "U" },
  { tool: "label", icon: Type, label: "Label", shortcut: "L" },
  { tool: "delete", icon: Trash2, label: "Delete", shortcut: "D" },
];
</script>

<template>
  <div
    class="w-14 shrink-0 flex flex-col gap-1 py-2 px-1 border-r bg-background"
  >
    <!-- Drawing tools -->
    <div class="flex flex-col gap-0.5">
      <button
        v-for="t in tools"
        :key="t.tool"
        class="group relative flex flex-col items-center justify-center h-11 w-full rounded-md transition-colors"
        :class="
          activeTool === t.tool
            ? 'bg-primary text-primary-foreground'
            : 'hover:bg-muted text-muted-foreground hover:text-foreground'
        "
        :title="`${t.label} (${t.shortcut})`"
        @click="emit('setTool', t.tool)"
      >
        <component :is="t.icon" class="size-4" />
        <span class="text-[9px] mt-0.5 leading-none">{{ t.shortcut }}</span>
      </button>
    </div>

    <Separator class="my-1" />

    <!-- History -->
    <button
      class="flex items-center justify-center h-10 w-full rounded-md transition-colors hover:bg-muted text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:pointer-events-none"
      :disabled="!canUndo"
      title="Undo (Ctrl+Z)"
      @click="emit('undo')"
    >
      <Undo2 class="size-4" />
    </button>
    <button
      class="flex items-center justify-center h-10 w-full rounded-md transition-colors hover:bg-muted text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:pointer-events-none"
      :disabled="!canRedo"
      title="Redo (Ctrl+Y)"
      @click="emit('redo')"
    >
      <Redo2 class="size-4" />
    </button>

    <Separator class="my-1" />

    <!-- View -->
    <button
      class="flex items-center justify-center h-10 w-full rounded-md transition-colors"
      :class="
        gridVisible
          ? 'bg-muted text-foreground'
          : 'hover:bg-muted text-muted-foreground hover:text-foreground'
      "
      title="Toggle grid (G)"
      @click="emit('toggleGrid')"
    >
      <Grid3x3 class="size-4" />
    </button>
    <button
      class="flex items-center justify-center h-10 w-full rounded-md transition-colors"
      :class="
        snapEnabled
          ? 'bg-muted text-foreground'
          : 'hover:bg-muted text-muted-foreground hover:text-foreground'
      "
      title="Toggle snap"
      @click="emit('toggleSnap')"
    >
      <Magnet class="size-4" />
    </button>
    <button
      class="flex items-center justify-center h-10 w-full rounded-md transition-colors hover:bg-muted text-muted-foreground hover:text-foreground"
      title="Fit to view (0)"
      @click="emit('fitToView')"
    >
      <Maximize2 class="size-4" />
    </button>

    <Separator class="my-1" />

    <!-- IO -->
    <button
      class="flex items-center justify-center h-10 w-full rounded-md transition-colors hover:bg-muted text-muted-foreground hover:text-foreground"
      title="Upload background image"
      @click="emit('uploadBg')"
    >
      <ImageIcon class="size-4" />
    </button>
    <button
      class="flex items-center justify-center h-10 w-full rounded-md transition-colors hover:bg-muted text-muted-foreground hover:text-foreground"
      title="Export layout JSON"
      @click="emit('exportJSON')"
    >
      <Download class="size-4" />
    </button>
    <button
      class="flex items-center justify-center h-10 w-full rounded-md transition-colors hover:bg-muted text-muted-foreground hover:text-foreground"
      title="Import layout JSON"
      @click="emit('importJSON')"
    >
      <Upload class="size-4" />
    </button>
  </div>
</template>
