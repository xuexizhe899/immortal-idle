<script setup lang="ts">
import { computed } from 'vue'

import { useGameStore } from '../stores/game'

const LEAN_LABELS: Record<string, string> = {
  attack: '攻',
  defense: '防',
  support: '辅',
  craft: '炼',
}

const store = useGameStore()
const owned = computed(() => new Set(store.state?.unlocks ?? []))

const list = computed(() => {
  const catalog = store.catalog?.disciples ?? {}
  return Object.entries(catalog).sort(
    (a, b) => a[1].unlock_cost.reputation - b[1].unlock_cost.reputation,
  )
})

function realmOf(id: string): number {
  return store.disciples.find((d) => d.template_id === id)?.realm ?? 0
}

function price(id: string): number {
  const base = store.catalog?.disciples[id]?.unlock_cost.reputation ?? 0
  return owned.value.has(id) ? base * 0.5 : base
}

async function recruit(id: string) {
  await store.recruit(id)
}
</script>

<template>
  <section class="panel">
    <div class="panel-head">
      <h2>招贤</h2>
      <span class="hint">声望 {{ (store.resources?.reputation ?? 0).toFixed(0) }}</span>
    </div>

    <div class="list">
      <div v-for="[id, d] in list" :key="id" class="row">
        <span class="name">{{ d.name }}</span>
        <span class="hint">
          {{ d.title }} · {{ LEAN_LABELS[d.lean] }}
          <template v-if="owned.has(id)"> · 境界 {{ realmOf(id) }}</template>
        </span>
        <button class="mini" type="button" :disabled="store.busy" @click="recruit(id)">
          {{ owned.has(id) ? '升境界' : '招募' }} · {{ price(id) }}
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.panel-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 12px;
}

.panel-head h2 {
  margin: 0;
  font-size: 16px;
}

.hint {
  color: var(--muted);
  font-size: 12px;
}

.list {
  display: flex;
  flex-direction: column;
}

.row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}

.row:last-child {
  border-bottom: none;
}

.name {
  width: 64px;
  flex: none;
  font-size: 14px;
}

.hint {
  flex: 1;
}

.mini {
  flex: none;
  padding: 4px 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: inherit;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}

.mini:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
}

.mini:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
