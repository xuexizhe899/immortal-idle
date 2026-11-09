<script setup lang="ts">
import { computed, onMounted } from 'vue'

import { useGameStore } from './stores/game'
import CityView from './views/CityView.vue'
import RunView from './views/RunView.vue'

const store = useGameStore()
const inRun = computed(() => store.status !== 'idle')

onMounted(() => {
  void store.bootstrap()
})
</script>

<template>
  <header class="head">
    <h1>修仙放置</h1>
    <p class="sub">单机多档 · 局外挂机 · 局内出征</p>
  </header>

  <p v-if="store.error" class="error">{{ store.error }}</p>

  <CityView v-if="!inRun" />
  <RunView v-else />

  <footer class="foot">
    <span v-if="store.slotId">存档 #{{ store.slotId }} · revision {{ store.revision }}</span>
    <span v-if="store.busy" class="busy">处理中…</span>
  </footer>
</template>

<style scoped>
.head {
  margin-bottom: 28px;
}

h1 {
  margin: 0 0 6px;
  font-size: 28px;
}

.sub {
  margin: 0;
  color: var(--muted);
}

.error {
  margin: 0 0 14px;
  padding: 10px 14px;
  border: 1px solid var(--danger);
  border-radius: 6px;
  color: var(--danger);
  font-size: 13px;
}

.foot {
  display: flex;
  gap: 12px;
  margin-top: 28px;
  padding-top: 14px;
  border-top: 1px solid var(--border);
  color: var(--muted);
  font-size: 12px;
}

.busy {
  color: var(--accent);
}
</style>
