<script setup lang="ts">
const route = useRoute();

const pageTitle = computed(() => {
  const map: Record<string, string> = {
    "/": "Dashboard",
    "/lots": "Lots",
    "/sessions": "Sessions",
    "/devices": "Devices",
    "/settings": "Settings",
  };
  if (route.path.startsWith("/lots/")) return "Lots";
  return map[route.path] ?? "Admin";
});
</script>

<template>
  <SidebarProvider :style="{ '--sidebar-width': '19rem' }">
    <AppSidebar />
    <SidebarInset>
      <header class="flex h-16 shrink-0 items-center gap-2 px-4">
        <SidebarTrigger class="-ml-1" />
        <Separator
          orientation="vertical"
          class="mr-2 data-[orientation=vertical]:h-4"
        />
        <h1 class="text-sm font-medium">{{ pageTitle }}</h1>
      </header>
      <div class="flex flex-1 flex-col p-6">
        <slot />
      </div>
    </SidebarInset>
  </SidebarProvider>
</template>
