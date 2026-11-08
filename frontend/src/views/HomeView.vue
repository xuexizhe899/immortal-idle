<script setup lang="ts">
import { computed, ref } from 'vue'

import DiscipleCard from '../components/DiscipleCard.vue'
import { useGameStore } from '../stores/game'

const store = useGameStore()
const party = ref<string[]>([])
const notice = ref<string | null>(null)

const roster = computed(() =>
  store.disciples.map((disciple) => ({
    disciple,
    name: store.catalog?.disciples[disciple.template_id]?.name ?? disciple.template_id,
  })),
)

const canStart = computed(() => party.value.length > 0 && !store.busy)

function toggle(id: string) {
  const index = party.value.indexOf(id)
  if (index >= 0) {
    party.value.splice(index, 1)
  } else if (party.value.length < 5) {
    party.value.push(id)
  }
}

async function doSettle() {
  const result = await store.settle()
  if (result) {
    notice.value = `补算 ${result.elapsed_hours.toFixed(2)} 小时：修为 +${result.gained.cultivation.toFixed(1)}，灵石 +${result.gained.spirit_stone.toFixed(1)}`
  }
}

async function doStart() {
  if (!canStart.value) return
  notice.value = null
  await store.startRun(party.value)
}
</script>

<template>
  <section class="resources">
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
  </section>

  <p v-if="notice" class="notice">{{ notice }}</p>

  <p v-if="store.lastRun" class="notice">
    上次出征：{{ store.lastRun.cleared }} 层 · {{ store.lastRun.victory ? '通关' : '失败' }} ·
    修为 +{{ (store.lastRun.loot.cultivation ?? 0).toFixed(1) }}
  </p>

  <section class="panel">
    <div class="panel-head">
      <h2>门下弟子</h2>
      <span class="hint">已选 {{ party.length }} / 5</span>
    </div>
    <p v-if="roster.length === 0" class="hint">还没有弟子，先去招人。</p>
    <div class="grid">
      <DiscipleCard
        v-for="entry in roster"
        :key="entry.disciple.id"
        :disciple="entry.disciple"
        :name="entry.name"
        :selected="party.includes(entry.disciple.id)"
        :disabled="entry.disciple.busy"
        @toggle="toggle(entry.disciple.id)"
      />
    </div>
  </section>

  <section class="actions">
    <button class="primary" type="button" :disabled="!canStart" @click="doStart">
      出征
    </button>
    <button class="ghost" type="button" :disabled="store.busy" @click="doSettle">
      收菜
    </button>
  </section>
</template>

<style scoped>
.resources {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}

.res {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
}

.label {
  color: var(--muted);
  font-size: 12px;
}

.value {
  font-family: ui-monospace, Consolas, monospace;
  font-size: 18px;
}

.notice {
  margin: 0 0 12px;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: 6px;
  background: var(--surface);
  color: var(--muted);
  font-size: 13px;
}

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
  font-size: 13px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(112px, 1fr));
  gap: 10px;
}

.actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
}

.primary {
  padding: 10px 22px;
  border: 1px solid var(--accent);
  border-radius: 8px;
  background: var(--accent);
  color: #fff;
  font: inherit;
  cursor: pointer;
}

.primary:disabled {
  border-color: var(--border);
  background: var(--border);
  cursor: not-allowed;
}

.ghost {
  padding: 10px 22px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
}

.ghost:disabled {
  color: var(--muted);
  cursor: not-allowed;
}
</style>
