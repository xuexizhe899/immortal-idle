<script setup lang="ts">
import { computed } from 'vue'
import { discipleImage } from '../presentation/assetPaths'
import { leanNames, leanDescriptions, resourceName, statNames, matchesProductionTarget, resourceDutyLeans } from '../presentation/gameText'
import { number } from '../shared/format'
import { useGameStore } from '../stores/game'

defineProps<{ readOnly?: boolean }>()
const emit = defineEmits<{ open: [panel: string] }>()
const store = useGameStore()
const catalog = computed(() => store.catalog)
const slots = computed(() => store.state?.duty_slots ?? [])
const onDuty = computed(() => new Set(slots.value.map(slot => slot.disciple_id)))
const production = computed(() => store.production)
const externalTarget = computed(() => !!store.productionTarget
  && store.productionDestination(store.productionTarget).panel === 'expedition')
const targetHint = computed(() => {
  if (externalTarget.value) return '本宗值守不产出这种材料，请前往对应外宗征讨或安排驻守。'
  const lean = resourceDutyLeans[store.productionTarget]
  return lean ? `已优先显示${leanNames[lean]}倾向弟子，其值守贡献对应${resourceName(store.productionTarget, catalog.value)}。`
    : '已优先显示专长匹配的弟子，可提高对应材料的产出。'
})
const roster = computed(() => [...store.disciples].sort((a, b) =>
  Number(matchesTarget(b.template_id)) - Number(matchesTarget(a.template_id)),
))
function matchesTarget(templateId: string) {
  return !externalTarget.value && matchesProductionTarget(catalog.value?.disciples[templateId], store.productionTarget)
}
function member(index: number) { return store.disciples.find(d => d.id === slots.value[index]?.disciple_id) }
function specialty(templateId: string) { return catalog.value?.disciples[templateId]?.production_specialty ?? '' }
function postOf(id: string) {
  return store.state?.sects.find(sect => sect.garrison.some(slot => slot.disciple_id === id))?.name
}
async function toggle(id: string) {
  if (onDuty.value.has(id)) await store.unassignDuty(id)
  else await store.assignDuty(id)
}
</script>
<template>
  <div class="section-heading">
    <div>
      <h3>因材任人，各有所长</h3>
      <p class="muted">演武场 {{ store.state?.facility_levels.training ?? 1 }} 级 · 按当前缺口安排专长弟子。</p>
    </div>
    <span class="badge">{{ slots.length }} / 6 席</span>
  </div>
  <label class="production-target">
    当前需要
    <select v-model="store.productionTarget">
      <option value="">全部资源</option>
      <option v-for="(name,id) in catalog?.materials" :key="id" :value="id">{{ name }}</option>
      <option value="cultivation">修为</option>
      <option value="spirit_stone">灵石</option>
      <option value="stamina">行动力</option>
    </select>
  </label>
  <p v-if="store.productionTarget" class="notice-box">
    {{ resourceName(store.productionTarget,catalog) }}
    · 持有
    {{ number(store.state?.inventory[store.productionTarget] ?? store.resources?.[store.productionTarget as 'cultivation'|'spirit_stone'|'stamina'],1) }}
    · 当前时产
    {{ number(store.production.materials[store.productionTarget] ?? store.production[store.productionTarget as 'cultivation'|'spirit_stone'|'stamina'],2) }}
    。
    {{ targetHint }}
    <button
      v-if="externalTarget"
      class="btn btn-small"
      @click="emit('open',store.planProduction(store.productionTarget))"
    >
      {{ store.productionDestination(store.productionTarget).label }}
    </button>
  </p>
  <div class="duty-slots">
    <div
      v-for="i in 6"
      :key="i"
      class="duty-slot"
      :class="{filled:member(i-1)}"
    >
      <template v-if="member(i-1)">
        <img
          :src="discipleImage(member(i-1)!.template_id,catalog)"
          alt=""
          class="pixel-art"
          loading="lazy"
        />
        <strong>{{ catalog?.disciples[member(i-1)!.template_id]?.name }}</strong>
        <span>专长 · {{ resourceName(specialty(member(i-1)!.template_id),catalog) }}</span>
        <button
          class="btn btn-small btn-quiet"
          :disabled="readOnly||store.busy"
          @click="toggle(member(i-1)!.id)"
        >
          卸下值守
        </button>
      </template>
      <template v-else>
        <span class="slot-number">{{ String(i).padStart(2,'0') }}</span>
        <strong>待安排</strong>
        <span>选择下方弟子上岗</span>
      </template>
    </div>
  </div>
  <div class="production-panel">
    <div class="section-heading">
      <h4>宗门每小时总产出</h4>
      <span class="muted">包含外宗驻守 · 按实际在岗时间结算</span>
    </div>
    <div class="production-grid">
      <div v-for="key in ['cultivation','spirit_stone','stamina'] as const" :key="key">
        <span>{{ statNames[key] }}</span>
        <strong>
          +
          {{ number(production[key],2) }}
          <small>/时</small>
        </strong>
      </div>
      <div v-for="(value,id) in production.materials" :key="id">
        <span>{{ resourceName(id,catalog) }}</span>
        <strong>
          +
          {{ number(value,2) }}
          <small>/时</small>
        </strong>
      </div>
    </div>
  </div>
  <div class="section-heading">
    <h3>安排弟子</h3>
    <span class="muted">出征自动离岗，结算自动回岗</span>
  </div>
  <div class="duty-roster">
    <div
      v-for="disciple in roster"
      :key="disciple.id"
      class="duty-row"
      :class="{matching:matchesTarget(disciple.template_id)}"
    >
      <img
        :src="discipleImage(disciple.template_id,catalog)"
        alt=""
        class="pixel-art"
        loading="lazy"
      />
      <div class="duty-person">
        <strong>
          {{ catalog?.disciples[disciple.template_id]?.name }}
          <small>{{ leanNames[catalog?.disciples[disciple.template_id]?.lean ?? ''] }}</small>
        </strong>
        <span>专长 · {{ resourceName(specialty(disciple.template_id),catalog) }}</span>
        <span>
          {{ leanDescriptions[catalog?.disciples[disciple.template_id]?.lean ?? ''] }}
          {{ postOf(disciple.id) ? ` · 驻守${postOf(disciple.id)}` : '' }}
        </span>
      </div>
      <span v-if="disciple.injury_stacks" class="badge badge-danger">有伤可值守</span>
      <button
        class="btn btn-small"
        :class="{'btn-primary':!onDuty.has(disciple.id)}"
        :disabled="readOnly||store.busy||disciple.busy||(!onDuty.has(disciple.id)&&slots.length>=6)"
        @click="toggle(disciple.id)"
      >
        {{ disciple.busy ? '出征中' : onDuty.has(disciple.id) ? '下岗' : slots.length>=6 ? '编制已满' : postOf(disciple.id) ? '调回值守' : '安排上岗' }}
      </button>
    </div>
  </div>
