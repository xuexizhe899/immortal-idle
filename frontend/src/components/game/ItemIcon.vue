<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { itemArtworkPath, itemIconPath } from '../../presentation/assetPaths'

const props = withDefaults(defineProps<{
  id?: string | null
  size?: number
  variant?: 'icon' | 'display'
}>(), { id: null, size: 32, variant: 'icon' })

const failedSources = ref<string[]>([])
watch([() => props.id, () => props.variant], () => { failedSources.value = [] })

const src = computed(() => [itemArtworkPath(props.id, props.variant), itemIconPath(props.id)]
  .find(path => path && !failedSources.value.includes(path)) ?? '')

function imageFailed(event: Event) {
  const path = (event.currentTarget as HTMLImageElement).getAttribute('src')
  if (path) failedSources.value.push(path)
}
</script>

<template>
  <span
    class="item-icon"
    :style="{ width: `${size}px`, height: `${size}px` }"
    aria-hidden="true"
  >
    <img v-if="src" :key="src" :src="src" :width="size" :height="size" alt="" @error="imageFailed" />
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
