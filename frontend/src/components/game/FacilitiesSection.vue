<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { FacilityView } from '../../api/client'
import { resourceName } from '../../presentation/gameText'
import { number } from '../../shared/format'
import { useGameStore } from '../../stores/game'

const emit = defineEmits<{ open: [panel: string] }>()
const store = useGameStore()
const facilities = ref<FacilityView[]>([])
const loading = ref(false)
const selected = ref('hall')
const current = computed(() => facilities.value.find(item => item.id === selected.value))
const costEntries = computed(() => Object.entries(current.value?.costs ?? {}))
const readyCosts = computed(() => costEntries.value.filter(([id, amount]) => held(id) >= amount).length)
const seals: Record<string, string> = { hall: '宗', forge: '器', alchemy: '丹', tower: '道', training: '武' }
let request = 0
async function load() {
  const currentRequest = ++request
  facilities.value = []
  loading.value = true
  const result = await store.previewFacilities()
  if (currentRequest !== request) return
  facilities.value = result?.facilities ?? []
  loading.value = false
}
watch([() => store.revision, () => store.slotId], load, { immediate: true })
function held(id: string) {
  if (id === 'spirit_stone' || id === 'cultivation' || id === 'reputation' || id === 'stamina') {
    return store.resources?.[id] ?? 0
  }
  return store.state?.inventory[id] ?? 0
}
function findMaterial(id: string) {
  emit('open', store.planProduction(id))
}
</script>

<template>
  <section class="facilities-section" aria-label="宗门设施升级">
    <div class="section-heading">
      <div>
        <span class="eyebrow">宗门营造</span>
        <h3>修楼阁，养百业</h3>
      </div>
      <span class="badge badge-gold">宗门 {{ store.state?.facility_levels.hall ?? 1 }} 级</span>
    </div>
    <p class="muted">主殿统筹设施上限。升级设施后，再以材料提升器具、丹药与弟子。</p>
    <p v-if="loading" class="notice-box" role="status">正在查阅设施与升级所需……</p>
    <div v-else-if="facilities.length" class="facility-layout">
      <div class="facility-list" aria-label="选择设施">
        <button
          v-for="facility in facilities"
          :key="facility.id"
          :class="{active:selected===facility.id}"
          :aria-pressed="selected===facility.id"
          @click="selected=facility.id"
        >
          <span class="facility-seal" aria-hidden="true">{{ seals[facility.id] }}</span>
          <span>
            <strong>{{ facility.name }}</strong>
            <small>{{ facility.level }} / {{ facility.max_level }} 级</small>
            <span class="facility-progress" aria-hidden="true"><i :style="{width:`${facility.level/facility.max_level*100}%`}"></i></span>
          </span>
          <span v-if="facility.upgradeable" class="upgrade-dot" aria-label="可以升级"></span>
        </button>
      </div>
      <article v-if="current" class="facility-detail">
        <header class="facility-detail-head"><span class="building-mark" aria-hidden="true">{{ seals[current.id] }}</span><div><span class="eyebrow">{{ current.level === current.max_level ? '此阶已成' : '下一步建设' }}</span><h3>{{ current.name }}<small>{{ current.level }} 级</small></h3></div></header>
        <div class="effect-section"><span>当前效果</span><p class="current-effect">{{ current.description }}</p></div>
        <template v-if="current.level < current.max_level">
          <div class="next-effect">
            <span>升至 {{ current.level+1 }} 级</span>
            <strong>{{ current.next_description }}</strong>
          </div>
          <div class="cost-heading"><strong>建设材料</strong><span>{{ readyCosts }} / {{ costEntries.length }} 项已备齐</span></div>
          <div class="facility-costs">
            <div v-for="(amount,id) in current.costs" :key="id" :class="{missing:held(id)<amount}">
              <span>{{ resourceName(id,store.catalog) }}</span>
              <strong>{{ number(held(id),1) }} / {{ amount }}</strong>
              <button v-if="held(id)<amount" class="btn btn-small btn-quiet" @click="findMaterial(id)">
                缺
                {{ number(amount-held(id),1) }}
                ·
                {{ store.productionDestination(id).label }}
              </button>
            </div>
          </div>
          <p v-if="current.reason" class="muted">{{ current.reason }}</p>
          <button
            class="btn btn-primary"
            :disabled="store.busy || !current.upgradeable"
            @click="store.upgradeFacility(current.id)"
          >
            升级
            {{ current.name }}
          </button>
        </template>
        <div v-else class="facility-complete"><strong>楼阁已成</strong><p>已达本期最高等级，可以继续培养弟子与装备。</p><button class="btn btn-small" @click="emit('open',current.id==='alchemy'?'alchemy':current.id==='forge'?'forge':'codex')">{{ current.id==='alchemy'?'前往炼丹房':current.id==='forge'?'前往炼器阁':'前往弟子堂' }}</button></div>
      </article>
    </div>
    <button
      v-else
      class="btn btn-small"
      :disabled="store.busy"
      @click="load"
    >
      重新查阅设施
    </button>
  </section>
