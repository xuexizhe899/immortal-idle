<script setup lang="ts">
import { computed, ref } from 'vue'

import { useGameStore } from '../stores/game'

const props = defineProps<{ kind?: string }>()

const store = useGameStore()
const target = ref('')

const recipes = computed(() => store.catalog?.recipes ?? {})
const inventory = computed(() => store.state?.inventory ?? {})
const bonuses = computed(() => store.state?.bonuses ?? {})

const list = computed(() =>
  Object.entries(recipes.value).filter(([, r]) => !props.kind || r.kind === props.kind),
)

function needsTarget(id: string): boolean {
  return ['heal', 'realm'].includes(recipes.value[id]?.special ?? '')
}

function inputText(inputs: Record<string, number>): string {
  return Object.entries(inputs)
    .map(([id, count]) => `${store.catalog?.materials[id] ?? id}×${count}`)
    .join('，')
}

function canCraft(inputs: Record<string, number>): boolean {
  return Object.entries(inputs).every(
    ([id, count]) => (inventory.value[id] ?? 0) >= count,
  )
}

async function craft(id: string) {
  await store.craft(id, needsTarget(id) ? target.value : null)
}
</script>

<template>
  <div class="craft">
    <div class="bonus-line">
      <span class="hint">全局加成：</span>
      <span v-for="(value, key) in bonuses" :key="key" class="chip">
        {{ key }} +{{ (value * 100).toFixed(0) }}%
      </span>
      <span v-if="!Object.keys(bonuses).length" class="hint">暂无</span>
    </div>

    <div class="list">
      <div v-for="[id, r] in list" :key="id" class="row">
        <span class="name">{{ r.name }}</span>
        <span class="inputs">{{ inputText(r.inputs) }}</span>
        <button
          class="mini"
          type="button"
          :disabled="store.busy || !canCraft(r.inputs) || (needsTarget(id) && !target)"
          @click="craft(id)"
        >
          炼制
        </button>
      </div>
    </div>

    <div class="target-line">
      <span class="hint">疗伤 / 破境的目标：</span>
      <select v-model="target" class="select">
        <option value="">未选择</option>
        <option v-for="d in store.disciples" :key="d.id" :value="d.id">
          {{ store.catalog?.disciples[d.template_id]?.name ?? d.id }}
        </option>
      </select>
    </div>
  </div>
</template>

<style scoped>
.hint {
  color: var(--muted);
  font-size: 12px;
}

.bonus-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 2px solid var(--border);
}

.chip {
  padding: 2px 8px;
  border: 1px solid var(--border);
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
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}

.row:last-child {
  border-bottom: none;
}

.name {
  width: 76px;
  flex: none;
  font-size: 14px;
}

.inputs {
  flex: 1;
  color: var(--muted);
  font-size: 12px;
}

.mini {
  flex: none;
  padding: 4px 12px;
  border: 2px solid var(--border);
  background: transparent;
  color: inherit;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}

.mini:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.mini:hover:not(:disabled) {
  background: var(--border);
  color: var(--surface);
}

.target-line {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 2px solid var(--border);
}

.select {
  padding: 4px 8px;
  border: 2px solid var(--border);
  background: var(--surface);
  color: inherit;
  font: inherit;
  font-size: 12px;
}
</style>
