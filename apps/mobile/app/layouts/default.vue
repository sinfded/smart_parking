<template>
  <div class="min-h-screen bg-background font-sans">
    <header class="sticky top-0 z-10 bg-background/95 backdrop-blur border-b border-border">
      <div class="px-4 h-14 flex items-center gap-2">
        <slot name="header-left" />
        <span class="font-semibold text-sm tracking-tight truncate">
          <slot name="title">Smart Parking</slot>
        </span>
        <div class="ml-auto flex items-center">
          <slot name="header-right" />
        </div>
      </div>
    </header>
    <main class="px-4 py-4 pb-8 max-w-lg mx-auto">
      <slot />
    </main>
  </div>
</template>
