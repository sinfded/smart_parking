export default defineNuxtConfig({
  compatibilityDate: "2025-07-15",
  devtools: { enabled: true },
  css: ["leaflet/dist/leaflet.css"],
  build: {
    transpile: ["lucide-vue-next"],
  },
  modules: [
    "@nuxtjs/tailwindcss",
    "shadcn-nuxt",
    "@vite-pwa/nuxt",
    "@nuxtjs/supabase",
  ],
  shadcn: {
    prefix: "",
    componentDir: "@/components/ui",
  },
  supabase: {
    redirect: false,
  },
  pwa: {
    registerType: "autoUpdate",
    manifest: {
      name: "Smart Parking",
      short_name: "Parking",
      description: "Find parking lots and check live slot availability",
      theme_color: "#2563eb",
      background_color: "#ffffff",
      display: "standalone",
      orientation: "portrait",
      start_url: "/",
    },
    workbox: {
      navigateFallback: null,
      globPatterns: ["**/*.{js,css,html,svg,png,ico}"],
    },
    devOptions: {
      enabled: true,
      suppressWarnings: true,
      type: "module",
    },
  },
});
