<script setup lang="ts">
const route = useRoute();
const lotId = route.params.id as string;

const tabs = [
  { href: `/lots/${lotId}`, label: "Overview", exact: true },
  { href: `/lots/${lotId}/slots`, label: "Slots" },
  { href: `/lots/${lotId}/cameras`, label: "Cameras" },
  { href: `/lots/${lotId}/members`, label: "Members" },
  { href: `/lots/${lotId}/settings`, label: "Settings" },
];

function isActive(tab: { href: string; exact?: boolean }) {
  if (tab.exact) return route.path === tab.href;
  return route.path === tab.href || route.path.startsWith(tab.href + "/");
}
</script>

<template>
  <div class="flex border-b">
    <NuxtLink
      v-for="tab in tabs"
      :key="tab.href"
      :to="tab.href"
      class="-mb-px border-b-2 px-3 py-2 text-sm transition-colors"
      :class="
        isActive(tab)
          ? 'border-primary font-medium text-foreground'
          : 'border-transparent text-muted-foreground hover:text-foreground'
      "
    >
      {{ tab.label }}
    </NuxtLink>
  </div>
</template>
