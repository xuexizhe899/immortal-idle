<script setup lang="ts">
import { computed } from 'vue'

import { useGameStore } from '../stores/game'

const RATE_LABELS: Record<string, string> = {
  cultivation_rate: '修为',
  spirit_stone_rate: '灵石',
  stamina_rate: '行动力',
  material_rate: '材料',
  injury_rate: '伤势消退',
}

const store = useGameStore()
const slots = computed(() => store.state?.duty_slots ?? [])
const onDuty = computed(() => new Set(slots.value.map((slot) => slot.disciple_id)))
const rates = computed(() => store.state?.duty_events?.at(-1)?.rates ?? {})

function nameOf(templateId: string): string {
  return store.catalog?.disciples[templateId]?.name ?? templateId
}

function slotName(index: number): string {
  const slot = slots.value[index]
  return slot ? nameOf(slot.disciple_id) : '空'
}

async function toggle(discipleId: string) {
  if (onDuty.value.has(discipleId)) {
    await store.unassignDuty(discipleId)
  } else {
    await store.assignDuty(discipleId)
  }
}
</script>

<template>
  <section class="panel">
    <div class="panel-head">
      <h2>值守编制</h2>
      <span class="hint">{{ onDuty.size }} / 6</span>
    </div>

    <div class="slots">
      <span
        v-for="i in 6"
        :key="i"
        class="slot"
        :class="{ filled: slots[i - 1] }"
      >
        {{ slotName(i - 1) }}
      </span>
    </div>

    <div class="rates">
      <span v-for="(value, key) in rates" :key="key" class="rate">
        {{ RATE_LABELS[key] ?? key }} +{{ (value * 100).toFixed(1) }}%
      </span>
      <span v-if="!Object.keys(rates).length" class="hint">无加成</span>
    </div>

    <div class="list">
      <div v-for="d in store.disciples" :key="d.id" class="row">
        <span class="name">{{ nameOf(d.template_id) }}</span>
        <span v-if="d.busy" class="hint">出征中</span>
        <button
          v-else
          class="mini"
          type="button"
          :disabled="store.busy"
          @click="toggle(d.id)"
        >
          {{ onDuty.has(d.id) ? '下岗' : '上岗' }}
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

.slots {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}

.slot {
  padding: 10px 6px;
  border: 1px dashed var(--border);
  border-radius: 8px;
  color: var(--muted);
  font-size: 12px;
  text-align: center;
}

.slot.filled {
  border-style: solid;
  border-color: var(--accent);
  color: var(--accent);
}

.rates {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 0 12px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 12px;
}

.rate {
  padding: 2px 8px;
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--muted);
  font-size: 12px;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 0;
  border-bottom: 1px solid var(--border);
}

.row:last-child {
  border-bottom: none;
}

.name {
  font-size: 14px;
}

.mini {
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
</style>
