export default defineNuxtConfig({
  compatibilityDate: "2025-07-15",
  devtools: { enabled: true },
  css: ["~/assets/tailwind.css"],
  modules: ["@nuxtjs/tailwindcss", "shadcn-nuxt", "@nuxtjs/supabase"],
  shadcn: {
    prefix: "",
    componentDir: "@/components/ui",
  },
  supabase: {
    redirectOptions: {
      login: "/login",
      callback: "/confirm",
      exclude: ["/login"],
    },
    types: "../../../packages/types/src/database.ts",
  },
  runtimeConfig: {
    public: {
      gatewayUrl: "",
    },
  },
});