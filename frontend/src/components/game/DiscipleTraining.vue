<script setup lang="ts">
import { computed } from 'vue'

import type { TrainingPreview, TrainingStats, TrainingStep } from '../../api/client'
import { resourceName, type DisplayCatalog } from '../../presentation/gameText'
import { number } from '../../shared/format'

const props = withDefaults(defineProps<{
  preview: TrainingPreview | null
  loading?: boolean
  busy?: boolean
  readOnly?: boolean
  pillName?: string
  catalog?: DisplayCatalog | null
}>(), { preview: null, loading: false, busy: false, readOnly: false, pillName: '破境丹' })

const emit = defineEmits<{ upgrade: []; breakthrough: [] }>()

const STAT_ROWS = [
  { key: 'health', label: '气血' },
  { key: 'attack', label: '攻击' },
  { key: 'defense', label: '防御' },
  { key: 'speed', label: '速度' },
] as const

function costText(costs: Record<string, number>): string {
  const parts = Object.entries(costs).filter(([, value]) => value > 0)
  if (!parts.length) return '无'
  return parts.map(([key, value]) => `${resourceName(key,props.catalog)} ${number(value)}`).join(' · ')
}

function dutyEntries(stats: TrainingStats | null | undefined): Array<[string, number]> {
  return Object.entries(stats?.duty_rates ?? {}).filter(([, value]) => value > 0.0001)
}

function dutyText(stats: TrainingStats | null | undefined): string {
  const entries = dutyEntries(stats)
  if (!entries.length) return '若值守：无额外加成'
  return `若值守：${entries.map(([key, value]) => productionText(key,value)).join(' · ')}`
}

function productionText(key: string, value: number): string {
  if (key.startsWith('material_') && key.endsWith('_flat')) {
    return `${resourceName(key.slice(9,-5),props.catalog)} +${number(value,2)}/时`
  }
  return `${resourceName(key,props.catalog)} +${number(value * 100,1)}%`
}

function dutyDelta(current: TrainingStats, next: TrainingStats | null | undefined): string {
  if (!next) return ''
  const before = new Map(dutyEntries(current))
  const changed = dutyEntries(next).filter(([key, value]) => value > (before.get(key) ?? 0) + 0.0001)
  return changed.map(([key, value]) => productionText(key,value)).join(' · ')
}

function statValue(stats: TrainingStats, key: typeof STAT_ROWS[number]['key']): number {
  return stats[key]
}

function statDelta(step: TrainingStep | null, key: typeof STAT_ROWS[number]['key']): string {
  if (!step?.target) return ''
  const current = props.preview?.current
  if (!current) return ''
  const delta = statValue(step.target, key) - statValue(current, key)
  return delta > 0 ? `+${number(delta, 1)}` : ''
}

const nextRealmDuty = computed(() => {
  const preview = props.preview
  if (!preview?.next_realm?.target) return ''
  return dutyDelta(preview.current, preview.next_realm.target)
})
</script>