</template>
<style scoped>
.section-heading p{margin:4px 0 0}.duty-slots{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:9px;margin:20px 0}.duty-slot{min-height:158px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;background:#ebe8d9;border:1px dashed #b6bba2;padding:8px 5px}.duty-slot.filled{border-style:solid;border-color:#adbea1;background:#e5e9d7}.duty-slot>img{width:64px;height:75px;object-fit:cover;object-position:top}.duty-slot>strong{font-size:12px;margin-top:5px}.duty-slot>span{font-size:9px;color:var(--muted)}.duty-slot .slot-number{font:32px 'SimSun',serif;color:#b9c0aa;margin-bottom:10px}.duty-slot .btn{font-size:9px;padding:2px 5px;min-height:26px}.production-panel{padding:18px;background:#ebe8d8;border:1px solid #d0c8ac;margin-bottom:24px}.production-panel h4{margin:0}.production-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(100px,1fr));gap:12px}.production-grid>div>span{display:block;color:var(--muted);font-size:11px}.production-grid strong{font-size:21px;font-weight:500;color:var(--jade)}.production-grid small{font-size:10px;color:var(--muted);margin-left:5px}.rate-chips{margin-top:14px}.duty-row{display:flex;align-items:center;gap:14px;border-bottom:1px solid #d9d0b8;padding:10px 0}.duty-row>img{width:44px;height:52px;object-fit:cover;object-position:top;background:#e9e5d3}.duty-person{flex:1}.duty-person strong{display:block;font-family:'SimSun',serif;font-size:15px}.duty-person span{display:block;color:var(--muted);font-size:10px}
@media(max-width:640px){.duty-slots{grid-template-columns:repeat(3,minmax(0,1fr))}.duty-slot{min-height:145px}.duty-row{gap:9px}.duty-row>.badge{display:none}.production-panel .section-heading{align-items:flex-start;flex-direction:column;gap:4px}.production-panel{padding:14px}.production-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.production-grid strong{font-size:18px}.duty-row>.btn{font-size:10px;padding-inline:8px}.duty-person span{max-width:150px}}
</style>

<style scoped>.production-target{display:flex;align-items:center;gap:16px;font-size:12px;margin:12px 0}.production-target select{flex:1}.duty-row.matching{background:#dce8cc;padding-inline:10px;border-left:3px solid var(--jade)}.duty-person small{font-size:10px;color:var(--gold)}</style>
