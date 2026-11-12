<script setup lang="ts">
defineProps<{ name: string }>()
</script>
<template>
  <svg viewBox="0 0 48 48" fill="none" shape-rendering="crispEdges" aria-hidden="true">
    <g v-if="name === 'sect'">
      <path d="M6 22h36v4H6zM10 26h28v14H10zM6 40h36v4H6z" fill="#264f43" />
      <path d="M8 18h6v-4h6v-4h8v4h6v4h6v4H8z" fill="#73947b" />
      <path d="M4 22h40v4H4zM12 28h4v12h-4zM32 28h4v12h-4z" fill="#c4a363" />
      <path d="M21 29h6v11h-6zM22 6h4v4h-4z" fill="#f6e8ba" />
    </g>
    <g v-else-if="name === 'codex'">
      <path d="M19 5h10v4h4v11h-4v5H19v-5h-4V9h4zM12 28h7v-3h10v3h7v5h4v11H8V33h4z" fill="#284e44" />
      <path d="M19 12h10v8H19z" fill="#e6c58e" />
      <path d="M13 31h6l5 7 5-7h6v10H13z" fill="#7f9d80" />
      <path d="M19 26h4l1 6 1-6h4l-5 12zM22 39h4v5h-4z" fill="#f6e8ba" />
      <path d="M12 10h6v4h-6zM30 10h6v4h-6z" fill="#c4a363" />
    </g>
    <g v-else-if="name === 'duty'">
      <path d="M7 8h5v5h5v5h5v5h5v5h5v5h5v5h5v5h-8v-5h-5v-5h-5v-5h-5v-5h-5v-5H9v-5H7z" fill="#73947b" />
      <path d="M36 5h7v7h-5v5h-5v5h-5v5h-5v5h-5v5h-6v6H5v-7h6v-6h5v-5h5v-5h5v-5h5v-5h5z" fill="#284e44" />
      <path d="M36 9h3v3h-4v5h-5v5h-5v5h-5v5h-4v-4h5v-5h5v-5h5v-5h5z" fill="#f6e8ba" />
      <path d="M10 25h4v5h5v4h5v4h-5v-4h-5v-4h-4zM26 33h5v-5h5v-5h4v5h-4v5h-5v5h-5z" fill="#c4a363" />
    </g>
    <g v-else-if="name === 'alchemy'">
      <path d="M18 5h12v4H18zM14 10h20v5H14zM17 15h14v5h7v5h4v14h-4v4H10v-4H6V25h4v-5h7z" fill="#284e44" />
      <path d="M18 9h12v5H18zM12 25h24v12H12zM17 20h14v5H17z" fill="#7f9d80" />
      <path d="M10 15h28v4H10zM10 37h28v4H10zM20 25h8v4h4v4h-4v4h-8v-4h-4v-4h4z" fill="#c4a363" />
      <path d="M22 28h4v6h-4zM14 26h3v7h-3z" fill="#f6e8ba" />
    </g>
    <g v-else-if="name === 'forge'">
      <path d="M9 6h18v4h8v4h5v7H26v-5H9zM23 21h6v12h-6zM8 34h32v5H8zM13 39h22v5H13z" fill="#284e44" />
      <path d="M10 7h16v7H10zM27 11h7v7h-7z" fill="#7f9d80" />
      <path d="M22 21h5v13h-5zM5 30h13v5H5zM8 35h32v3H8z" fill="#c4a363" />
      <path d="M12 8h4v5h-4zM35 26h4v4h-4zM39 21h4v3h-4z" fill="#f6e8ba" />
    </g>
    <g v-else>
      <path d="M21 3h6v5h5v4h5v4h-7v5h9v4h-7v5h10v4h-9v7h7v4H8v-4h7v-7H6v-4h10v-5H9v-4h9v-5h-7v-4h5V8h5z" fill="#264f43" />
      <path d="M21 10h6v5h-6zM20 20h8v4h-8zM18 29h12v4H18zM20 36h8v5h-8z" fill="#f6e8ba" />
      <path d="M11 15h26v3H11zM9 24h30v3H9zM6 33h36v3H6zM8 41h32v4H8z" fill="#c4a363" />
    </g>
  </svg>
</template>
