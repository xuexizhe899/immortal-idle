<script setup lang="ts">
import { ref, watch } from 'vue'
import type { HealPreview } from '../../api/client'
import { resourceName } from '../../presentation/gameText'
import { useGameStore } from '../../stores/game'

const props = defineProps<{ party: string[] }>()
const store = useGameStore()
const preview = ref<HealPreview | null>(null)
const loading = ref(false)
let request = 0
watch([() => props.party.join('|'), () => store.revision, () => store.slotId], async () => {
  const current = ++request
  preview.value = null
  loading.value = false
  if (!props.party.length || store.state?.active_run) return
  loading.value = true
  const result = await store.previewHealing([...props.party])
  if (current !== request) return
  preview.value = result
  loading.value = false
}, { immediate: true })
</script>

<template>
  <section
    v-if="loading || preview?.injured_count"
    class="party-healing"
    aria-label="队伍疗伤"
    aria-live="polite"
  >
    <div>
      <strong>出发前，先安顿伤势</strong>
      <p v-if="loading" class="muted">正在核对队伍伤势与疗伤丹……</p>
      <template v-else-if="preview">
        <p>{{ preview.injured_count }} 位伤员 · 本次可治 {{ preview.healed.length }} 人</p>
        <p class="muted">
          库存使用
          {{ preview.stock_used }}
          颗 · 补炼
          {{ preview.crafted }}
          颗
          <span v-for="(value,id) in preview.costs" :key="id">· {{ resourceName(id,store.catalog) }} ×{{ value }}</span>
        </p>
        <p v-if="preview.reason" class="muted">{{ preview.reason }}</p>
      </template>
    </div>
    <button
      class="btn btn-small"
      :disabled="store.busy || loading || !preview?.healed.length"
      @click="store.healParty([...party])"
    >
      一键炼丹疗伤
    </button>
  </section>
</template>

<style scoped>
.party-healing{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:15px 17px;margin:16px 0;border:1px solid #b4bf9e;border-left:3px solid var(--jade);background:#e6ebd8}.party-healing strong{font:16px 'SimSun',serif;color:var(--jade)}.party-healing p{font-size:11px;line-height:1.7;margin:5px 0 0}.party-healing .btn{flex-shrink:0}@media(max-width:600px){.party-healing{align-items:stretch;flex-direction:column;gap:10px}.party-healing .btn{width:100%}}
</style>
