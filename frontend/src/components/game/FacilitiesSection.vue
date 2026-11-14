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
        <span class="eyebrow">经营宗门 · 修筑山门</span>
        <h3>把下一步修行，落在实处</h3>
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
          <span class="facility-seal">{{ seals[facility.id] }}</span>
          <span>
            <strong>{{ facility.name }}</strong>
            <small>{{ facility.level }} / {{ facility.max_level }} 级</small>
          </span>
          <span v-if="facility.upgradeable" class="upgrade-dot" aria-label="可以升级"></span>
        </button>
      </div>
      <article v-if="current" class="facility-detail">
        <span class="eyebrow">{{ current.level === current.max_level ? '此阶已成' : '下一步建设' }}</span>
        <h3>
          {{ current.name }}
          <small>{{ current.level }} 级</small>
        </h3>
        <p class="current-effect">{{ current.description }}</p>
        <template v-if="current.level < current.max_level">
          <div class="next-effect">
            <span>升至 {{ current.level+1 }} 级</span>
            <strong>{{ current.next_description }}</strong>
          </div>
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
        <p v-else class="notice-box">已达本期最高等级，可以继续培养弟子与装备。</p>
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
</style>
