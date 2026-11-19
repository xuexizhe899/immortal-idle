<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import PanelModal from '../ui/PanelModal.vue'
import ItemIcon from './ItemIcon.vue'
import { materialSources, type MaterialSource } from '../../presentation/materialSources'
import { number } from '../../shared/format'
import { useGameStore } from '../../stores/game'

const emit = defineEmits<{ open: [panel: string] }>()
const store = useGameStore()
const sources = computed(() => materialSources(store.catalog, store.state, store.worldMap))
const search = ref('')
const availableOnly = ref(false)
const selectedId = ref('')
const materials = computed(() => Object.entries(store.catalog?.materials ?? {}).filter(([id, name]) => (!search.value || name.includes(search.value)) && (!availableOnly.value || availableCount(id)>0)))
const selectedName = computed(() => store.catalog?.materials[selectedId.value])
const sourceNames: Record<MaterialSource['kind'],string> = { idle: '挂机', duty: '值守', garrison: '驻守', tower: '问道', conquest: '首胜', retrial: '论道', dungeon: '秘境', invasion: '入侵', smelt: '熔炼' }
watch([() => store.slotId, () => store.revision], () => { void store.loadWorld(true) }, { immediate: true })
watch(() => store.slotId, () => { selectedId.value = ''; search.value = ''; availableOnly.value = false })
watch([selectedId, selectedName], ([id, name]) => { if (id && !name) selectedId.value = '' })
function blockedLabel(source: MaterialSource) {
  return source.blockedReason || (source.kind === 'conquest' ? '已领取' : source.kind === 'garrison' ? '需攻克' : '未开放')
}
function availableCount(id: string) { return (sources.value[id] ?? []).filter(source => source.available).length }
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
    <div class="source-toolbar"><input v-model="search" class="source-search" type="search" aria-label="查找材料" placeholder="查找材料" /><button class="btn btn-small" :class="{'btn-primary':availableOnly}" :aria-pressed="availableOnly" @click="availableOnly=!availableOnly">只看可前往</button></div>
    <div class="material-list" tabindex="0" aria-label="可查阅的材料"><button v-for="[id,name] in materials" :key="id" class="material-entry" :class="{available:availableCount(id)>0}" aria-haspopup="dialog" @click="selectedId=id"><ItemIcon :id="id" :size="30" /><span class="material-copy"><strong>{{ name }}</strong><span>持有 {{ number(store.state?.inventory[id]??0) }}</span><small>{{ availableCount(id) }} 处可前往 · 查看来源</small></span></button></div>
    <div v-if="!materials.length" class="source-empty"><p>未找到对应材料，可换个名称查找{{ availableOnly ? '，或查看全部来源' : '' }}。</p><button v-if="search||availableOnly" class="btn btn-small" @click="search='';availableOnly=false">查看全部材料</button></div>
    <PanelModal v-if="selectedName" :title="selectedName" subtitle="材料来源" @close="selectedId=''">
      <div class="source-summary"><ItemIcon :id="selectedId" :size="43" /><div><strong>{{ selectedName }}</strong><span>持有 {{ number(store.state?.inventory[selectedId]??0) }} · {{ availableCount(selectedId) }} 处可前往</span></div></div>
      <div v-for="source in sources[selectedId]" :key="source.kind + (source.sectId ?? source.label)" class="source-row" :class="{unavailable:!source.available}">
        <span class="source-label"><small>{{ sourceNames[source.kind] }}</small>{{ source.label }}</span>
        <span class="source-detail">{{ source.detail }}</span>
        <strong v-if="source.rate !== undefined">+{{ number(source.rate,2) }}/时</strong>
        <button class="btn btn-small btn-quiet" :disabled="!source.available" @click="go(selectedId,source)">{{ source.available ? '前往' : blockedLabel(source) }}</button>
      </div>
      <p v-if="!sources[selectedId]?.length" class="muted">暂无已开放来源。</p>
    </PanelModal>
  </section>
</template>

