<script setup lang="ts">
import { ArrowLeft, Brain, Calendar, Info, RefreshCw, TrendingUp } from "lucide-vue-next";

const route = useRoute();
const client = useSupabaseClient();
const config = useRuntimeConfig();
const lotId = route.params.id as string;

// Fetch lot data
const { data: lot } = await useLazyAsyncData(`lot-${lotId}`, async () => {
  const { data } = await client
    .from("lots")
    .select("id, name, address, timezone")
    .eq("id", lotId)
    .is("deleted_at", null)
    .single();
  return data;
});

useHead(() => ({
  title: lot.value
    ? `Forecast — ${lot.value.name} — Smart Parking`
    : "Forecast — Smart Parking",
}));

// Fetch current occupancy
const currentOccupied = ref(0);
const totalSlots = ref(0);
const loadingSlots = ref(true);

async function loadCurrentState() {
  loadingSlots.value = true;
  const { data } = await client
    .from("slots")
    .select("id, current_state")
    .eq("lot_id", lotId)
    .is("deleted_at", null);
  
  if (data) {
    totalSlots.value = data.length;
    currentOccupied.value = data.filter((s) => s.current_state === "occupied").length;
  }
  loadingSlots.value = false;
}

await loadCurrentState();

// Forecasting state
const forecastUrl = config.public.forecastUrl;
const forecasting = ref(false);
const forecastError = ref<string | null>(null);

type ForecastPoint = {
  time: Date;
  hour: number;
  dayOfWeek: number;
  predicted: number;
  utilization: number;
};

const forecastPoints = ref<ForecastPoint[]>([]);
const hoveredIndex = ref<number | null>(null);

// Generate recursive 12-hour forecast
async function runForecast() {
  if (!forecastUrl) {
    forecastError.value = "Forecasting API URL is not configured.";
    return;
  }

  forecasting.value = true;
  forecastError.value = null;
  forecastPoints.value = [];

  try {
    let lastOccupied = currentOccupied.value;
    const points: ForecastPoint[] = [];
    const now = new Date();

    // autogressive multi-step forecast (12 hours ahead)
    for (let i = 1; i <= 12; i++) {
      const targetTime = new Date(now.getTime() + i * 60 * 60 * 1000);
      const hour = targetTime.getHours();
      // JavaScript Sunday is 0, model expects 0=Monday, 6=Sunday
      const dayOfWeek = targetTime.getDay() === 0 ? 6 : targetTime.getDay() - 1;

      const response = await $fetch<{ predicted_occupied_slots: number }>(
        `${forecastUrl}/api/forecast`,
        {
          method: "POST",
          body: {
            hour,
            day_of_week: dayOfWeek,
            previous_occupancy: Math.round(lastOccupied),
          },
        }
      );

      const predicted = Math.max(0, Math.min(response.predicted_occupied_slots, totalSlots.value));
      const utilization = totalSlots.value > 0 ? (predicted / totalSlots.value) * 100 : 0;

      points.push({
        time: targetTime,
        hour,
        dayOfWeek,
        predicted,
        utilization,
      });

      // Feed back prediction to next iteration
      lastOccupied = predicted;
    }

    forecastPoints.value = points;
  } catch (err: any) {
    console.error(err);
    forecastError.value = err?.message || "Failed to contact the forecasting service. Please verify it is running.";
  } finally {
    forecasting.value = false;
  }
}

// Automatically trigger on page load if URL is available
onMounted(() => {
  if (forecastUrl && totalSlots.value > 0) {
    runForecast();
  }
});

// SVG Chart Metrics
const chartWidth = 720;
const chartHeight = 240;
const paddingX = 40;
const paddingY = 30;

const chartPath = computed(() => {
  if (forecastPoints.value.length === 0) return "";
  const points = forecastPoints.value;
  const maxVal = totalSlots.value || 10;
  
  return points.map((p, idx) => {
    const x = paddingX + (idx / (points.length - 1)) * (chartWidth - 2 * paddingX);
    const y = chartHeight - paddingY - (p.predicted / maxVal) * (chartHeight - 2 * paddingY);
    return `${idx === 0 ? "M" : "L"} ${x} ${y}`;
  }).join(" ");
});

