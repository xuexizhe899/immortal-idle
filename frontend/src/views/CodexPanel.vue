<script setup lang="ts">
import { computed } from 'vue'

import DiscipleCard from '../components/DiscipleCard.vue'
import { useGameStore } from '../stores/game'

const LEAN_LABELS: Record<string, string> = {
  attack: '攻',
  defense: '防',
  support: '辅',
  craft: '炼',
}

const store = useGameStore()

const roster = computed(() =>
  store.disciples.map((disciple) => ({
    disciple,
    name: store.catalog?.disciples[disciple.template_id]?.name ?? disciple.template_id,
  })),
)

const owned = computed(() => new Set(store.state?.unlocks ?? []))

const recruitables = computed(() => {
  const catalog = store.catalog?.disciples ?? {}
  return Object.entries(catalog).sort(
    (a, b) => a[1].unlock_cost.reputation - b[1].unlock_cost.reputation,
  )
})

function price(id: string): number {
  const base = store.catalog?.disciples[id]?.unlock_cost.reputation ?? 0
  return owned.value.has(id) ? base * 0.5 : base
}

function realmOf(id: string): number {
  return store.disciples.find((d) => d.template_id === id)?.realm ?? 0
}
</script>

<template>
  <div class="codex">
    <div class="head">
      <h3>门下弟子</h3>
      <span class="hint">已选 {{ store.party.length }} / 5</span>
    </div>
    <p v-if="roster.length === 0" class="hint">还没有弟子，往下招一个。</p>
    <div class="grid">
      <DiscipleCard
        v-for="entry in roster"
        :key="entry.disciple.id"
        :disciple="entry.disciple"
        :name="entry.name"
        :selected="store.party.includes(entry.disciple.id)"
        :disabled="entry.disciple.busy"
        @toggle="store.toggleParty(entry.disciple.id)"
      />
    </div>

    <div class="head recruit-head">
      <h3>招贤</h3>
      <span class="hint">声望 {{ (store.resources?.reputation ?? 0).toFixed(0) }}</span>
    </div>
    <div class="list">
      <div v-for="[id, d] in recruitables" :key="id" class="row">
        <span class="name">{{ d.name }}</span>
        <span class="meta">
          {{ d.title }} · {{ LEAN_LABELS[d.lean] }}
          <template v-if="owned.has(id)"> · 境界 {{ realmOf(id) }}</template>
        </span>
        <button class="mini" type="button" :disabled="store.busy" @click="store.recruit(id)">
          {{ owned.has(id) ? '升境界' : '招募' }} · {{ price(id) }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 10px;
}

.head h3 {
  margin: 0;
  font-size: 15px;
}

.recruit-head {
  margin-top: 20px;
  padding-top: 14px;
  border-top: 2px solid var(--border);
}

.hint {
  color: var(--muted);
  font-size: 12px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(104px, 1fr));
  gap: 10px;
}

.list {
  display: flex;
  flex-direction: column;
}

.row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 0;
  border-bottom: 1px solid var(--border);
}

.row:last-child {
  border-bottom: none;
}

.name {
  width: 60px;
  flex: none;
  font-size: 14px;
}

.meta {
  flex: 1;
  color: var(--muted);
  font-size: 12px;
}

.mini {
  flex: none;
  padding: 4px 10px;
  border: 2px solid var(--border);
  background: transparent;
  color: inherit;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}

.mini:hover:not(:disabled) {
  background: var(--border);
  color: var(--surface);
}

.mini:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
</style>
