<script setup lang="ts">
import { computed, watch } from 'vue'
import { materialSources, type MaterialSource } from '../../presentation/materialSources'
import { number } from '../../shared/format'
import { useGameStore } from '../../stores/game'

const emit = defineEmits<{ open: [panel: string] }>()
const store = useGameStore()
const sources = computed(() => materialSources(store.catalog, store.state, store.worldMap))
watch([() => store.slotId, () => store.revision], () => { void store.loadWorld(true) }, { immediate: true })
function blockedLabel(source: MaterialSource) {
  return source.blockedReason || (source.kind === 'conquest' ? '已领取' : source.kind === 'garrison' ? '需攻克' : '未开放')
}
function go(id: string, source: MaterialSource) {
  store.productionTarget = id
  if (source.panel === 'expedition') store.targetSectId = source.sectId ?? ''
  emit('open', source.panel)
}
</script>

<template>
  <section class="material-sources" aria-label="材料来源总览">
    <div class="section-heading">
      <div><span class="eyebrow">缺什么，就去哪里</span><h3>材料来源总览</h3></div>
    </div>
    <p class="muted">驻守实际产出见宗门详情；跨地区来源需先切换图层，奖励按来源所在地区展示。</p>
    <article v-for="(name,id) in store.catalog?.materials" :key="id" class="source-card">
      <h4>{{ name }}</h4>
      <div v-for="source in sources[id]" :key="source.kind + (source.sectId ?? source.label)" class="source-row" :class="{unavailable:!source.available}">
        <span class="source-label">{{ source.label }}</span>
        <span class="source-detail">{{ source.detail }}</span>
        <strong v-if="source.rate !== undefined">+{{ number(source.rate,2) }}/时</strong>
        <button class="btn btn-small btn-quiet" :disabled="!source.available" @click="go(id,source)">{{ source.available ? '前往' : blockedLabel(source) }}</button>
      </div>
      <p v-if="!sources[id]?.length" class="muted">暂无已开放来源。</p>
    </article>
  </section>
</template>

<style scoped>
.material-sources{margin:18px 0}.material-sources h3{font-size:21px;margin:4px 0}.material-sources>.muted{font-size:11px;margin:6px 0 16px}.source-card{border:1px solid #c8bea3;background:#f3ecd8;padding:14px 16px;margin-bottom:10px}.source-card h4{font:16px 'SimSun',serif;margin:0 0 8px;color:var(--jade)}.source-row{display:flex;align-items:center;gap:10px;padding:7px 0;border-top:1px solid #ddd3b8;font-size:11px}.source-label{flex:none;min-width:110px;color:var(--ink)}.source-detail{flex:1;color:var(--muted)}.source-row strong{font-weight:500;color:var(--jade)}.source-row.unavailable .source-label,.source-row.unavailable .source-detail{opacity:.6}.source-row .btn{font-size:10px;padding:3px 8px}@media(max-width:640px){.source-row{flex-wrap:wrap}.source-label{min-width:0}.source-detail{flex-basis:100%;order:3}.source-row .btn{margin-left:auto}}
</style>