<style scoped>
.source-search{width:100%;margin-bottom:12px;min-height:44px}.material-list{max-height:min(54dvh,520px);overflow-y:auto;overscroll-behavior:contain;scrollbar-gutter:stable;display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px}.material-entry{min-width:0;padding:12px;text-align:left;border:1px solid #c8bea3;background:#f3ecd8;min-height:66px}.material-entry strong{display:block;font:16px 'SimSun',serif;color:var(--jade)}.material-entry>.material-copy{display:block;margin-top:0}.material-list:focus-visible,.material-entry:focus-visible{outline:2px solid var(--jade);outline-offset:2px}
.material-sources{margin:18px 0}.material-sources h3{font-size:21px;margin:4px 0}.material-sources>.muted{font-size:11px;margin:6px 0 16px}.source-row{display:flex;align-items:center;gap:10px;padding:7px 0;border-top:1px solid #ddd3b8;font-size:11px}.source-label{flex:none;min-width:110px;color:var(--ink)}.source-detail{flex:1;color:var(--muted)}.source-row strong{font-weight:500;color:var(--jade)}.source-row.unavailable .source-label,.source-row.unavailable .source-detail{opacity:.6}.source-row .btn{font-size:10px;padding:3px 8px}@media(max-width:640px){.source-row{flex-wrap:wrap}.source-label{min-width:0}.source-detail{flex-basis:100%;order:3}.source-row .btn{margin-left:auto}}
.material-sources{margin:8px 0 18px}.material-sources>.section-heading .eyebrow{font-size:10px;letter-spacing:.08em;color:#8c6844}.material-sources h3{font-size:23px;color:#213f36}.material-sources>.muted{line-height:1.8}.source-toolbar{display:flex;gap:8px;margin-bottom:12px}.source-toolbar>.source-search{margin:0;min-width:0;flex:1;background:#f6f1df;border-color:#b8c4a5}.source-toolbar>.btn{flex:none;font-size:11px;min-height:44px}.material-list{gap:7px;grid-template-columns:repeat(auto-fill,minmax(185px,1fr));padding:1px}.material-entry{display:flex;gap:10px;align-items:center;padding:12px;min-height:92px;border-color:#c8cbb0;background:#f1efdf;border-bottom:2px solid #b9c6a4}.material-entry.available{background:#f6f1df}.material-entry>.item-icon{flex:none}.material-copy{min-width:0;flex:1}.material-entry .material-copy>strong{font-size:16px;line-height:1.5;color:#213f36}.material-entry .material-copy>span{display:block;color:var(--muted);font-size:10px;margin-top:4px;font-variant-numeric:tabular-nums}.material-entry .material-copy>small{display:block;font-size:10px;line-height:1.7;margin-top:4px;color:#8b8b72}.material-entry.available .material-copy>small{color:#326c55}.material-entry:hover{border-color:#7d9a74}.source-summary{display:flex;gap:13px;align-items:center;padding:2px 0 17px;border-bottom:2px solid #a8ba96}.source-summary>div{min-width:0}.source-summary strong{display:block;font:24px 'SimSun',serif;color:#213f36}.source-summary>div>span{display:block;font-size:11px;color:#6b785e;margin-top:7px;font-variant-numeric:tabular-nums}.source-row{padding:13px 0;border-color:#d5d9bf;gap:12px;line-height:1.8}.source-label{display:flex;align-items:center;gap:7px;min-width:0;max-width:45%;font-size:12px;color:#213f36}.source-label>small{display:inline-block;flex:none;padding:0 5px;border:1px solid #b9c7a8;background:#e5ecd8;color:#326c55;font-size:9px}.source-detail{font-size:11px}.source-row>strong{flex:none;font-variant-numeric:tabular-nums}.source-row.unavailable .source-label>small{background:#e9e7d7;border-color:#c4c3ab;color:#8a896f}.source-row>.btn{flex:none;min-height:36px;max-width:145px;white-space:normal;font-size:11px}.source-empty{padding:16px;border:1px dashed #bdc6a8;background:#f1f1df}.source-empty p{font-size:12px;line-height:1.8;color:var(--muted);margin:0 0 12px}.source-toolbar>.btn:focus-visible,.source-empty>.btn:focus-visible,.source-row>.btn:focus-visible{outline:2px solid #326c55;outline-offset:2px}
@media(max-width:640px){.material-list{grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.material-entry{flex-direction:column;align-items:flex-start;gap:8px;padding:10px;min-height:133px}.material-entry .material-copy>strong{font-size:16px}.material-entry .material-copy>span,.material-entry .material-copy>small{font-size:11px}.source-toolbar{gap:6px}.source-toolbar>.btn{font-size:11px;padding-inline:8px}.source-row{gap:7px;align-items:flex-start}.source-label{max-width:none;flex:1;flex-wrap:wrap;font-size:13px;line-height:1.8}.source-label>small{font-size:10px}.source-row>.btn{min-height:44px;max-width:120px;font-size:11px;margin-left:auto}.source-row>.source-detail{font-size:12px;line-height:1.8}.source-row>strong{order:4;font-size:12px}.source-summary>div>span{font-size:12px}.source-empty>.btn{min-height:44px}}
</style>
