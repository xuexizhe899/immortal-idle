<script setup lang="ts">
defineProps<{ kind: string }>()
</script>
<template>
  <svg class="enemy-figure" viewBox="0 0 90 100" aria-hidden="true" shape-rendering="crispEdges">
    <ellipse cx="45" cy="95" rx="35" ry="3" fill="#233d3633" />
    <g v-if="kind.includes('archer')" stroke="#263e36" stroke-width="2">
      <path d="m25 23-9 11 5 30 9-3-1-26Z" fill="#8b6743" /><path d="M18 23 15 8m7 16L22 6m4 18 4-15" stroke="#bfab75" /><path d="m12 9 4-5 4 7m0-5 3-4 3 5m1 3 5-4 1 6" fill="#ddd8bc" stroke-width="1" />
      <path d="M34 30 25 42 27 71 23 85 39 87 44 72 48 87 60 84 55 68 57 42 47 29Z" fill="#63866e" /><path d="m29 43 10-8 11 4-4 24-13 1Z" fill="#8eaa86" stroke="none" /><path d="m28 63 27 3-1 7-25-3Z" fill="#b99b5d" /><path d="M35 72v8m8-7v9m8-8v7" stroke="#3e5e49" />
      <path d="M32 12h18l5 13-8 11H35l-7-12Z" fill="#c5ba92" /><path d="M27 15 33 7h17l7 12-7 4H28Z" fill="#405c4a" /><path d="m33 10 16 0 4 8H30Z" fill="#7a9a77" stroke="none" /><path d="M35 26h5m6 0h4" stroke="#344d3b" /><path d="m33 32 8 6 9-6" fill="#3e634d" />
      <path d="m63 18 12 14 5 23-5 21-12 13m0-71v71" fill="none" stroke="#c7a65e" stroke-width="4" /><path d="m66 25 8 30-8 27" fill="none" stroke="#f0dab0" stroke-width="1" /><path d="M43 47 61 55 77 55" fill="none" stroke="#bbbd93" stroke-width="6" /><path d="M53 52h28m-4-4 6 4-6 4" fill="none" stroke="#ddca89" /><path d="M33 84 29 96m23-12 4 12" stroke-width="7" /><path d="M23 96h10m19 0h9" stroke="#53664e" stroke-width="4" />
    </g>
    <g v-else-if="kind.includes('master')" stroke="#263e36" stroke-width="2">
      <path d="m25 31-10 5-8 26 8 17 9-9 6-25m35-14 10 5 8 26-8 17-9-9-6-25" fill="#375953" /><path d="m13 58 7 5-6 8m63-13-7 5 6 8" fill="none" stroke="#bca96c" stroke-width="3" />
      <path d="m45 5 8 12 11 3-4 15 7 21 7 35H16l7-35 7-21-4-15 11-3Z" fill="#365b57" /><path d="m35 38 10 8 10-8 5 40-15 13-15-13Z" fill="#7da795" /><path d="m45 45 8 31-8 11-8-11Z" fill="#bbcfac" stroke="none" /><path d="m29 43 8 33-12 9m36-42-8 33 12 9" fill="none" stroke="#c4af70" stroke-width="3" />
      <path d="m28 17-5-7 12 3L39 3h12l4 10 12-3-5 7-6 7H34Z" fill="#a99051" /><path d="m45 7 4 9-4 8-4-8Z" fill="#e4d6a0" /><path d="M32 25h26l-3 15-10 5-10-5Z" fill="#4b7a68" /><path d="M33 29h8m8 0h8" stroke="#e0eed1" stroke-width="3" /><path d="m43 33 2 5 2-5" fill="#c9bc86" stroke-width="1" />
      <path d="M9 42v40m-5-45 5-8 5 8-5 8Z" fill="#8db49e" stroke="#c5b26c" /><path d="m76 45 7 8-7 8-7-8Z" fill="#bed1ac" /><path d="M37 88v8m16-8v8" stroke-width="7" /><path d="M29 96h12m8 0h12" stroke="#314e46" stroke-width="4" />
    </g>
    <g v-else-if="kind.includes('warden')" stroke="#263e36" stroke-width="2">
      <path d="m30 32-8 13 6 30-5 17h35l2-37-7-21Z" fill="#4c7760" /><path d="M33 39h19v33H33Z" fill="#a1c3a0" /><path d="m39 42 6 6-6 7-6-7Z" fill="#5a9175" stroke="none" /><path d="M32 60h22v7H32Z" fill="#bca66b" /><path d="m28 73 6 12m7-12v13m8-12 5 12" fill="none" stroke="#729c79" />
      <path d="m29 21 4-11h7V3h11v7h7l4 11-6 13H35Z" fill="#7ca68a" /><path d="M34 12h20l3 7H31Z" fill="#c7b47d" /><path d="m45 5 4 6-4 6-4-6Z" fill="#d4e6bd" stroke-width="1" /><path d="M34 23h9m5 0h8" stroke="#e5e6be" stroke-width="3" /><path d="m40 29 5 3 5-3" fill="none" stroke="#3e614a" />
      <path d="M5 37 20 28 36 37v30L21 85 6 68Z" fill="#65957b" /><path d="m11 40 9-5 10 5v24L20 77 12 65Z" fill="#b8d3b2" /><path d="m20 42 7 12-7 13-7-13Z" fill="#6a9e84" /><path d="M20 44v21" stroke="#dfd4a1" /><path d="M66 14v69m-6-63 6-14 6 14-6 9Z" fill="#99c2a1" stroke="#557c60" /><path d="M60 51h12" stroke="#c8b57d" stroke-width="5" /><path d="M33 90v6m20-6v6" stroke-width="7" /><path d="M27 96h12m10 0h10" stroke="#496e55" stroke-width="4" />
    </g>
    <g v-else stroke="#263e36" stroke-width="2">
      <path d="m24 36-9 4-7 15 8 13 12-4 34 1 8-11-5-16-10-6Z" fill="#737e76" /><path d="m25 27 10-6 20 3 11 14-4 39-12 12-23-9-9-25Z" fill="#90998b" /><path d="m24 39 13-7 9 10-6 20-17-7Zm22 4 12-6 5 14-8 19-10-8Z" fill="#aab29b" stroke="#596c5d" /><path d="m29 62 10 2-2 14-11-5m19-8 10 8-5 9-10-6" fill="#657b6b" /><path d="M28 30 31 13 44 6 58 13 61 30 51 40H37Z" fill="#9ca48b" /><path d="m34 14 10-4 10 5-2 7H34Z" fill="#b8bea1" stroke="none" /><path d="m30 23 13 2-2 8-10-3m15-5 13-2-1 7-10 3" fill="#3e5c4a" /><path d="M34 28h5m10 0h6" stroke="#dccd91" /><path d="m44 14-3 7 5 3-2 12m-20 7 8 5-5 8m26-11 5 7-6 10" fill="none" stroke="#596d5c" stroke-width="1" />
      <path d="m9 58 9-5 9 10-6 9-11-3Z" fill="#a7ac95" /><path d="m68 35 4 54" stroke="#927048" stroke-width="6" /><path d="m58 28 20-5 10 9-2 17-22 4-9-11Z" fill="#737f76" /><path d="m61 31 15-4 9 7-2 8-19 4Z" fill="#adb29c" stroke="none" /><path d="m69 29 3 7-7 6 4 6" fill="none" stroke="#50685a" /><path d="M30 82 26 95h15l2-11m7 0 3 11h14l-7-18" fill="#6a7c6b" /><path d="M27 92h12m15 0h10" stroke="#a5ae95" stroke-width="2" />
    </g>
  </svg>
</template>
<style scoped>.enemy-figure{display:block;width:100%;height:100%;overflow:visible}</style>
