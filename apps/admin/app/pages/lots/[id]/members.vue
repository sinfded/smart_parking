<script setup lang="ts">
import { ArrowLeft, Plus, Trash2 } from "lucide-vue-next";

const route = useRoute();
const client = useSupabaseClient();
const lotId = route.params.id as string;

type Member = {
  user_id: string;
  role: "owner" | "manager" | "staff";
  created_at: string;
  display_name: string | null;
  email: string | null;
};

const { data: lot } = await useLazyAsyncData(`lot-${lotId}`, async () => {
  const { data } = await client
    .from("lots")
    .select("id, name")
    .eq("id", lotId)
    .single();
  return data;
});

useHead(() => ({
  title: lot.value ? `Members — ${lot.value.name}` : "Members",
}));

const members = ref<Member[]>([]);
const membersLoading = ref(true);

async function loadMembers() {
  membersLoading.value = true;

  const { data: rows } = await client
    .from("lot_members")
    .select("user_id, role, created_at")
    .eq("lot_id", lotId)
    .order("created_at");

  if (!rows?.length) {
    members.value = [];
    membersLoading.value = false;
    return;
  }

  const userIds = rows.map((r) => r.user_id);
  const { data: profiles } = await client
    .from("profiles")
    .select("id, display_name, email")
    .in("id", userIds);

  members.value = rows.map((r) => ({
    ...r,
    display_name:
      profiles?.find((p) => p.id === r.user_id)?.display_name ?? null,
    email: profiles?.find((p) => p.id === r.user_id)?.email ?? null,
  })) as Member[];

  membersLoading.value = false;
}

await loadMembers();

const ROLES = ["owner", "manager", "staff"] as const;

async function updateRole(userId: string, role: string) {
  await client
    .from("lot_members")
    .update({ role: role as Member["role"] })
    .eq("lot_id", lotId)
    .eq("user_id", userId);
  await loadMembers();
}

async function removeMember(userId: string) {
  await client
    .from("lot_members")
    .delete()
    .eq("lot_id", lotId)
    .eq("user_id", userId);
  await loadMembers();
}

const showInvite = ref(false);

function formatDate(d: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(
    new Date(d),
  );
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <Button variant="ghost" size="icon" class="size-7" as-child>
          <NuxtLink to="/lots">
            <ArrowLeft class="size-4" />
          </NuxtLink>
        </Button>
        <Skeleton v-if="!lot" class="h-6 w-36" />
        <h2 v-else class="text-base font-semibold">{{ lot.name }}</h2>
      </div>
      <Button size="sm" @click="showInvite = true">
        <Plus class="mr-2 size-4" />
        Add member
      </Button>
    </div>

    <LotNav />

    <Card class="p-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Member</TableHead>
            <TableHead>Role</TableHead>
            <TableHead>Added</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-if="membersLoading">
            <TableCell colspan="4">
              <div class="space-y-2 py-2">
                <Skeleton v-for="i in 3" :key="i" class="h-8 w-full" />
              </div>
            </TableCell>
          </TableRow>
          <TableEmpty v-else-if="!members.length" :colspan="4">
            No members yet.
          </TableEmpty>
          <TableRow v-for="m in members" v-else :key="m.user_id">
            <TableCell>
              <div>
                <p class="text-sm font-medium">
                  {{ m.display_name ?? m.email ?? "Unknown" }}
                </p>
                <p
                  v-if="m.display_name && m.email"
                  class="text-muted-foreground text-xs"
                >
                  {{ m.email }}
                </p>
              </div>
            </TableCell>
            <TableCell>
              <Select
                :model-value="m.role"
                @update:model-value="(v) => updateRole(m.user_id, v as string)"
              >
                <SelectTrigger class="h-8 w-32 text-xs capitalize">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem
                    v-for="r in ROLES"
                    :key="r"
                    :value="r"
                    class="capitalize"
                  >
                    {{ r }}
                  </SelectItem>
                </SelectContent>
              </Select>
            </TableCell>
            <TableCell class="text-muted-foreground text-sm">
              {{ formatDate(m.created_at) }}
            </TableCell>
            <TableCell class="text-right">
              <Button
                variant="ghost"
                size="icon"
                class="text-muted-foreground hover:text-destructive size-7"
                @click="removeMember(m.user_id)"
              >
                <Trash2 class="size-3.5" />
              </Button>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </Card>
  </div>

  <AddMemberDialog
    v-model:open="showInvite"
    :lot-id="lotId"
    @added="loadMembers"
  />
</template>