const chartAreaPath = computed(() => {
  if (forecastPoints.value.length === 0) return "";
  const baseLineY = chartHeight - paddingY;
  const startX = paddingX;
  const endX = chartWidth - paddingX;
  return `${chartPath.value} L ${endX} ${baseLineY} L ${startX} ${baseLineY} Z`;
});

function getPointCoords(idx: number, val: number) {
  const maxVal = totalSlots.value || 10;
  const x = paddingX + (idx / (12 - 1)) * (chartWidth - 2 * paddingX);
  const y = chartHeight - paddingY - (val / maxVal) * (chartHeight - 2 * paddingY);
  return { x, y };
}

// Summary Statistics
const peakHour = computed(() => {
  if (forecastPoints.value.length === 0) return null;
  return forecastPoints.value.reduce((max, p) => p.predicted > max.predicted ? p : max, forecastPoints.value[0]);
});

const avgOccupancy = computed(() => {
  if (forecastPoints.value.length === 0) return 0;
  const sum = forecastPoints.value.reduce((acc, p) => acc + p.predicted, 0);
  return sum / forecastPoints.value.length;
});

function formatHour(date: Date) {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

const dayNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function round(val: number, precision: number = 1): number {
  const factor = Math.pow(10, precision);
  return Math.round(val * factor) / factor;
}
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-start justify-between gap-4">
      <div class="space-y-1">
        <div class="flex items-center gap-2">
          <Button variant="ghost" size="icon" class="size-7" as-child>
            <NuxtLink :to="`/lots/${lotId}`">
              <ArrowLeft class="size-4" />
            </NuxtLink>
          </Button>
          <Skeleton v-if="!lot" class="h-6 w-40" />
          <h2 v-else class="text-lg font-semibold">{{ lot.name }} — Forecast</h2>
        </div>
        <p v-if="lot?.address" class="text-muted-foreground pl-9 text-sm">
          {{ lot.address }}
        </p>
      </div>
    </div>

    <LotNav />

    <!-- Not Configured Alert -->
    <Card v-if="!forecastUrl" class="border-amber-200 bg-amber-50/50 dark:border-amber-950 dark:bg-amber-950/20">
      <CardHeader class="flex flex-row items-start gap-4 space-y-0">
        <div class="rounded-full bg-amber-100 p-2 text-amber-800 dark:bg-amber-950 dark:text-amber-300">
          <Info class="size-5" />
        </div>
        <div class="space-y-1">
          <CardTitle class="text-amber-800 dark:text-amber-300">Forecasting Service Offline</CardTitle>
          <CardDescription class="text-amber-700/80 dark:text-amber-400/80">
            The Vercel Serverless forecasting microservice is not configured for this app.
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent class="text-muted-foreground pl-16 text-sm">
        <p class="mb-4">
          To enable smart predictions, please deploy your forecasting API to Vercel and define the environment variable in your local environment file:
        </p>
        <code class="block rounded border bg-muted px-4 py-2 font-mono text-xs text-foreground">
          NUXT_PUBLIC_FORECAST_URL=https://your-vercel-project.vercel.app
        </code>
      </CardContent>
    </Card>

    <div v-else class="space-y-6">
      <!-- Controls -->
      <div class="flex items-center justify-between gap-4">
        <div class="flex items-center gap-2">
          <Brain class="text-primary size-5" />
          <span class="text-sm font-medium">Predictive Occupancy (Next 12 Hours)</span>
        </div>
        <Button 
          variant="outline" 
          size="sm" 
          :disabled="forecasting || loadingSlots"
          @click="runForecast"
          class="gap-1.5"
        >
          <RefreshCw class="size-3.5" :class="forecasting ? 'animate-spin' : ''" />
          <span>{{ forecasting ? 'Forecasting...' : 'Recalculate' }}</span>
        </Button>
      </div>

      <!-- Error Alert -->
      <Card v-if="forecastError" class="border-destructive/30 bg-destructive/10">
        <CardContent class="flex items-center gap-3 py-3 text-destructive text-sm">
          <Info class="size-4 shrink-0" />
          <span>{{ forecastError }}</span>
        </CardContent>
      </Card>

      <!-- Forecast Graph Card -->
      <Card class="overflow-hidden">
        <CardContent class="p-6">
          <div v-if="forecasting && forecastPoints.length === 0" class="flex h-[280px] flex-col items-center justify-center space-y-4">
            <RefreshCw class="text-muted-foreground size-8 animate-spin" />
            <p class="text-muted-foreground text-sm font-medium">Running machine learning model calculations...</p>
          </div>

          <div v-else-if="forecastPoints.length === 0" class="flex h-[280px] flex-col items-center justify-center space-y-2 text-center">
            <TrendingUp class="text-muted-foreground size-8 opacity-40" />
            <p class="text-muted-foreground text-sm">Click 'Recalculate' above to run the forecasting model.</p>
          </div>

          <div v-else class="relative">
            <!-- SVG Chart -->
            <svg 
              :viewBox="`0 0 ${chartWidth} ${chartHeight}`" 
              class="w-full select-none"
            >
              <!-- Gradients definitions -->
              <defs>
                <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="var(--color-primary, #3b82f6)" stop-opacity="0.25" />
                  <stop offset="100%" stop-color="var(--color-primary, #3b82f6)" stop-opacity="0.00" />
                </linearGradient>
              </defs>

              <!-- Grid Lines -->
              <g stroke="currentColor" class="text-border" stroke-dasharray="3" stroke-width="1">
                <!-- Y grids -->
                <line :x1="paddingX" :y1="paddingY" :x2="chartWidth - paddingX" :y2="paddingY" />
                <line :x1="paddingX" :y1="chartHeight / 2" :x2="chartWidth - paddingX" :y2="chartHeight / 2" />
                <line :x1="paddingX" :y1="chartHeight - paddingY" :x2="chartWidth - paddingX" :y2="chartHeight - paddingY" />
              </g>

              <!-- Y Labels -->
              <g font-size="10" class="fill-muted-foreground text-right" font-family="monospace">
                <text :x="paddingX - 8" :y="paddingY + 3">{{ totalSlots }}</text>
                <text :x="paddingX - 8" :y="chartHeight / 2 + 3">{{ Math.round(totalSlots / 2) }}</text>
                <text :x="paddingX - 8" :y="chartHeight - paddingY + 3">0</text>
              </g>

              <!-- Filled Area -->
              <path :d="chartAreaPath" fill="url(#areaGrad)" />

              <!-- Line Path -->
              <path 
                :d="chartPath" 
                fill="none" 
                stroke="var(--color-primary, #3b82f6)" 
                stroke-width="3" 
                stroke-linecap="round" 
                stroke-linejoin="round"
              />

              <!-- Data Point dots -->
              <g>
                <circle 
                  v-for="(p, idx) in forecastPoints" 
                  :key="idx"
                  :cx="getPointCoords(idx, p.predicted).x" 
                  :cy="getPointCoords(idx, p.predicted).y" 
                  :r="hoveredIndex === idx ? 6 : 4" 
                  fill="var(--color-primary, #3b82f6)"
                  :stroke="hoveredIndex === idx ? '#fff' : 'none'"
                  :stroke-width="hoveredIndex === idx ? 2 : 0"
                  class="cursor-pointer transition-all duration-150"
                  @mouseenter="hoveredIndex = idx"
                  @mouseleave="hoveredIndex = null"
                />
              </g>

              <!-- X Labels -->
              <g font-size="10" class="fill-muted-foreground" font-family="monospace" text-anchor="middle">
                <text 
                  v-for="(p, idx) in forecastPoints" 
                  v-show="idx % 2 === 0"
                  :key="idx"
                  :x="getPointCoords(idx, p.predicted).x" 
                  :y="chartHeight - 8"
                >
                  {{ formatHour(p.time) }}
                </text>
              </g>
            </svg>

            <!-- Custom Overlay Hover Tooltip -->
            <div 
              v-if="hoveredIndex !== null && forecastPoints[hoveredIndex]"
              class="bg-popover border-border pointer-events-none absolute rounded-lg border p-3 text-popover-foreground shadow-lg text-xs space-y-1 transition-all duration-100"
              :style="{
                left: `${(getPointCoords(hoveredIndex, forecastPoints[hoveredIndex].predicted).x / chartWidth) * 100}%`,
                top: `${(getPointCoords(hoveredIndex, forecastPoints[hoveredIndex].predicted).y / chartHeight) * 100 - 85}px`,
                transform: 'translateX(-50%)'
              }"
            >
              <p class="text-muted-foreground font-semibold uppercase leading-none">
                {{ formatHour(forecastPoints[hoveredIndex].time) }} · {{ dayNames[forecastPoints[hoveredIndex].dayOfWeek] }}
              </p>
              <div class="flex items-baseline gap-1 text-sm font-semibold">
                <span>{{ round(forecastPoints[hoveredIndex].predicted, 1) }}</span>
                <span class="text-muted-foreground text-xs font-normal">/ {{ totalSlots }} occupied</span>
              </div>
              <p class="text-emerald-500 font-semibold leading-none">
                {{ round(forecastPoints[hoveredIndex].utilization, 0) }}% expected load
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- Stats Cards -->
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card class="flex items-center gap-4 p-4">
          <div class="rounded-full bg-primary/10 p-3 text-primary">
            <TrendingUp class="size-6" />
          </div>
          <div class="space-y-0.5">
            <p class="text-muted-foreground text-xs font-medium uppercase tracking-wide">Peak Demand</p>
            <h3 v-if="peakHour" class="text-lg font-bold">
              {{ round(peakHour.predicted, 1) }} slots
              <span class="text-muted-foreground text-xs font-normal block">at {{ formatHour(peakHour.time) }}</span>
            </h3>
            <h3 v-else class="text-lg font-bold">—</h3>
          </div>
        </Card>

        <Card class="flex items-center gap-4 p-4">
          <div class="rounded-full bg-emerald-500/10 p-3 text-emerald-500">
            <Calendar class="size-6" />
          </div>
          <div class="space-y-0.5">
            <p class="text-muted-foreground text-xs font-medium uppercase tracking-wide">Average Load</p>
            <h3 class="text-lg font-bold">
              {{ round(avgOccupancy, 1) }} slots
              <span class="text-muted-foreground text-xs font-normal block">{{ totalSlots > 0 ? round((avgOccupancy / totalSlots) * 100, 0) : 0 }}% expected utilization</span>
            </h3>
          </div>
        </Card>

        <Card class="flex items-center gap-4 p-4">
          <div class="rounded-full bg-orange-500/10 p-3 text-orange-500">
            <RefreshCw class="size-6" />
          </div>
          <div class="space-y-0.5">
            <p class="text-muted-foreground text-xs font-medium uppercase tracking-wide">Current Occupancy</p>
            <h3 class="text-lg font-bold">
              {{ currentOccupied }} slots
              <span class="text-muted-foreground text-xs font-normal block">Live from lot sensors</span>
            </h3>
          </div>
        </Card>
      </div>

      <!-- Info Details -->
      <Card class="bg-muted/30">
        <CardContent class="flex items-start gap-4 p-5">
          <Brain class="text-primary size-5 shrink-0 mt-0.5" />
          <div class="text-sm space-y-1">
            <h4 class="font-semibold text-foreground">About the Forecasting Model</h4>
            <p class="text-muted-foreground leading-relaxed text-xs">
              This system uses a **Random Forest Regressor** trained on historical lot occupancy behavior. It makes multi-step hourly predictions using recursive feedback: the predicted state of the next hour ($T+1$) is evaluated as the prior condition (`previous_occupancy`) for the following hour ($T+2$). Predictions are dynamically calculated live using the Vercel serverless ML API.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  </div>
</template>

<style scoped>
/* Injecting Tailwind primary variables dynamically in case of config changes */
:root {
  --color-primary: #3b82f6;
}
</style>
