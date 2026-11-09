<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'

defineProps<{ title: string }>()
const emit = defineEmits<{ close: [] }>()

function onKey(event: KeyboardEvent) {
  if (event.key === 'Escape') emit('close')
}

onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="overlay" @click.self="$emit('close')">
    <section class="sheet">
      <header class="sheet-head">
        <h2>{{ title }}</h2>
        <button class="close" type="button" @click="$emit('close')">关闭</button>
      </header>
      <div class="sheet-body">
        <slot />
      </div>
    </section>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(20, 20, 26, 0.5);
}

.sheet {
  display: flex;
  flex-direction: column;
  width: min(760px, 100%);
  max-height: 86vh;
  border: 2px solid var(--border);
  background: var(--surface);
  box-shadow: 6px 6px 0 rgba(20, 20, 26, 0.35);
}

.sheet-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 2px solid var(--border);
}

.sheet-head h2 {
  margin: 0;
  font-size: 16px;
}

.close {
  padding: 4px 12px;
  border: 2px solid var(--border);
  background: transparent;
  color: inherit;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}

.close:hover {
  background: var(--border);
  color: var(--surface);
}

.sheet-body {
  padding: 16px;
  overflow-y: auto;
}
</style>
