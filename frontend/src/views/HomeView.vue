<script setup lang="ts">
import { computed, ref } from 'vue'

import DiscipleCard from '../components/DiscipleCard.vue'
import { useGameStore } from '../stores/game'
import CraftPanel from './CraftPanel.vue'
import DutyPanel from './DutyPanel.vue'
import RecruitPanel from './RecruitPanel.vue'
import SaveSlotsPanel from './SaveSlotsPanel.vue'

const TABS = [
  { key: 'roster', label: '弟子' },
  { key: 'duty', label: '值守' },
  { key: 'recruit', label: '招贤' },
  { key: 'craft', label: '炼制' },
  { key: 'saves', label: '存档' },
]

const store = useGameStore()
const party = ref<string[]>([])
const notice = ref<string | null>(null)
const activeTab = ref('roster')

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

  <nav class="tabs">
    <button
      v-for="tab in TABS"
      :key="tab.key"
      class="tab"
      :class="{ active: activeTab === tab.key }"
      type="button"
      @click="activeTab = tab.key"
    >
      {{ tab.label }}
    </button>
  </nav>

  <section v-if="activeTab === 'roster'" class="panel">
    <div class="panel-head">
      <h2>门下弟子</h2>
      <span class="hint">已选 {{ party.length }} / 5</span>
    </div>
    <p v-if="roster.length === 0" class="hint">还没有弟子，去「招贤」看看。</p>
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

  <DutyPanel v-else-if="activeTab === 'duty'" />
  <RecruitPanel v-else-if="activeTab === 'recruit'" />
  <CraftPanel v-else-if="activeTab === 'craft'" />
  <SaveSlotsPanel v-else />

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
  gap: 8px;
  margin-bottom: 14px;
}

.res {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 12px;
  border: 2px solid var(--border);
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
  padding: 8px 12px;
  border: 2px solid var(--border);
  border-left-width: 6px;
  border-left-color: var(--accent);
  background: var(--surface);
  color: var(--muted);
  font-size: 13px;
}

.tabs {
  display: flex;
  gap: 0;
  margin-bottom: 14px;
  border-bottom: 2px solid var(--border);
}

.tab {
  padding: 8px 16px;
  border: 2px solid transparent;
  border-bottom: none;
  background: transparent;
  color: var(--muted);
  font: inherit;
  font-size: 14px;
  cursor: pointer;
}

.tab.active {
  border-color: var(--border);
  background: var(--surface);
  color: var(--text);
  margin-bottom: -2px;
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
  grid-template-columns: repeat(auto-fill, minmax(108px, 1fr));
  gap: 10px;
}

.actions {
  display: flex;
  gap: 10px;
  margin-top: 18px;
}

.primary {
  padding: 10px 24px;
  border: 2px solid var(--border);
  background: var(--accent);
  color: #fff;
  font: inherit;
  cursor: pointer;
  box-shadow: 3px 3px 0 rgba(43, 43, 51, 0.35);
}

.primary:disabled {
  background: #cfcabb;
  color: #8b8779;
  box-shadow: none;
  cursor: not-allowed;
}

.ghost {
  padding: 10px 24px;
  border: 2px solid var(--border);
  background: var(--surface);
  color: inherit;
  font: inherit;
  cursor: pointer;
  box-shadow: 3px 3px 0 rgba(43, 43, 51, 0.2);
}

.ghost:disabled {
  color: var(--muted);
  box-shadow: none;
  cursor: not-allowed;
}
</style>
