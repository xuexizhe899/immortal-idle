<script setup lang="ts">
import { computed } from 'vue'

import BattleStage from '../components/BattleStage.vue'
import { useGameStore } from '../stores/game'

const KIND_LABELS: Record<string, string> = {
  battle: '遭遇',
  elite: '强敌',
  boss: '首领',
}

const STATUS_LABELS: Record<string, string> = {
  choosing_node: '选择去路',
  choosing_affix: '选择词条',
  defeated: '已失败',
  cleared: '已通关',
}

const store = useGameStore()
const run = computed(() => store.run?.run ?? null)
const status = computed(() => store.status)

const statusLabel = computed(() => STATUS_LABELS[status.value] ?? '准备中')

const hpPercent = computed(() => {
  const current = run.value
  if (!current || current.max_hp <= 0) return 0
  return Math.max(0, Math.round((current.hp / current.max_hp) * 100))
})

function affixName(id: string): string {
  return store.catalog?.affixes[id]?.name ?? id
}

async function choose(index: number) {
  await store.choose(index)
}

async function pick(id: string) {
  await store.pickAffix(id)
}

async function finish() {
  await store.settleRun()
}
</script>

<template>
  <section class="panel">
    <div class="panel-head">
      <h2>出征</h2>
      <span class="hint">{{ statusLabel }}</span>
    </div>

    <div v-if="run" class="hp">
      <div class="bar"><span :style="{ width: `${hpPercent}%` }"></span></div>
      <span class="hp-text">{{ run.hp }} / {{ run.max_hp }}</span>
    </div>

    <BattleStage
      v-if="run"
      :hp="run.hp"
      :max-hp="run.max_hp"
      :layer="run.nodes?.length ?? 0"
    />

    <div v-if="run && (run.affixes ?? []).length" class="chips">
      <span v-for="id in run.affixes ?? []" :key="id" class="chip">{{ affixName(id) }}</span>
    </div>
  </section>

  <section v-if="status === 'choosing_node'" class="panel">
    <h2>第 {{ (run?.nodes?.length ?? 0) + 1 }} 层 · 选择去路</h2>
    <div class="choices">
      <button
        v-for="(node, index) in run?.choices ?? []"
        :key="`${node.enemy}-${index}`"
        class="choice"
        type="button"
        :disabled="store.busy"
        @click="choose(index)"
      >
        <span class="kind">{{ KIND_LABELS[node.kind] ?? node.kind }}</span>
        <span class="power">战力 {{ node.power }}</span>
        <span class="reward">修为 {{ (node.reward?.cultivation ?? 0).toFixed(1) }}</span>
      </button>
    </div>
  </section>

  <section v-else-if="status === 'choosing_affix'" class="panel">
    <h2>三选一</h2>
    <p class="hint">同组词条更容易凑成套</p>
    <div class="choices">
      <button
        v-for="id in run?.affix_options ?? []"
        :key="id"
        class="choice"
        type="button"
        :disabled="store.busy"
        @click="pick(id)"
      >
        {{ affixName(id) }}
      </button>
    </div>
  </section>

  <section v-else class="panel">
    <h2>{{ status === 'cleared' ? '通关' : '失败' }}</h2>
    <p class="hint">共到达 {{ run?.nodes?.length ?? 0 }} 层</p>
    <button class="primary" type="button" :disabled="store.busy" @click="finish">
      结算
    </button>
  </section>
</template>

<style scoped>
.panel-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 12px;
}

.panel-head h2,
.panel h2 {
  margin: 0 0 10px;
  font-size: 16px;
}

.panel-head h2 {
  margin-bottom: 0;
}

.hint {
  color: var(--muted);
  font-size: 13px;
}

.hp {
  display: flex;
  align-items: center;
  gap: 12px;
}

.bar {
  position: relative;
  flex: 1;
  height: 8px;
  border-radius: 4px;
  background: #e6e2d9;
  overflow: hidden;
}

.bar span {
  display: block;
  height: 100%;
  background: var(--accent);
  transition: width 0.2s ease;
}

.hp-text {
  font-family: ui-monospace, Consolas, monospace;
  font-size: 13px;
  color: var(--muted);
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 12px;
}

.chip {
  padding: 2px 8px;
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--muted);
  font-size: 12px;
}

.choices {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
}

.choice {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.choice:hover:not(:disabled) {
  border-color: var(--accent);
}

.choice:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.kind {
  font-size: 15px;
}

.power,
.reward {
  color: var(--muted);
  font-size: 12px;
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
</style>
