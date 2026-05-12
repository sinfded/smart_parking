<script setup lang="ts">
import type { SessionDetail } from "~/components/SessionDetailSheet.vue";

const client = useSupabaseClient();

const activeOnly = ref(true);

const {
  data: sessions,
  status,
  refresh,
} = await useLazyAsyncData(
  "sessions",
  async () => {
    let query = client
      .from("parking_sessions")
      .select(
        "id, slot_id, started_at, ended_at, duration_seconds, plate_number, slots(label), lots(name)",
      )
      .order("started_at", { ascending: false })
      .limit(100);

    if (activeOnly.value) {
      query = query.is("ended_at", null);
    }

    const { data } = await query;
    return (data ?? []) as SessionDetail[];
  },
  { watch: [activeOnly] },
);

function formatDate(d: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(d));
}

function formatDuration(seconds: number | null) {
  if (!seconds) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

const selectedSession = ref<SessionDetail | null>(null);
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <Tabs
        :default-value="activeOnly ? 'active' : 'all'"
        @update:model-value="(v) => (activeOnly = v === 'active')"
      >
        <TabsList>
          <TabsTrigger value="active">Active</TabsTrigger>
          <TabsTrigger value="all">All</TabsTrigger>
        </TabsList>
      </Tabs>
      <Button variant="outline" size="sm" @click="refresh">Refresh</Button>
    </div>

    <Card class="p-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Slot</TableHead>
            <TableHead>Lot</TableHead>
            <TableHead>Started</TableHead>
            <TableHead>Ended</TableHead>
            <TableHead>Duration</TableHead>
            <TableHead>Plate</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-if="status === 'pending'">
            <TableCell colspan="6">
              <div class="space-y-2 py-2">
                <Skeleton v-for="i in 5" :key="i" class="h-8 w-full" />
              </div>
            </TableCell>
          </TableRow>
          <TableEmpty v-else-if="!sessions?.length" :colspan="6">
            No sessions found.
          </TableEmpty>
          <TableRow
            v-for="s in sessions"
            v-else
            :key="s.id"
            class="cursor-pointer"
            @click="selectedSession = s"
          >
            <TableCell class="font-medium">
              {{ s.slots?.label ?? "—" }}
            </TableCell>
            <TableCell class="text-muted-foreground">
              {{ s.lots?.name ?? "—" }}
            </TableCell>
            <TableCell>{{ formatDate(s.started_at) }}</TableCell>
            <TableCell>
              <Badge v-if="!s.ended_at" variant="default">Active</Badge>
              <span v-else class="text-muted-foreground">{{
                formatDate(s.ended_at)
              }}</span>
            </TableCell>
            <TableCell>{{ formatDuration(s.duration_seconds) }}</TableCell>
            <TableCell class="text-muted-foreground">{{
              s.plate_number ?? "—"
            }}</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </Card>
  </div>

  <SessionDetailSheet
    :session="selectedSession"
    @close="selectedSession = null"
    @updated="refresh"
  />
</template>
