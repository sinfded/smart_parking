<script setup lang="ts">
import { ArrowLeft } from "lucide-vue-next";

const route = useRoute();
const client = useSupabaseClient();
const lotId = route.params.id as string;

const { data: lot, refresh: refreshLot } = await useLazyAsyncData(
  `lot-full-${lotId}`,
  async () => {
    const { data } = await client
      .from("lots")
      .select("id, name, address, timezone, is_public")
      .eq("id", lotId)
      .is("deleted_at", null)
      .single();
    return data;
  },
);

const { data: settings, refresh: refreshSettings } = await useLazyAsyncData(
  `lot-settings-${lotId}`,
  async () => {
    const { data } = await client
      .from("lot_settings")
      .select("*")
      .eq("lot_id", lotId)
      .maybeSingle();
    return data;
  },
);

useHead(() => ({
  title: lot.value ? `Settings — ${lot.value.name}` : "Settings",
}));

// ── Lot info form ─────────────────────────────────────────────────────────────
const lotForm = reactive({
  name: "",
  address: "",
  timezone: "Asia/Manila",
  is_public: true,
});

watch(
  lot,
  (v) => {
    if (!v) return;
    lotForm.name = v.name;
    lotForm.address = v.address ?? "";
    lotForm.timezone = v.timezone;
    lotForm.is_public = v.is_public;
  },
  { immediate: true },
);

const savingLot = ref(false);
async function saveLot() {
  savingLot.value = true;
  await client
    .from("lots")
    .update({
      name: lotForm.name.trim(),
      address: lotForm.address.trim() || null,
      timezone: lotForm.timezone.trim(),
      is_public: lotForm.is_public,
    })
    .eq("id", lotId);
  await refreshLot();
  savingLot.value = false;
}

// ── Gateway settings form ─────────────────────────────────────────────────────
const gwForm = reactive({
  confidence: 0.35,
  debounce_frames: 3,
  debounce_frames_free: 10,
  min_duration: 5,
  api_host: "0.0.0.0",
  api_port: 8000,
});

watch(
  settings,
  (v) => {
    if (!v) return;
    gwForm.confidence = v.confidence;
    gwForm.debounce_frames = v.debounce_frames;
    gwForm.debounce_frames_free = v.debounce_frames_free;
    gwForm.min_duration = v.min_duration;
    gwForm.api_host = v.api_host;
    gwForm.api_port = v.api_port;
  },
  { immediate: true },
);

const savingGw = ref(false);
async function saveGateway() {
  savingGw.value = true;
  await client.from("lot_settings").upsert(
    {
      lot_id: lotId,
      confidence: gwForm.confidence,
      debounce_frames: gwForm.debounce_frames,
      debounce_frames_free: gwForm.debounce_frames_free,
      min_duration: gwForm.min_duration,
      api_host: gwForm.api_host.trim(),
      api_port: gwForm.api_port,
      updated_at: new Date().toISOString(),
    },
    { onConflict: "lot_id" },
  );
  await refreshSettings();
  savingGw.value = false;
}
</script>

<template>
  <div class="space-y-6">
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

    <div class="grid gap-6 lg:grid-cols-2">
      <!-- Lot information -->
      <Card>
        <CardHeader>
          <CardTitle class="text-sm">Lot information</CardTitle>
          <CardDescription
            >Name, address, and visibility settings.</CardDescription
          >
        </CardHeader>
        <CardContent class="space-y-4">
          <div class="space-y-2">
            <Label for="lot-name">Name</Label>
            <Input id="lot-name" v-model="lotForm.name" />
          </div>
          <div class="space-y-2">
            <Label for="lot-address">Address</Label>
            <Input
              id="lot-address"
              v-model="lotForm.address"
              placeholder="123 Main St"
            />
          </div>
          <div class="space-y-2">
            <Label for="lot-tz">Timezone</Label>
            <Input
              id="lot-tz"
              v-model="lotForm.timezone"
              placeholder="Asia/Manila"
            />
          </div>
          <div class="space-y-2">
            <Label>Visibility</Label>
            <Select
              :model-value="lotForm.is_public ? 'true' : 'false'"
              @update:model-value="(v) => (lotForm.is_public = v === 'true')"
            >
              <SelectTrigger class="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="true"
                  >Public — listed in user app</SelectItem
                >
                <SelectItem value="false"
                  >Private — hidden from users</SelectItem
                >
              </SelectContent>
            </Select>
          </div>
        </CardContent>
        <CardFooter>
          <Button :disabled="savingLot" @click="saveLot">
            <Spinner v-if="savingLot" class="mr-2 size-4" />
            Save
          </Button>
        </CardFooter>
      </Card>

      <!-- Gateway / vision settings -->
      <Card>
        <CardHeader>
          <CardTitle class="text-sm">Gateway settings</CardTitle>
          <CardDescription
            >Vision detector thresholds and API config.</CardDescription
          >
        </CardHeader>
        <CardContent class="space-y-4">
          <div class="grid grid-cols-2 gap-4">
            <div class="space-y-2">
              <Label for="gw-confidence">Confidence</Label>
              <Input
                id="gw-confidence"
                v-model.number="gwForm.confidence"
                type="number"
                step="0.01"
                min="0"
                max="1"
              />
              <p class="text-muted-foreground text-xs">
                YOLO detection threshold (0–1)
              </p>
            </div>
            <div class="space-y-2">
              <Label for="gw-debounce">Debounce (occupied)</Label>
              <Input
                id="gw-debounce"
                v-model.number="gwForm.debounce_frames"
                type="number"
                min="1"
              />
              <p class="text-muted-foreground text-xs">
                Frames to confirm a car arrived
              </p>
            </div>
            <div class="space-y-2">
              <Label for="gw-debounce-free">Debounce (free)</Label>
              <Input
                id="gw-debounce-free"
                v-model.number="gwForm.debounce_frames_free"
                type="number"
                min="1"
              />
              <p class="text-muted-foreground text-xs">
                Frames to confirm a slot is empty
              </p>
            </div>
            <div class="space-y-2">
              <Label for="gw-mindur">Min duration (s)</Label>
              <Input
                id="gw-mindur"
                v-model.number="gwForm.min_duration"
                type="number"
                min="0"
              />
              <p class="text-muted-foreground text-xs">
                Sessions shorter than this are dropped
              </p>
            </div>
            <div class="space-y-2">
              <Label for="gw-port">API port</Label>
              <Input
                id="gw-port"
                v-model.number="gwForm.api_port"
                type="number"
                min="1"
                max="65535"
              />
            </div>
          </div>
          <div class="space-y-2">
            <Label for="gw-host">API host</Label>
            <Input
              id="gw-host"
              v-model="gwForm.api_host"
              placeholder="0.0.0.0"
            />
          </div>
        </CardContent>
        <CardFooter>
          <Button :disabled="savingGw" @click="saveGateway">
            <Spinner v-if="savingGw" class="mr-2 size-4" />
            Save
          </Button>
        </CardFooter>
      </Card>
    </div>
  </div>
</template>
