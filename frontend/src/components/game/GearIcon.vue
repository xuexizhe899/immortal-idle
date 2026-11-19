<script setup lang="ts">
withDefaults(defineProps<{ slot: string; size?: number }>(), { size: 40 })
</script>

<template>
  <svg class="gear-icon" :width="size" :height="size" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="miter" aria-hidden="true">
    <template v-if="slot==='weapon'"><path d="M30 7h11v11L19 36l-7-7L30 7Z" fill="#d7e3d3" /><path d="m29 12 7 1-1 7M9 26l15 15M8 40l8-8" /><path d="m6 38 4 4 6-6-4-4-6 6Z" fill="#b89c68" /></template>
    <template v-else-if="slot==='armor'"><path d="m16 7-9 7 4 11 5-3v19h16V22l5 3 4-11-9-7-3 6H19l-3-6Z" fill="#d7e3d3" /><path d="M16 22v-6m16 6v-6M24 15v24M17 26h14M17 33h14" /><path d="m20 18 4-3 4 3-4 5-4-5Z" fill="#b89c68" /></template>
    <template v-else-if="slot==='boots'"><path d="M18 7h17l-3 22 7 4v8H10v-9l7-5 1-20Z" fill="#d7e3d3" /><path d="M18 12h16M18 18h15M17 26l15 3M11 36h27M22 16l6 2-6 3 5 3" /><path d="M11 36h27v5H11Z" fill="#b89c68" /></template>
    <template v-else><path d="M12 30a12 12 0 1 0 24 0 12 12 0 0 0-24 0Z" fill="#d7e3d3" /><path d="M17 30a7 7 0 1 0 14 0 7 7 0 0 0-14 0Z" /><path d="m17 12 7-7 7 7-7 9-7-9Z" fill="#b89c68" /><path d="M17 12h14M24 5v16" /></template>
  </svg>
</template>

<style scoped>
.gear-icon{display:block;flex:none;color:#55795e;shape-rendering:geometricPrecision}
</style>
