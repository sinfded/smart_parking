<script setup lang="ts">
type MemberRole = "owner" | "manager" | "staff";

const ROLES: MemberRole[] = ["owner", "manager", "staff"];

const props = defineProps<{
  open: boolean;
  lotId: string;
}>();

const emit = defineEmits<{
  "update:open": [value: boolean];
  added: [];
}>();

const client = useSupabaseClient();

const inviteEmail = ref("");
const inviteRole = ref<MemberRole>("staff");
const inviteError = ref("");
const inviting = ref(false);

function resetForm() {
  inviteEmail.value = "";
  inviteRole.value = "staff";
  inviteError.value = "";
}

watch(
  () => props.open,
  (v) => { if (!v) resetForm(); },
);

async function addMember() {
  inviteError.value = "";
  inviting.value = true;

  const { data: rpcData, error } = await client.rpc("find_user_by_email", {
    p_email: inviteEmail.value,
  });
  const userId = rpcData as string | null;

  if (error || !userId) {
    inviteError.value = "No account found with that email address.";
    inviting.value = false;
    return;
  }

  const { error: insertError } = await client
    .from("lot_members")
    .insert({ lot_id: props.lotId, user_id: userId, role: inviteRole.value });

  if (insertError) {
    inviteError.value = insertError.message.includes("duplicate")
      ? "That user is already a member of this lot."
      : insertError.message;
    inviting.value = false;
    return;
  }

  emit("update:open", false);
  emit("added");
  inviting.value = false;
}
</script>

<template>
  <Dialog
    :open="open"
    @update:open="(v) => emit('update:open', v)"
  >
    <DialogContent class="sm:max-w-sm">
      <DialogHeader>
        <DialogTitle>Add member</DialogTitle>
        <DialogDescription>
          Enter the email address of an existing user account.
        </DialogDescription>
      </DialogHeader>
      <div class="space-y-4">
        <div class="space-y-2">
          <Label>Email</Label>
          <Input
            v-model="inviteEmail"
            type="email"
            placeholder="user@example.com"
            @keydown.enter="addMember"
          />
        </div>
        <div class="space-y-2">
          <Label>Role</Label>
          <Select v-model="inviteRole">
            <SelectTrigger class="w-full capitalize">
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
        </div>
        <p v-if="inviteError" class="text-destructive text-sm">
          {{ inviteError }}
        </p>
      </div>
      <DialogFooter>
        <Button variant="outline" @click="emit('update:open', false)">
          Cancel
        </Button>
        <Button :disabled="inviting || !inviteEmail.trim()" @click="addMember">
          <Spinner v-if="inviting" class="mr-2 size-4" />
          Add
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
