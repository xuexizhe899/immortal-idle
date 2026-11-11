<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { itemIconPath } from './itemIcons'

const props = withDefaults(defineProps<{
  id?: string | null
  size?: number
}>(), { id: null, size: 32 })

const failed = ref(false)
watch(() => props.id, () => { failed.value = false })

const src = computed(() => itemIconPath(props.id))
</script>

<template>
  <span
    class="item-icon"
    :style="{ width: `${size}px`, height: `${size}px` }"
    aria-hidden="true"
  >
    <img v-if="src && !failed" :src="src" :width="size" :height="size" alt="" @error="failed = true" />
    <svg v-else class="item-icon-placeholder" viewBox="0 0 64 64" aria-hidden="true">
      <path d="M32 10 52 32 32 54 12 32Z" fill="none" stroke="currentColor" stroke-width="3" />
      <circle cx="32" cy="32" r="4" fill="currentColor" />
    </svg>
  </span>
</template>

<style scoped>
.item-icon { display: inline-grid; place-items: center; flex: 0 0 auto; color: var(--jade); }
.item-icon img { display: block; width: 100%; height: 100%; image-rendering: pixelated; }
.item-icon-placeholder { width: 100%; height: 100%; opacity: .5; }
</style>
