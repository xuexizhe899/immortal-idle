<script setup lang="ts">
import { ref } from 'vue'

import { useGameStore } from '../stores/game'
import SaveSlotsPanel from './SaveSlotsPanel.vue'

const store = useGameStore()
const notice = ref<string | null>(null)

async function doSettle() {
  const result = await store.settle()
  if (result) {
    notice.value = `补算 ${result.elapsed_hours.toFixed(2)} 小时：修为 +${result.gained.cultivation.toFixed(1)}，灵石 +${result.gained.spirit_stone.toFixed(1)}，行动力 +${result.gained.stamina.toFixed(1)}`
  }
}
</script>

<template>
  <div>
    <div class="resources">
      <div class="res">
        <span class="label">修为</span>
        <span class="value">{{ (store.resources?.cultivation ?? 0).toFixed(1) }}</span>
      </div>
      <div class="res">
        <span class="label">灵石</span>
        <span class="value">{{ (store.resources?.spirit_stone ?? 0).toFixed(1) }}</span>
      </div>
      <div class="res">
        <span class="label">行动力</span>
        <span class="value">{{ (store.resources?.stamina ?? 0).toFixed(1) }}</span>
      </div>
      <div class="res">
        <span class="label">声望</span>
        <span class="value">{{ (store.resources?.reputation ?? 0).toFixed(0) }}</span>
      </div>
    </div>

    <button class="primary" type="button" :disabled="store.busy" @click="doSettle">
      收菜
    </button>

    <p v-if="notice" class="notice">{{ notice }}</p>

    <div class="slots">
      <SaveSlotsPanel />
    </div>
  </div>
</template>

<style scoped>
.resources {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 14px;
}

.res {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 12px;
  border: 2px solid var(--border);
  background: var(--bg);
}

.label {
  color: var(--muted);
  font-size: 12px;
}

.value {
  font-family: ui-monospace, Consolas, monospace;
  font-size: 18px;
}

.primary {
  padding: 8px 20px;
  border: 2px solid var(--border);
  background: var(--accent);
  color: #fff;
  font: inherit;
  cursor: pointer;
  box-shadow: 3px 3px 0 rgba(20, 20, 26, 0.35);
}

.primary:disabled {
  background: #cfcabb;
  color: #8b8779;
  box-shadow: none;
  cursor: not-allowed;
}

.notice {
  margin: 12px 0 0;
  padding: 8px 12px;
  border: 2px solid var(--border);
  border-left-width: 6px;
  border-left-color: var(--accent);
  font-size: 13px;
  color: var(--muted);
}

.slots {
  margin-top: 18px;
}
</style>
