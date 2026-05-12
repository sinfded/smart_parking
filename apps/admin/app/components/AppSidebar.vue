<script setup lang="ts">
import {
  Building2,
  Car,
  Cpu,
  LayoutDashboard,
  LogOut,
  Settings,
} from "lucide-vue-next";
import type { SidebarProps } from "./ui/sidebar";

const route = useRoute();
const client = useSupabaseClient();
const user = useSupabaseUser();

const props = withDefaults(defineProps<SidebarProps>(), {
  variant: "floating",
});

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { href: "/lots", label: "Lots", icon: Building2 },
  { href: "/sessions", label: "Sessions", icon: Car },
  { href: "/devices", label: "Devices", icon: Cpu },
];

function isActive(item: { href: string; exact?: boolean }) {
  if (item.exact) return route.path === item.href;
  return route.path === item.href || route.path.startsWith(item.href + "/");
}

async function signOut() {
  await client.auth.signOut();
  await navigateTo("/login");
}
</script>

<template>
  <Sidebar v-bind="props">
    <SidebarHeader>
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton size="lg" as-child>
            <a href="#">
              <div
                class="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground"
              >
                <Car class="size-4" />
              </div>
              <div class="flex flex-col gap-0.5 leading-none">
                <span class="font-medium">Smart Parking</span>
                <span class="">v1.0.0</span>
              </div>
            </a>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    </SidebarHeader>
    <SidebarContent>
      <SidebarGroup>
        <SidebarGroupContent>
          <SidebarMenu>
            <SidebarMenuItem v-for="item in navItems" :key="item.href">
              <SidebarMenuButton as-child :is-active="isActive(item)">
                <NuxtLink :to="item.href" class="flex items-center gap-2">
                  <component :is="item.icon" class="size-4" />
                  <span>{{ item.label }}</span>
                </NuxtLink>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarGroupContent>
      </SidebarGroup>

      <SidebarGroup class="mt-auto">
        <SidebarGroupContent>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton as-child>
                <NuxtLink to="/settings" class="flex items-center gap-2">
                  <Settings class="size-4" />
                  <span>Settings</span>
                </NuxtLink>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarGroupContent>
      </SidebarGroup>
    </SidebarContent>
    <SidebarFooter>
      <div class="flex items-center gap-3">
        <Avatar class="size-8">
          <AvatarFallback class="text-xs">
            {{ user?.email?.slice(0, 2).toUpperCase() }}
          </AvatarFallback>
        </Avatar>
        <div class="min-w-0 flex-1">
          <p class="truncate text-sm font-medium">{{ user?.email }}</p>
        </div>
        <Button
          variant="ghost"
          size="icon"
          class="size-8 shrink-0"
          @click="signOut"
        >
          <LogOut class="size-4" />
        </Button>
      </div>
    </SidebarFooter>
  </Sidebar>
</template>
