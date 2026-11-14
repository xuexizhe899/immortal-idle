<script setup lang="ts">
defineProps<{ name?: string }>()
const paths: Record<string, string> = {
  leaf: 'M12 21V10m0 7C3 17 3 8 3 8s9-1 9 9Zm0-4C12 4 21 3 21 3s1 10-9 10Z',
  stone: 'm12 2 9 7-3 12H6L3 9l9-7Zm0 0L8 10l4 11 4-11-4-8ZM3 9l5 1h8l5-1',
  flame: 'M12 2C15 8 7 9 8 14c1-1 3-2 4-5 1 3 6 4 6 8a6 6 0 0 1-12 0C2 10 8 8 12 2Z',
  star: 'm12 2 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1 3-6Z',
  home: 'm3 10 9-7 9 7M5 9v12h14V9M9 21v-7h6v7',
  tower: 'M5 22h14M7 22V8h10v14M5 8h14l-7-6-7 6Zm2 6h10M7 18h10M12 8v14',
  people: 'M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm-7 10v-3a7 7 0 0 1 14 0v3M17 4a4 4 0 0 1 0 8m2 2a6 6 0 0 1 3 5v2',
  scroll: 'M6 3h13a3 3 0 0 1 0 6h-1M6 3a3 3 0 0 0-3 3v13a2 2 0 0 0 4 0V6a3 3 0 0 0-1-3Zm1 18h12V9M10 9h5m-5 4h5m-5 4h5',
  sword: 'm14 3 7-1-1 7L8 21l-5-5L14 3ZM3 12l9 9M3 21l4-4M12 12l6-6',
  ship: 'M3 17h18l-3 4H7l-4-4Zm2-2V7h8l3 3v5M8 7V4h5l3 3M7 20l-2 2m14-2 2 2',
  close: 'm6 6 12 12M6 18 18 6', check: 'm4 12 5 5L20 6', chevron: 'm9 5 7 7-7 7', plus: 'M12 5v14M5 12h14', bag: 'M5 7h14l2 14H3L5 7Zm3 0V5a4 4 0 0 1 8 0v2',
}
</script>
<template><svg class="game-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="paths[name ?? 'leaf'] ?? paths.leaf" /></svg></template>
