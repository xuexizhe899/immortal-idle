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
    <span class="healing-mark" aria-hidden="true">丹</span>
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
.party-healing{display:flex;align-items:center;justify-content:space-between;gap:13px;padding:12px 15px;margin:14px 0;border:1px solid #aab993;border-left:3px solid #326c55;background:#e4ebd5}.party-healing strong{font:16px 'SimSun',serif;color:var(--jade)}.party-healing p{font-size:11px;line-height:1.7;margin:5px 0 0}.party-healing .btn{flex-shrink:0}@media(max-width:600px){.party-healing{align-items:stretch;flex-direction:column;gap:10px}.party-healing .btn{width:100%}}

.healing-mark{display:grid;place-items:center;flex:none;width:34px;height:40px;border:1px solid #86a37c;background:#f6f1df;color:#326c55;font:22px SimSun,serif;box-shadow:inset 0 0 0 3px #e4ebd5,inset 0 0 0 4px #aab993}.party-healing>div{flex:1;min-width:0}.party-healing p{overflow-wrap:anywhere}.party-healing .btn{min-height:42px}
@media(max-width:600px){.party-healing{display:grid;grid-template-columns:34px minmax(0,1fr);gap:10px}.party-healing .btn{grid-column:1 / -1}.party-healing p{font-size:12px}}

</style>
