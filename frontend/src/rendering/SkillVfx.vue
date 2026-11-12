<script setup lang="ts">
defineProps<{ kind: string; defensive?: boolean }>()
</script>
<template>
  <svg :class="['skill-vfx', { defensive }]" viewBox="0 0 100 100" aria-hidden="true">
    <g v-if="kind === 'heal'" fill="none" stroke="currentColor" stroke-width="3"><circle cx="50" cy="54" r="28" /><path d="M50 29v50M25 54h50M24 14v10m-5-5h10m48 44v12m-6-6h12" /><path d="m31 88 19-12 19 12" /></g>
    <g v-else-if="kind === 'shield' || kind === 'guard'" fill="none" stroke="currentColor" stroke-width="3"><path d="m50 9 31 13v31L71 73 50 90 29 73 19 53V22Z" /><path d="m50 23 18 8v22L50 73 32 53V31Z" /><path d="M50 36v23M39 47h22" /></g>
    <g v-else-if="kind === 'arrow'" fill="none" stroke="currentColor" stroke-width="3"><path d="M9 82 84 17M64 17h20v20M19 69l12 12M12 76l12 12M14 52l19-16M49 87l19-16" /></g>
    <g v-else-if="kind === 'flame' || kind === 'fire'" fill="currentColor" opacity=".85"><path d="M51 7C61 33 79 37 80 60L68 84 48 94 25 79 18 58 34 34 35 57 47 43Z" /><path d="m49 47 13 17-3 15-10 9-12-13 3-13Z" fill="#f5efca" /></g>
    <g v-else-if="kind === 'wave' || kind === 'slash'" fill="none" stroke="currentColor"><path d="M12 81Q20 13 87 17 48 36 37 91" stroke-width="7" /><path d="M23 9 84 83M10 29l63 61" stroke-width="2" /></g>
    <g v-else-if="kind === 'water'" fill="none" stroke="currentColor" stroke-width="4"><path d="M8 42q14-17 28 0t28 0 28 0M8 57q14-17 28 0t28 0 28 0M8 72q14-17 28 0t28 0 28 0" /><path d="M50 10q-15 18-15 25a15 15 0 0 0 30 0q0-7-15-25Z" stroke-width="2" /></g>
    <g v-else-if="kind === 'stone'" fill="currentColor"><path d="m13 67 7-20 16-8 13 14-2 26-22 9Zm42-32 7-17 20 8 6 22-13 17-20-7Z" /><path d="m47 9 4 13m-43 7 15 7m49 43 13 11" stroke="currentColor" stroke-width="4" /></g>
    <g v-else-if="kind === 'wind'" fill="none" stroke="currentColor" stroke-width="3"><path d="M8 35h58q22 0 16-17-9-15-17 0M7 49h72q22 0 12-14M13 62h46q25 0 18 20-10 17-20-1M20 75h21" /></g>
    <g v-else-if="kind === 'jade'" fill="none" stroke="currentColor" stroke-width="3"><path d="m50 7 35 43-35 43L15 50Zm0 14 23 29-23 29-23-29Z" /><path d="M7 50h22m42 0h22M50 7v22m0 42v22" /></g>
    <g v-else-if="kind === 'buff'" fill="none" stroke="currentColor" stroke-width="3"><path d="m22 64 28-37 28 37M22 83l28-37 28 37M50 14v15" /><circle cx="50" cy="52" r="37" stroke-dasharray="7 8" /></g>
    <g v-else fill="none" stroke="currentColor"><path d="m17 16 66 68M80 16 20 84" stroke-width="7" /><path d="M50 7v18M7 50h18m50 0h18M50 75v18" stroke-width="3" /></g>
  </svg>
</template>
<style scoped>
.skill-vfx{position:absolute;inset:6% 4% 20%;width:92%;height:74%;pointer-events:none;color:#e1bd67;filter:drop-shadow(0 1px #4c3c25);animation:skill-flare .44s ease-out both}.skill-vfx.defensive{color:#a6e6c1}@keyframes skill-flare{0%{opacity:0;transform:scale(.65) rotate(-7deg)}35%{opacity:1}100%{opacity:0;transform:scale(1.12) rotate(4deg)}}@media(prefers-reduced-motion:reduce){.skill-vfx{animation:none;opacity:.6}}
</style>