</template>

<style scoped>
.facilities-section{margin:18px 0 26px}.facilities-section>.section-heading{margin-bottom:8px}.facilities-section>.section-heading h3{font-size:21px;margin:4px 0}.facility-layout{display:grid;grid-template-columns:180px minmax(0,1fr);gap:16px;margin-top:18px}.facility-list{display:flex;flex-direction:column;gap:7px}.facility-list>button{display:flex;align-items:center;gap:11px;position:relative;padding:12px;text-align:left;border:1px solid #c8bea3;background:#eae5d3;min-height:66px}.facility-list>button.active{border-color:var(--jade);background:#e2e8d5;box-shadow:inset 3px 0 var(--jade)}.facility-seal{font:25px 'SimSun',serif;color:var(--gold)}.facility-list strong,.facility-list small{display:block}.facility-list strong{font:15px 'SimSun',serif}.facility-list small{font-size:10px;color:var(--muted);margin-top:5px}.upgrade-dot{width:5px;height:5px;background:var(--jade);margin-left:auto}.facility-detail{border:1px solid #c6b891;background:#f6efdb;padding:22px}.facility-detail>h3{font-size:27px;margin:5px 0 12px}.facility-detail h3 small{font-size:13px;color:var(--muted)}.current-effect{color:var(--muted);font-size:12px;line-height:1.7}.next-effect{display:flex;flex-direction:column;gap:7px;background:#e4ead5;border-left:3px solid var(--jade);padding:13px;margin:16px 0}.next-effect span{font-size:10px;color:var(--muted)}.next-effect strong{font-size:13px;color:var(--jade);font-weight:500}.facility-costs>div{display:flex;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid #d9ceb0;font-size:12px}.facility-costs strong{margin-left:auto;font-weight:500}.facility-costs .missing>strong{color:var(--danger)}.facility-costs .btn{font-size:10px;padding:4px 7px}.facility-detail>.btn{margin-top:14px;width:100%}.facility-detail>.muted{font-size:11px;margin-top:10px}@media(max-width:640px){.facility-layout{grid-template-columns:1fr}.facility-list{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px}.facility-list>button{padding:8px;gap:7px;min-height:58px}.facility-list strong{font-size:12px}.facility-seal{font-size:20px}.facility-detail{padding:16px}.facility-costs>div{flex-wrap:wrap}.facility-costs .btn{margin-left:auto}.facilities-section>.section-heading{align-items:flex-start;gap:12px}.facilities-section>.section-heading h3{font-size:18px}}
.facilities-section{margin:8px 0 18px}.facilities-section>.section-heading .eyebrow{font-size:10px;letter-spacing:.1em;color:#8c6844}.facilities-section>.section-heading h3{color:#213f36;font-size:23px}.facilities-section>.muted{font-size:11px;line-height:1.8}.facility-layout{grid-template-columns:184px minmax(0,1fr);gap:13px;margin-top:15px}.facility-list>button{min-height:75px;padding:11px;border-color:#c1c9ad;background:#efeedf}.facility-list>button.active{border-color:#70916f;background:#e5ecd8;box-shadow:inset 3px 0 #326c55}.facility-list>button>span:nth-child(2){flex:1;min-width:0}.facility-seal{display:grid;place-items:center;width:33px;height:38px;flex:none;background:#e2e6d1;color:#326c55;border:1px solid #a6b696;font-size:22px}.facility-list>button.active .facility-seal{background:#326c55;color:#f6f1df;border-color:#326c55}.facility-list strong{color:#213f36}.facility-list small{font-variant-numeric:tabular-nums}.facility-progress{display:block;height:3px;background:#d4d9c3;margin-top:7px}.facility-progress>i{display:block;height:100%;background:#8ca37a}.facility-list>button.active .facility-progress>i{background:#326c55}.upgrade-dot{position:absolute;top:10px;right:9px;width:5px;height:5px;background:#b38a46;transform:rotate(45deg)}.facility-detail{padding:18px;border-color:#b9c5a6;background:#f6f1df}.facility-detail-head{display:flex;align-items:center;gap:13px;padding-bottom:15px;border-bottom:1px solid #d5d8bf}.building-mark{width:53px;height:56px;display:grid;place-items:center;border:1px solid #7a9a7d;box-shadow:inset 0 0 0 4px #f6f1df,inset 0 0 0 5px #a6b696;font:30px 'SimSun',serif;color:#326c55;background:#e5ecd8}.facility-detail-head .eyebrow{font-size:10px;color:#8c6844;letter-spacing:0}.facility-detail-head h3{font-size:25px;margin:5px 0 0;color:#213f36}.facility-detail-head h3 small{margin-left:9px;font-size:12px;font-variant-numeric:tabular-nums}.effect-section{padding-top:13px}.effect-section>span,.cost-heading>strong{font-size:10px;font-weight:400;color:#8c6844}.effect-section>.current-effect{font-size:12px;color:#405846;line-height:1.8;margin:5px 0}.next-effect{margin:12px 0 15px;padding:11px 13px;border-left-color:#326c55;background:#e5ecd8}.next-effect strong{line-height:1.8;color:#326c55}.cost-heading{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:2px}.cost-heading>span{font-size:10px;color:#6c7b60;font-variant-numeric:tabular-nums}.facility-costs>div{font-variant-numeric:tabular-nums;border-bottom-color:#dbd9c1}.facility-costs .missing>strong{color:var(--danger)}.facility-costs .btn{max-width:100%;white-space:normal}.facility-list>button:focus-visible,.facility-detail button:focus-visible{outline:2px solid #326c55;outline-offset:2px}.facility-complete{padding:15px 0 0}.facility-complete>strong{font:19px 'SimSun',serif;color:#326c55}.facility-complete>p{font-size:12px;line-height:1.8;color:var(--muted)}
@media(max-width:640px){.facility-layout{grid-template-columns:1fr;gap:12px}.facility-list{grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}.facility-list>button{min-height:74px;padding:8px;gap:7px}.facility-seal{width:24px;height:31px;font-size:19px}.facility-list strong{font-size:12px;line-height:1.5}.facility-list small{font-size:10px;margin-top:3px}.facility-list .upgrade-dot{top:6px;right:5px;width:4px;height:4px}.facility-detail{padding:15px}.facility-detail-head{gap:11px;padding-bottom:12px}.building-mark{width:44px;height:49px;font-size:26px}.facility-detail-head h3{font-size:23px}.facilities-section>.section-heading h3{font-size:21px}.facility-costs>div{font-size:12px;gap:7px}.facility-costs .btn{min-height:44px;font-size:11px}.facility-detail>.btn{min-height:44px}.next-effect strong{font-size:12px}.cost-heading>span,.effect-section>span,.cost-heading>strong{font-size:11px}.facility-complete>.btn{min-height:44px}}
</style>