<template>
  <section class="training-section">
    <div class="section-heading">
      <h4>培养</h4>
      <span v-if="preview" class="badge">等级 {{ preview.level }} / {{ preview.level_cap }} · 境界 {{ preview.realm }}</span>
    </div>
    <p class="training-note">等级影响战斗；境界影响战斗、值守和后续等级上限。</p>

    <template v-if="preview">
      <div v-if="preview.legacy_over_cap" class="training-warning">
        旧档等级或境界超出当前阶段上限，已保留；可按门槛突破，不会截断。
      </div>
      <div class="training-stats">
        <div v-for="row in STAT_ROWS" :key="row.key">
          <span>{{ row.label }}</span>
          <strong>{{ number(statValue(preview.current, row.key), 1) }}</strong>
        </div>
      </div>
      <p class="duty-line">{{ dutyText(preview.current) }}</p>

      <div class="training-grid">
        <article class="training-card">
          <header>
            <strong>修炼升级</strong>
            <span v-if="preview.next_level?.target">Lv.{{ preview.level }} → Lv.{{ preview.level + 1 }}</span>
          </header>
          <template v-if="preview.next_level">
            <div v-if="preview.next_level.target" class="delta-list">
              <span v-for="row in STAT_ROWS" :key="row.key">
                {{ row.label }} {{ number(statValue(preview.current, row.key), 1) }}
                <small>{{ statDelta(preview.next_level, row.key) }}</small>
              </span>
            </div>
            <p class="cost">消耗：{{ costText(preview.next_level.costs) }}</p>
            <p v-if="preview.next_level.reason" class="reason">{{ preview.next_level.reason }}</p>
            <button class="btn btn-small" :disabled="readOnly || busy || !preview.next_level.allowed" @click="emit('upgrade')">修炼升级</button>
          </template>
          <p v-else class="reason">已达当前阶段上限，请先突破境界。</p>
        </article>

        <article class="training-card">
          <header>
            <strong>境界突破</strong>
            <span v-if="preview.next_realm?.target">境界 {{ preview.realm }} → {{ preview.realm + 1 }}</span>
          </header>
          <template v-if="preview.next_realm">
            <div v-if="preview.next_realm.target" class="delta-list">
              <span v-for="row in STAT_ROWS" :key="row.key">
                {{ row.label }} {{ number(statValue(preview.current, row.key), 1) }}
                <small>{{ statDelta(preview.next_realm, row.key) }}</small>
              </span>
            </div>
            <p class="cost">等级要求：{{ preview.next_realm.requires_level }} 级</p>
            <p class="cost">
              消耗：{{ costText(preview.next_realm.costs) }}
              <span v-if="preview.next_realm.alternative_recipe_id">，或用{{ pillName }} 1 颗</span>
            </p>
            <p v-if="nextRealmDuty" class="duty-line">突破后：{{ nextRealmDuty }}</p>
            <p v-if="preview.next_realm.reason" class="reason">{{ preview.next_realm.reason }}</p>
            <button class="btn btn-small" :disabled="readOnly || busy || !preview.next_realm.allowed" @click="emit('breakthrough')">境界突破</button>
          </template>
          <p v-else class="reason">已达当前最高境界。</p>
        </article>
      </div>
    </template>
    <p v-else class="muted">{{ loading ? '正在读取培养信息…' : '暂无培养信息。' }}</p>
  </section>
</template>

<style scoped>
.training-section { padding-top: 16px; border-top: 1px solid #d3c8aa; margin-top: 16px; }
.training-section h4 { margin: 0 0 8px; font-size: 14px; }
.training-section .section-heading { margin-bottom: 6px; }
.training-note { margin: 0 0 10px; font-size: 10px; color: var(--muted); }
.training-warning { margin-bottom: 10px; padding: 8px 10px; border-left: 2px solid var(--gold); background: #e8e4d2; font-size: 10px; color: var(--ink); }
.training-stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; margin-bottom: 8px; }
.training-stats > div { padding: 6px 8px; background: #e6e4d2; }
.training-stats span { display: block; font-size: 9px; color: var(--muted); }
.training-stats strong { font-size: 15px; font-variant-numeric: tabular-nums; }
.duty-line { margin: 0 0 10px; font-size: 10px; color: var(--jade); }
.training-grid { display: grid; grid-template-columns: 1fr; gap: 10px; }
.training-card { padding: 10px; background: #e9e6d6; border: 1px solid #d3c8aa; min-width: 0; }
.training-card header { display: flex; justify-content: space-between; gap: 6px; align-items: baseline; margin-bottom: 7px; }
.training-card header strong { font-size: 12px; }
.training-card header span { font-size: 9px; color: var(--muted); }
.delta-list { display: flex; flex-wrap: wrap; gap: 3px 8px; margin-bottom: 6px; font-size: 10px; color: var(--muted); }
.delta-list small { color: var(--jade); font-size: 10px; }
.cost { margin: 0 0 4px; font-size: 10px; color: var(--muted); }
.reason { margin: 0 0 7px; font-size: 10px; color: var(--danger); }
.training-card .btn { width: 100%; margin-top: 2px; }
@media(max-width: 640px) {
  .training-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .training-grid { grid-template-columns: 1fr; }
}
</style>
